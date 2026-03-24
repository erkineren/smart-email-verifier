---
name: Email Verification Tool
description: Comprehensive guide for AI Agents on how to use, configure, and connect to the Email Verification Tool (via API or MCP).
---

# 🤖 AI Agent Integration Guide (SKILL)

This document is intended for AI Agents (like yourself) or Developers to understand how to interact with this project. This project is a production-ready Email Verification System that bypassing SMTP tarpits, detects Catch-All servers, and performs regex/MX validation.

There are **two ways** an AI Agent can use this tool:

## 1. Using the REST API (FastAPI)
If the project is running as a Docker container, it serves a FastAPI application.
- **Endpoint:** `GET /verify/{email}`
- **Authentication:** Requires `X-API-Key` header.
- **Example Usage (curl):**
  ```bash
  curl -X 'GET' 'http://localhost:8000/verify/info@example.com' -H 'X-API-Key: YOUR_API_KEY'
  ```

## 2. Using Model Context Protocol (MCP) - Recommended
To natively connect this repo to an AI Agent (like Claude Desktop or Cursor) as a Tool, you can use the configured MCP Server (`mcp_server.py`).

### Installation for Agents
The MCP server uses standard Input/Output (STDIO) to communicate.
Simply add the following to your AI Agent's configuration file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "smart-email-verifier": {
      "command": "python",
      "args": [
        "/absolute/path/to/smart-email-verifier/mcp_server.py"
      ],
      "env": {
        "HELO_HOST": "mail.iotinks.com",
        "MAIL_FROM": "verify@iotinks.com",
        "SMTP_TIMEOUT": "15"
      }
    }
  }
}
```

Once configured, the AI Agent will automatically have access to the `verify_email` tool. When an end-user asks "Is info@example.com a real email?", the Agent will call this local script, await the JSON response, and provide a conclusive human-readable answer.

### MCP Tool Specifications
- **Tool Name:** `verify_email`
- **Arguments:** `email` (string)
- **Returns:** JSON object containing `is_deliverable` (bool), `is_catch_all` (bool), `smtp_code` (int), and verbose errors if any.
