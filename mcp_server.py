#!/usr/bin/env python3
import os
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List
import asyncio

from main import SmartEmailVerifier

from pathlib import Path

# Load configuration so the agent inherits the same bypass settings
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# Initialize the FastMCP server
mcp = FastMCP("Email Verifier MCP", streamable_http_path="/")

@mcp.tool()
def verify_email(email: str) -> Dict[str, Any]:
    """
    Verifies the existence of an email address using advanced SMTP checks.
    It performs syntax checking, MX record resolution, Trap/Catch-All detection,
    and returns whether the email is definitively deliverable.
    
    Use this tool whenever the user asks to verify, check, or test an email address.
    """
    # Create an instance of the verifier (inherits from ENV variables like the web API)
    verifier = SmartEmailVerifier()
    
    # Perform verification
    result = verifier.verify(email)
    
    # Convert dataclass to dictionary for JSON serialization through MCP
    from dataclasses import asdict
    return asdict(result)

@mcp.tool()
async def verify_emails_bulk(emails: List[str]) -> Dict[str, Any]:
    """
    Verifies a list of email addresses concurrently.
    Uses advanced SMTP checks to determine existence and Catch-All status.
    Max 10 concurrent checks to prevent IP blocking.
    Use this tool when the user provides multiple emails (e.g. an array or a list).
    """
    verifier = SmartEmailVerifier()
    semaphore = asyncio.Semaphore(10)

    async def verify_with_semaphore(email: str):
        async with semaphore:
            return await asyncio.to_thread(verifier.verify, email)

    tasks = [verify_with_semaphore(email) for email in emails]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    results = []
    from dataclasses import asdict
    for i, res in enumerate(completed):
        if isinstance(res, Exception):
            results.append({"email": emails[i], "error": str(res)})
        else:
            results.append(asdict(res))
            
    return {"total": len(results), "results": results}

if __name__ == "__main__":
    # Start the MCP server using Standard I/O (STDIO)
    # This is the standard mechanism for local AI Agents (Claude Desktop, Cursor)
    mcp.run(transport='stdio')
