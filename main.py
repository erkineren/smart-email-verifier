import smtplib
import socket
import dns.resolver
import re
import uuid
import logging
import os
from functools import lru_cache
from dotenv import load_dotenv
from dataclasses import dataclass, asdict
import json
import sys

from pathlib import Path

env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')


@lru_cache(maxsize=512)
def _resolve_mx(domain: str) -> list[str]:
    """Cached MX lookup — same domain is only queried once per process."""
    try:
        answers = dns.resolver.resolve(domain, "MX")
        records = sorted(answers, key=lambda r: r.preference)
        hosts = []
        for r in records:
            host = str(r.exchange).rstrip(".")
            if "mx-verification" in host:
                continue
            hosts.append(host)
        return hosts
    except Exception as e:
        logging.debug(f"DNS Error: {e}")
        return []


@dataclass
class VerificationResult:
    email: str
    domain: str
    is_valid_syntax: bool
    has_mx_records: bool
    is_catch_all: bool | None
    is_deliverable: bool | None
    smtp_code: int | None
    smtp_message: str | None
    error: str | None
    mx_hosts: list[str]


class SmartEmailVerifier:
    def __init__(self, helo_host=None, mail_from=None, timeout=None):
        """
        :param helo_host: Domain to identify the server during the HELO phase (important for reputation)
        :param mail_from: Sender address to be used in the MAIL FROM command
        :param timeout: Connection and response wait time (seconds)
        """
        self.helo_host = helo_host or os.getenv("HELO_HOST", "mail.example.com")
        self.mail_from = mail_from or os.getenv("MAIL_FROM", "verify@example.com")
        self.timeout = int(timeout or os.getenv("SMTP_TIMEOUT", "15"))
        self.email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

    def check_syntax(self, email: str) -> bool:
        return bool(self.email_regex.match(email))

    def get_mx_records(self, domain: str) -> list[str]:
        return _resolve_mx(domain)

    def _test_smtp(
        self,
        email: str,
        mx_host: str,
        catch_all_email: str | None = None,
    ) -> tuple[
        tuple[int | None, str | None, str | None],
        tuple[int | None, str | None, str | None] | None,
    ]:
        """
        Establishes a single SMTP session against mx_host and tests *email*.
        If *catch_all_email* is provided, also tests that address in the same
        session (saves a full TCP + EHLO + MAIL FROM round-trip).

        Returns:
            (real_result, catchall_result)
            Each result is (smtp_code, smtp_message, error_string).
            catchall_result is None when catch_all_email is not provided.
        """
        server = None
        try:
            # Use instance-level timeout only — avoids mutating the global
            # socket default which is not thread-safe under concurrent use.
            server = smtplib.SMTP(timeout=self.timeout)
            server.set_debuglevel(0)
            server.connect(mx_host, 25)

            code, msg = server.ehlo(self.helo_host)
            if code >= 400:
                code, msg = server.helo(self.helo_host)

            code, msg = server.mail(self.mail_from)
            if code >= 400:
                err = f"MAIL FROM rejected by {mx_host}."
                return (code, str(msg), err), None

            # Test real email
            code, msg = server.rcpt(email)
            msg_text = msg.decode(errors='ignore') if isinstance(msg, bytes) else str(msg)
            real_result: tuple[int | None, str | None, str | None] = (code, msg_text, None)

            # Optionally test catch-all in the same session (no extra TCP connection)
            catchall_result: tuple[int | None, str | None, str | None] | None = None
            if catch_all_email is not None:
                try:
                    ca_code, ca_msg = server.rcpt(catch_all_email)
                    ca_text = ca_msg.decode(errors='ignore') if isinstance(ca_msg, bytes) else str(ca_msg)
                    catchall_result = (ca_code, ca_text, None)
                except Exception as e:
                    catchall_result = (None, None, f"Catch-all probe error: {e}")

            return real_result, catchall_result

        except (socket.timeout, TimeoutError):
            err = f"Timeout ({mx_host}): Port 25 might be blocked by ISP/Network."
            return (None, None, err), None
        except ConnectionRefusedError:
            return (None, None, f"Connection Refused ({mx_host})."), None
        except Exception as e:
            return (None, None, f"Error ({mx_host}): {type(e).__name__} - {e}"), None
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass

    def verify(self, email: str) -> VerificationResult:
        if not self.check_syntax(email):
            return VerificationResult(email, "", False, False, None, False, None, None, "Invalid email format", [])

        local_part, domain = email.rsplit("@", 1)
        mx_hosts = self.get_mx_records(domain)

        if not mx_hosts:
            return VerificationResult(email, domain, True, False, None, False, None, None, "No MX records found for the domain", [])

        target_code: int | None = None
        target_msg: str | None = None
        target_error: str | None = "Could not connect to any MX server. Port 25 might be closed."
        is_deliverable: bool | None = None
        is_catch_all: bool = False

        # Pre-generate catch-all probe so both RCPTs share one SMTP session.
        random_email = f"catchall_test_{uuid.uuid4().hex[:8]}@{domain}"

        for mx in mx_hosts:
            real_res, ca_res = self._test_smtp(email, mx, catch_all_email=random_email)
            target_code, target_msg, target_error = real_res

            if target_code in (250, 251):
                is_deliverable = True
                if ca_res is not None:
                    is_catch_all = ca_res[0] in (250, 251)
                break
            elif target_code in (550, 551, 553):
                is_deliverable = False
                break
            # On timeout / connection error — try next MX

        return VerificationResult(
            email=email,
            domain=domain,
            is_valid_syntax=True,
            has_mx_records=True,
            is_catch_all=is_catch_all if is_deliverable is not None else None,
            is_deliverable=is_deliverable,
            smtp_code=target_code,
            smtp_message=target_msg,
            error=target_error if is_deliverable is None else None,
            mx_hosts=mx_hosts
        )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <email>")
        sys.exit(1)

    email = sys.argv[1]

    # Initialize without arguments to fetch from ENV file (ideal for app.py and Docker environment)
    # If you want to force parameters:
    # verifier = SmartEmailVerifier(helo_host="...", mail_from="...", timeout=15)
    verifier = SmartEmailVerifier()

    result = verifier.verify(email)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))