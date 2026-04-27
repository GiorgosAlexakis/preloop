# Claude Code Anthropic Gateway Smoke Test

This is a manual host-based smoke test for validating the currently delivered Anthropic-compatible gateway path and the surrounding control-plane visibility.

It is intentionally a smoke test, not a claim of fully automated Claude Code compatibility.

## Goals

- Verify that Preloop's `POST /anthropic/v1/messages` ingress is reachable with realistic headers
- Exercise runtime-session token onboarding for a Claude Code style client identity
- Confirm that the resulting traffic appears in the dashboard, AI model views, runtime sessions, and audit

## Current Constraints

- This path is best run manually on a host, not as a fully automated containerized review
- The repo currently has stronger repeatable support for managed/containerized agents than for desktop-style Claude Code automation
- Treat this as a compatibility and UX smoke test, not the primary realistic-data generator

## Prerequisites

- Preloop running locally
- A gateway-enabled Anthropic model configured
- A valid user token exported as `PRELOOP_TOKEN`
- Claude Code available on the host if you want the true client smoke test

## Step 1: Mint a Runtime Session Token

Create a token that identifies the client as a Claude Code runtime:

```bash
curl -X POST http://localhost:8000/api/v1/auth/runtime-sessions/token \
  -H "Authorization: Bearer $PRELOOP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_source_type": "claude_code",
    "session_source_id": "claude-code-workspace-01",
    "session_reference": "/path/to/workspace",
    "runtime_principal_id": "claude-code-principal-01",
    "runtime_principal_name": "Claude Code Workspace 01",
    "expires_in_minutes": 120,
    "allowed_mcp_servers": ["Example MCP Server"]
  }'
```

Save the returned `token` and `runtime_session_id`.

Expected evidence:

- `/console/agents` shows a new managed agent
- `/console/runtime-sessions` shows a new runtime session

## Step 2: Validate the Anthropic Gateway with Curl First

Before involving Claude Code, confirm the endpoint works directly:

```bash
curl -X POST http://localhost:8000/anthropic/v1/messages \
  -H "x-api-key: <RUNTIME_SESSION_TOKEN>" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "anthropic/claude-sonnet-4-5",
    "messages": [{"role": "user", "content": "Summarize deployment risk in one sentence."}],
    "max_tokens": 256
  }'
```

What this validates:

- `x-api-key` is accepted as the gateway token
- `anthropic-version` is required
- model gateway usage is attributed through the runtime session

Expected evidence:

- `/console/ai-models` shows Anthropic traffic
- `/console/runtime-sessions?sessionId=<runtime_session_id>` shows a new interaction
- `/console/audit` contains the gateway request

## Step 3: Manual Claude Code Pointing

For the manual smoke test, point Claude Code at Preloop's Anthropic-compatible gateway:

- Base URL: `http://localhost:8000/anthropic`
- API key: the runtime-session token created above
- Required header behavior: Claude Code must send `anthropic-version`

Use the closest available Claude Code configuration mechanism for custom Anthropic routing in your local environment.

Success criteria:

- Claude Code can complete at least one simple prompt through Preloop
- The request lands in the same runtime session or managed-agent identity you minted
- The operator can trace the traffic from dashboard -> AI model detail -> runtime session -> audit

## Step 4: Review UX and Evidence

After one successful and one intentionally bad prompt, review:

- `Overview`: does the home page surface the traffic and any exceptions clearly?
- `/console/ai-models`: does the model list and detail make the Anthropic traffic easy to find?
- `/console/runtime-sessions`: can you find the session quickly and understand what happened?
- `/console/agents`: does the managed-agent record feel clearly tied to the runtime session?
- `/console/audit`: can you trace the model request and any operator-relevant failures?

## Suggested Negative Checks

### Missing Anthropic Version Header

Omit `anthropic-version` in the curl request.

Expected result:

- HTTP `400`
- Anthropic-style error envelope

### Invalid Token

Use a bad token in `x-api-key`.

Expected result:

- HTTP `401`
- Authentication error

### Budget Denial

Use a very low model or account gateway budget and retry.

Expected result:

- HTTP `403`
- `budget_denied` style evidence in audit/control-plane surfaces

## What This Test Does Not Yet Prove

- Full Claude Code streaming/event compatibility across all interaction types
- Full automation suitability for Kubernetes or CI
- A polished operator enrollment workflow inside the console

For repeatable realistic data, prefer the managed/containerized flow path in:

- `preloop/scripts/manual_tests/ai-control-plane-realistic-data.md`
