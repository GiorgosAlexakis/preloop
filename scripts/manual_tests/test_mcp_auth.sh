#!/bin/bash
# Test MCP authentication with your token

TOKEN="${1}"

if [ -z "$TOKEN" ]; then
    echo "Usage: ./test_mcp_auth.sh <your-token>"
    exit 1
fi

echo "Testing MCP endpoint with token..."
echo "Token (first 10 chars): ${TOKEN:0:10}..."
echo ""

# Test initialize with Authorization header
echo "=== Testing with Authorization header ==="
curl -v -X POST http://localhost:8000/mcp/v1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'

echo ""
echo ""

# Test with query parameter
echo "=== Testing with query parameter ==="
curl -v -X POST "http://localhost:8000/mcp/v1?token=$TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2024-11-05",
      "clientInfo": {
        "name": "test-client",
        "version": "1.0.0"
      }
    }
  }'
