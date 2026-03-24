import os
from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from dotenv import load_dotenv
from typing import Dict, Any, List
from pydantic import BaseModel
import asyncio

from main import SmartEmailVerifier

from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# --- MCP App (must be created before FastAPI to pass lifespan) ---
from mcp_server import mcp
mcp_app = mcp.streamable_http_app()

app = FastAPI(
    title="Smart Email Verifier API",
    description="A smart email verification system with Catch-All detection and anti-tarpit capabilities.",
    version="1.0.0",
    lifespan=mcp_app.router.lifespan_context,
)

# --- Security: API Key Check ---
API_KEY = os.getenv("API_KEY", "your_super_secret_api_key_here")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key (Check X-API-Key Header)"
        )
    return api_key

# --- Initialize Email Verifier ---
verifier = SmartEmailVerifier()

@app.get("/verify/{email}", response_model=Dict[str, Any])
def verify_email_api(email: str, api_key: str = Depends(get_api_key)):
    """
    Performs Smart SMTP Verification for the given email address.
    """
    try:
        result = verifier.verify(email)
        from dataclasses import asdict
        return asdict(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BulkVerifyRequest(BaseModel):
    emails: List[str]

@app.post("/verify/bulk", response_model=Dict[str, Any])
async def verify_email_bulk(request: BulkVerifyRequest, api_key: str = Depends(get_api_key)):
    """
    Verifies a list of emails concurrently.
    Uses a maximum of 10 concurrent connections to prevent IP rate-limiting or blocking.
    """
    # Use a Semaphore to limit the maximum number of concurrent threads to 10
    semaphore = asyncio.Semaphore(10)

    async def verify_with_semaphore(email: str):
        async with semaphore:
            # asyncio.to_thread runs the synchronous verifier logic in a thread pool
            # so it doesn't block the main FastAPI async loop
            return await asyncio.to_thread(verifier.verify, email)

    # Launch all tasks concurrently
    tasks = [verify_with_semaphore(email) for email in request.emails]
    
    # Wait for all thread pool tasks to complete
    completed_verifications = await asyncio.gather(*tasks, return_exceptions=True)
    
    results = []
    from dataclasses import asdict
    
    for i, res in enumerate(completed_verifications):
        if isinstance(res, Exception):
            results.append({"email": request.emails[i], "error": str(res)})
        else:
            results.append(asdict(res))
            
    return {"total": len(results), "results": results}

@app.get("/health")
def health_check():
    """
    For container and load balancer health checks.
    """
    return {"status": "ok", "message": "Email Verifier API is running."}

# --- MCP Server Integration ---
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

class MCPAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            # Check X-API-Key header, Authorization header, or token query param
            auth_header = request.headers.get("X-API-Key") or request.headers.get("Authorization")
            query_token = request.query_params.get("token")
            
            token = auth_header.replace("Bearer ", "") if auth_header and auth_header.startswith("Bearer ") else auth_header
            token = token or query_token
            
            if token != API_KEY:
                return JSONResponse(status_code=403, content={"detail": "Invalid API Key for MCP Server"})
        return await call_next(request)

app.add_middleware(MCPAuthMiddleware)
app.mount("/mcp", mcp_app)
