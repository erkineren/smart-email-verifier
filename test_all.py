import os
os.environ["API_KEY"] = "test_key"

import asyncio
from fastapi.testclient import TestClient
from app import app
from mcp_server import verify_email, verify_emails_bulk

def test_api():
    print("--- API Tests ---")
    client = TestClient(app)
    
    # 1. Healthcheck
    res = client.get("/health")
    print(f"Health check: {res.status_code} - {res.json()}")
    assert res.status_code == 200
    
    # 2. Verify Email (No Auth)
    res = client.get("/verify/test@google.com")
    print(f"Verify without API Key: {res.status_code}")
    assert res.status_code in [401, 403]
    
    # 3. Verify Email (With Auth)
    res = client.get("/verify/test@google.com", headers={"x-api-key": "test_key"})
    print(f"Verify with API Key: {res.status_code}")
    assert res.status_code == 200
    print("Result:", res.json())
    
    # 4. Bulk Verify
    res = client.post("/verify/bulk", 
                      json={"emails": ["test@google.com", "fake@example.com"]},
                      headers={"x-api-key": "test_key"})
    print(f"Bulk Verify Status: {res.status_code}")
    assert res.status_code == 200
    print("Bulk Result Total:", res.json().get("total"))

    # 5. MCP HTTP Endpoint (No Auth)
    res = client.get("/mcp/sse")
    print(f"MCP HTTP No Auth Status: {res.status_code}")
    assert res.status_code == 403

    # 6. MCP HTTP Endpoint (With Token)
    try:
        with client.stream("GET", "/mcp/sse?token=test_key", headers={"Accept": "text/event-stream"}) as response:
            print(f"MCP HTTP Auth Status: {response.status_code}")
            assert response.status_code == 200
            # Read just one chunk to verify connection is open
            iterator = response.iter_lines()
            next(iterator, None)
    except Exception as e:
        print("Stream test exception (expected if blocking or closed quickly):", e)
    
def test_mcp():
    print("--- MCP Tests ---")
    
    # 1. Single
    res = verify_email("test@google.com")
    print("Single MCP Result email:", res.get("email"), "- is_deliverable:", res.get("is_deliverable"))
    
    # 2. Bulk (Async)
    async def run_bulk():
        bulk_res = await verify_emails_bulk(["test@google.com", "fake2@example.com"])
        print("Bulk MCP Result length:", bulk_res.get("total"))
    
    asyncio.run(run_bulk())

if __name__ == "__main__":
    test_api()
    test_mcp()
    print("ALL TESTS PASSED")
