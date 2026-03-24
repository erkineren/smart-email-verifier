# Smart Email Verifier

A production-ready, advanced email verification system built in Python. This service performs deep SMTP validation, Catch-All (tarpit) detection, and MX record resolution, ensuring high accuracy for deliverability checks. It can be used as a standalone script, a REST API built with FastAPI, or an AI-Agent tool via the Model Context Protocol (MCP).

## Features

- **Advanced SMTP Validation:** Connects directly to domain MX servers to verify if an email address actually exists.
- **Catch-All / Tarpit Detection:** Bypasses "always accept" configurations used by some email providers (e.g., Google Workspace, Office 365) by testing random non-existent addresses.
- **FastAPI REST API:** High-performance, highly concurrent REST API with robust authentication via API Keys.
- **Bulk Verification:** Verify multiple emails concurrently while limiting connections to prevent IP rate-limiting.
- **MCP Server Support:** Easily integrate with AI assistants (like Claude Desktop or Cursor) using the `mcp_server.py`.
- **Docker Ready:** Fully containerized setup with a `docker-compose` configuration for immediate deployment.

---

## 🚀 Getting Started (Standalone & Local)

### 1. Requirements

- Python 3.10+
- `pip`

### 2. Installation

Clone the repository and install the dependencies:

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

Copy the example environment file and adjust the values according to your needs:

```bash
cp .env.example .env
```

**Key Variables in `.env`:**
- `API_KEY`: The secret key required for authenticating with the FastAPI endpoints.
- `HELO_HOST`: Formatted as `mail.yourdomain.com` (critical for maintaining good SMTP reputation).
- `MAIL_FROM`: The standard reply-to address used in `MAIL FROM` during SMTP probes.
- `SMTP_TIMEOUT`: Connection timeout limits (default 15 to combat tarpitting).

---

## 💻 Usage Methods

### Method 1: CLI (Standalone Script)

You can run a single email check natively via the terminal:

```bash
python main.py test@example.com
```

### Method 2: FastAPI Web Server

Start the REST API server locally using `uvicorn`:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

#### API Endpoints

**1. Verification Endpoint (Single)**
```http
GET /verify/example@google.com
X-API-Key: your_super_secret_api_key_here
```

**2. Bulk Verification Endpoint**
```http
POST /verify/bulk
X-API-Key: your_super_secret_api_key_here
Content-Type: application/json

{
  "emails": ["test1@google.com", "fake@example.com"]
}
```

**3. Health Check**
```http
GET /health
```

### Method 3: Docker Deployment

Deploy the API seamlessly using Docker and Docker Compose:

```bash
docker-compose up -d --build
```
This will start the API on `http://localhost:8000` inside a detached container (`smart_email_verifier`).

### Method 4: Model Context Protocol (MCP) Server via HTTP (SSE)

The application mounts a production-ready FastMCP server directly into the FastAPI application. This means when you deploy this project (e.g., via Docker), the MCP tools are exposed securely over HTTP using Server-Sent Events (SSE).

You **MUST** authenticate with your API Key to use the MCP Server.

#### 🤖 Cursor Integration
1. Open Cursor Settings -> Features -> MCP Servers.
2. Click **+ Add New MCP Server**.
3. Set **Type** to `sse`.
4. Set **Name** to `SmartEmailVerifier`.
5. Set **URL** to: `https://your-deployed-domain.com/mcp/sse?token=your_super_secret_api_key_here` (Replace with your actual domain and API Key).

#### 🤖 Claude Code & Claude Desktop Integration

Claude natively supports HTTP/SSE connections. You can add it directly via the Claude Code CLI:

```bash
claude mcp add-json EmailVerifier '{"type":"http","url":"https://your-deployed-domain.com/mcp/sse","headers":{"X-API-Key":"your_super_secret_api_key_here"}}'
```

Alternatively, you can manually add this to your configuration file (`.mcp.json` or `claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "EmailVerifier": {
      "type": "http",
      "url": "https://your-deployed-domain.com/mcp/sse",
      "headers": {
        "X-API-Key": "your_super_secret_api_key_here"
      }
    }
  }
}
```

The AI agent will communicate with your deployed server remotely over the web!

---

## ⚙️ How it Works

1. **Syntax Checking:** Quick regex validation to stop invalid emails immediately.
2. **MX Resolution:** Checks the DNS entries to extract the active Mail Exchange servers.
3. **Interactive SMTP Verification:** Uses the `EHLO`, `MAIL FROM`, and `RCPT TO` commands against the identified MX servers.
4. **Catch-All Testing:** If the server says "OK" to the target email, the system simulates a random, mathematically impossible email structure (`catchall_test_xyz@domain.com`). If the server *also* accepts that, we mark it as Catch-All.

## 🛡️ License

This project is licensed under the MIT License.
