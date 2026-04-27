# AI Control Plane Realistic Data Guide

This guide describes the most practical Docker-host setup for generating realistic
AI control-plane data in Preloop today.

## Goals

- Populate the merged dashboard with real flow, MCP, approval, and AI control-plane data
- Exercise runtime sessions, model gateway usage, and tool activity end-to-end
- Produce repeatable scenarios for healthy traffic, failures, budget pressure, and approvals

## Recommended Topology

Use a Docker-host setup first:

1. Run the main Preloop stack with Docker Compose
2. Run the example MCP server in a separate container
3. Add a gateway-enabled AI model
4. Create one container-agent flow that uses Preloop MCP plus explicit proxied tools
5. Trigger that flow repeatedly to generate traffic
6. Optionally mint a runtime-session token to also populate `/console/agents`

This path is currently more repeatable than trying to automate Claude Code or OpenClaw directly.

## Prerequisites

- Docker available on the host
- A valid Preloop API token exported as `PRELOOP_TOKEN`
- A provider API key for at least one AI model

Optional:

- `jq` for inspecting API responses
- A second terminal for monitoring the dashboard and runtime-session views live

## Step 1: Start Preloop

From the `preloop` submodule:

```bash
cd /Users/dimo/git/spacecode/preloop-ee/preloop
docker compose up
```

Reference:

- `preloop/README.md`

## Step 2: Start the Example MCP Server

Build and run the example MCP server:

```bash
cd /Users/dimo/git/spacecode/preloop-ee/preloop
docker build -t example-mcp-server -f scripts/examples/Dockerfile scripts/examples
docker run --rm -p 8001:8001 example-mcp-server
```

If Preloop itself is running in Docker, use `host.docker.internal` when configuring the MCP server URL.
If Preloop is running directly on the host, use `localhost`.

References:

- `preloop/scripts/examples/README.md`
- `preloop/scripts/examples/example_mcp_server.py`

## Step 3: Add the MCP Server to Preloop

```bash
curl -X POST http://localhost:8000/api/v1/mcp-servers \
  -H "Authorization: Bearer $PRELOOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example MCP Server",
    "url": "http://host.docker.internal:8001/mcp",
    "transport": "http-streaming",
    "auth_type": "none"
  }'
```

Expected evidence:

- `Overview` shows MCP server/tools state
- `/console/tools` lists the server and discovered tools

## Step 4: Add a Gateway-Enabled AI Model

Use pricing metadata so budget and spend surfaces move during testing:

```bash
curl -X POST http://localhost:8000/api/v1/ai-models \
  -H "Authorization: Bearer $PRELOOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Gateway GPT-5",
    "provider_name": "openai",
    "model_identifier": "gpt-5",
    "api_key": "YOUR_PROVIDER_KEY",
    "is_default": true,
    "meta_data": {
      "gateway": {
        "enabled": true,
        "model_alias": "openai/gpt-5",
        "provider_adapter": "preloop"
      },
      "pricing": {
        "input_price_per_1k": 0.01,
        "output_price_per_1k": 0.02
      }
    }
  }'
```

Expected evidence:

- `/console/ai-models` shows fleet traffic/spend signals
- `/console/ai-models/:id` shows model-specific sessions and captured interactions after traffic starts

## Step 5: Create a Managed Flow

Use a container agent such as `codex`. The critical part is letting the flow reach tools through Preloop MCP and explicitly allowing the proxied tools.

Example payload:

```json
{
  "name": "Docker MCP Control Plane",
  "description": "Control-plane realistic data scenario",
  "trigger_event_source": "manual",
  "trigger_event_type": "test",
  "prompt_template": "Verify refund eligibility for order ORD-123, refund it if eligible, then send a confirmation email.",
  "agent_type": "codex",
  "ai_model_id": "<AI_MODEL_ID>",
  "agent_config": {
    "model_gateway_budget": {
      "soft_limit_usd": 0.05,
      "monthly_usd_limit": 0.10
    }
  },
  "allowed_mcp_servers": ["preloop-mcp"],
  "allowed_mcp_tools": [
    {
      "server_name": "Example MCP Server",
      "tool_name": "verify_refund_eligibility"
    },
    {
      "server_name": "Example MCP Server",
      "tool_name": "refund_order"
    },
    {
      "server_name": "Example MCP Server",
      "tool_name": "send_email"
    }
  ],
  "is_enabled": true
}
```

You can create the flow via the console or with `POST /api/v1/flows`.

References:

- `preloop/backend/preloop/agents/container.py`
- `preloop/scripts/test_agent_api.py`

## Step 6: Trigger the Flow Repeatedly

Use the existing helper:

```bash
cd /Users/dimo/git/spacecode/preloop-ee/preloop
PRELOOP_TOKEN="$PRELOOP_TOKEN" python scripts/test_agent_api.py --agent-type codex --flow-id <FLOW_ID> --max-wait 600
```

Expected evidence:

- `Overview`: flow executions, AI summary cards, MCP card, approvals if triggered
- `/console/flows/executions/:id`: execution status and gateway events
- `/console/runtime-sessions`: sessions, interaction history, activity timeline
- `/console/ai-models`: fleet and model-detail traffic
- `/console/api-usage`: account-level gateway usage
- `/console/audit`: gateway and lifecycle audit events

## Optional Step 7: Populate `/console/agents`

Normal flow executions do not automatically create a durable managed-agent row in `/console/agents`.
To exercise the agent registry surfaces as well, mint a runtime-session token:

```bash
curl -X POST http://localhost:8000/api/v1/auth/runtime-sessions/token \
  -H "Authorization: Bearer $PRELOOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_source_type": "codex",
    "session_source_id": "docker-codex-01",
    "session_reference": "docker://codex-agent-01",
    "runtime_principal_name": "Docker Codex Agent 01",
    "allowed_mcp_servers": ["Example MCP Server"]
  }'
```

Expected evidence:

- `/console/agents` shows an enrolled agent
- `/console/agents/:id` links to the related runtime session and accumulated activity

## Scenario Matrix

### Healthy

- Example MCP server running
- Gateway-enabled model configured
- Flow budget high enough to succeed
- No approval required on the used tools

Expected evidence:

- Successful flow execution
- Runtime session activity
- Gateway usage summary
- Model/session spend and token counts

### Failing

- Stop the example MCP server after the flow and model are configured
- Trigger the flow again

Expected evidence:

- Failed flow execution
- Tool and/or gateway error evidence
- Dashboard failure card
- Audit exceptions

### Budget Pressure

- Keep the pricing metadata
- Set a very low soft and hard limit in the flow `model_gateway_budget`
- Re-run until soft then hard thresholds are crossed

Expected evidence:

- Budget health card moves from healthy to warning or denial
- Gateway usage shows spend pressure
- Audit contains `budget_denied` outcomes once the hard threshold is crossed

### Approval

- Configure approval on a high-risk tool such as `refund_order`, `pay`, or `rollback_deployment`
- Trigger the flow with a prompt that reaches that tool

Expected evidence:

- Pending approval card on the dashboard
- Approval request in `/console/approvals`
- Audit trail for request and resolution

## Caveats

- The example MCP server is intentionally simple and should be treated as test-only.
- The built-in managed/container flow is the best repeatable path today; it does not exactly mirror external desktop-client onboarding.
- If you specifically need the managed-agent registry to fill, use the runtime-session token path in addition to the flow path.
