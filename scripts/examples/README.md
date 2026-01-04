# Preloop Examples

This directory contains example code for working with Preloop.

## Example MCP Server

`example_mcp_server.py` is a simple MCP server built with FastMCP that provides several example tools for testing external MCP server integration and approval policies.

### Available Tools

- **add**: Add two numbers together
- **multiply**: Multiply two numbers
- **random_number**: Generate a random number within a range

### Running the Server

#### Local Development

```bash
# Install FastMCP if not already installed
pip install fastmcp

# Run the server (with default bearer token)
python scripts/examples/example_mcp_server.py

# Or with custom bearer token
export BEARER_TOKEN=my-secret-token
python scripts/examples/example_mcp_server.py
```

The server will start on `http://localhost:8001` with bearer token authentication enabled.

#### Docker Deployment

```bash
# Build the image
docker build -t example-mcp-server -f scripts/examples/Dockerfile scripts/examples

# Run the container
docker run -p 8001:8001 -e BEARER_TOKEN=my-secret-token example-mcp-server
```

#### Kubernetes Deployment via GitLab CI

The example MCP server can be deployed to the Kubernetes cluster via GitLab CI:

1. **Build the image**: Run the manual job `build:example-mcp-server` in your GitLab pipeline
   - Builds Docker image using Kaniko
   - Pushes to `$CI_REGISTRY_IMAGE/example-mcp-server:$CI_COMMIT_SHA`

2. **Deploy to Kubernetes**: After build completes, run the manual job `deploy:example-mcp-server`
   - Deploys to namespace `example-mcp-servers`
   - Creates deployment at URL: `https://$CI_COMMIT_REF_NAME.example-mcp.preloop.ai`
   - Environment auto-stops after 4 hours
   - Bearer token configured via `EXAMPLE_MCP_BEARER_TOKEN` CI variable (defaults to `test-token-12345`)

3. **Cleanup**: Environment stops automatically after 4 hours, or run manual job `stop-example-mcp-server`

See `.gitlab-ci.yml` for job definitions and `helm/example-mcp-server/` for Helm chart details.

### Adding to Preloop

Once the server is running (locally, via Docker, or on Kubernetes), add it to Preloop:

#### Via API

```bash
# For local development
curl -X POST https://preloop.ai/api/v1/mcp-servers \
  -H "Authorization: Bearer YOUR_PRELOOP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example MCP Server",
    "base_url": "http://localhost:8001",
    "auth_type": "bearer",
    "auth_config": {
      "token": "test-token-12345"
    }
  }'

# For deployed environment
curl -X POST https://preloop.ai/api/v1/mcp-servers \
  -H "Authorization: Bearer YOUR_PRELOOP_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example MCP Server",
    "base_url": "https://YOUR_BRANCH.example-mcp.preloop.ai",
    "auth_type": "bearer",
    "auth_config": {
      "token": "test-token-12345"
    }
  }'
```

#### Via Preloop UI

1. Navigate to Settings > MCP Servers
2. Click "Add MCP Server"
3. Fill in:
   - **Name**: Example MCP Server
   - **Base URL**:
     - Local: `http://localhost:8001`
     - Docker: `http://host.docker.internal:8001`
     - Kubernetes: `https://YOUR_BRANCH.example-mcp.preloop.ai`
   - **Auth Type**: Bearer Token
   - **Token**: `test-token-12345` (or your custom token)
4. Click "Save"
5. Server will be scanned automatically for available tools

### Testing Approval Policies

The example server is designed to test approval policies in flows:

#### Create Approval Policy

1. In Preloop, create an approval policy for the `add` tool:
```json
{
  "tool_name": "add",
  "mcp_server_name": "Example MCP Server",
  "approval_required": true,
  "approvers": ["user@example.com"]
}
```

2. Test the policy by calling the `add` tool through Preloop in a flow
3. The request should be pending approval
4. Approve it via the UI or API
5. The tool should execute and return the result

#### Test Different Scenarios

- **No approval required**: Test with `random_number` tool (if not in policy)
- **Multiple approvers**: Add multiple approvers to policy
- **Conditional approval**: Test with different argument values
- **Approval timeout**: Set timeout and let it expire

### Authentication

The example server requires bearer token authentication for all endpoints except `/health`:

```bash
# Health check (no auth required)
curl https://YOUR_BRANCH.example-mcp.preloop.ai/health

# MCP endpoints (auth required)
curl -H "Authorization: Bearer test-token-12345" \
  https://YOUR_BRANCH.example-mcp.preloop.ai/

# Will return 401 without proper token
curl https://YOUR_BRANCH.example-mcp.preloop.ai/
```

### Troubleshooting

#### Server not responding

1. Check health endpoint:
```bash
curl https://YOUR_BRANCH.example-mcp.preloop.ai/health
```

2. Check pod logs (Kubernetes):
```bash
kubectl logs -n example-mcp-servers deployment/YOUR_BRANCH-example-mcp -f
```

3. Check pod status:
```bash
kubectl get pods -n example-mcp-servers
```

#### Authentication errors

1. Verify bearer token is correct
2. Check if token was set correctly in deployment:
```bash
kubectl get deployment YOUR_BRANCH-example-mcp \
  -n example-mcp-servers \
  -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name=="BEARER_TOKEN")].value}'
```

#### TLS certificate issues

The ingress uses cert-manager with letsencrypt-prod. If certificates aren't working:

1. Check certificate status:
```bash
kubectl get certificate -n example-mcp-servers
```

2. Check cert-manager logs:
```bash
kubectl logs -n cert-manager deployment/cert-manager
```

### Architecture

```
┌─────────────────┐
│   GitLab CI     │
│   Pipeline      │
└────────┬────────┘
         │
         │ Build & Deploy
         ▼
┌─────────────────┐
│   Kubernetes    │
│    Cluster      │
├─────────────────┤
│  Ingress (TLS)  │◄────── https://branch.example-mcp.preloop.ai
├─────────────────┤
│    Service      │
│   (ClusterIP)   │
├─────────────────┤
│   Deployment    │
│  (1 replica)    │
│                 │
│  example_mcp_   │
│   server.py     │
│  (FastMCP +     │
│   Bearer Auth)  │
└─────────────────┘
```

### Security Notes

- The default bearer token `test-token-12345` is **NOT secure** and should only be used for testing
- Always set `EXAMPLE_MCP_BEARER_TOKEN` in GitLab CI variables for production-like testing
- The server is intended for testing only, not production use
- Bearer token is passed in plain text - always use HTTPS
- Auto-stop after 4 hours prevents long-running test environments
