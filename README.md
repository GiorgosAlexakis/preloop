# <img alt="Preloop Logo" src="frontend/public/assets/preloop-badge.png" style="height: 44px; margin-bottom: -14px" height="44px" /> Preloop - The Open-Source AI Agent Control Plane

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Preloop is the open-source AI agent control plane.** It unifies an **MCP firewall** for tool access, an **AI model gateway** for cost, safety and attribution, **policy-as-code** with **human approvals**, **runtime session observability**, and **audit trails** - in a single self-hostable platform.

Use Preloop to **onboard existing agents** with one command, and to **deploy event-driven agentic automations** with governed tools and budgets.

**Works with [OpenClaw](https://github.com/openclaw/openclaw), Claude Code, Codex CLI, Cursor, Gemini CLI, [OpenCode](https://github.com/sst/opencode), Windsurf, and any MCP-compatible agent or managed runtime.**

Run `preloop agents discover` and Preloop will find local agent configs, import representable MCP servers and model metadata, and transparently rewrite those agents to route tool calls through the **Preloop MCP Firewall** and model traffic through the **Preloop Gateway**. No SDK changes and no agent code changes required.


Build automations with templates like the [Pull Request Reviewer](./backend/presets/002-pull-request-reviewer.yaml), or write your own.

> **Official documentation:** Full guides and tutorials at [docs.preloop.ai](https://docs.preloop.ai).

```bash
# Install the standalone CLI
curl -fsSL https://preloop.ai/install/cli | sh
```

<a href="https://youtu.be/yTtXn8WibTY" target="_blank" title="Watch the video">
  <img alt="Preloop Video" src="frontend/public/assets/mcp-firewall.svg" style="width: 100%; max-width: 1135px;" />
</a>

## What is Preloop?

Preloop is a single open-source platform that covers the five jobs teams otherwise buy from four different vendors:

| Capability | What it does | Alternatives |
|---|---|---|
| **MCP Firewall** | Govern every tool call an agent makes. Allow, deny, require approval, require justification. YAML + CEL policies. | MintMCP, Lunar.dev MCPX, TrueFoundry MCP Gateway |
| **AI Model Gateway** | OpenAI- and Anthropic-compatible gateway with per-account/flow budgets, allowed-model lists, token accounting, and runtime attribution. | Portkey, Helicone, LiteLLM, Kong AI |
| **Human Approvals** | Mobile, watch, Slack, Mattermost, email, or webhook notifications with one-tap decisions and full context. Async-safe. | Custom Slack bots, Peta Desk |
| **Runtime Observability** | Session-level timeline of tool calls, model calls, policy decisions, approvals, spend, and outcomes across agents. | AgentOps, Langfuse, LangSmith |
| **Audit & AI Act Evidence** | Durable logs with matched policy, approver, inputs, timestamps, and outcome. Ready for security review and EU AI Act work. | Credo AI, IBM watsonx.governance |

All shipped as Apache 2.0 software that runs on your infrastructure.

## Why Preloop?

AI agents like Claude Code, Cursor, and OpenClaw are transforming how we work. But agents now deploy code, touch production data, change infrastructure, and spend money — and traditional IAM, prompt rules, and manual review were never built for that.

- **Accidental deletions.** One wrong command and your production database is gone.
- **Leaked secrets.** API keys pushed to public repos before anyone notices.
- **Runaway costs.** Agents spinning up expensive cloud resources without limits.
- **Breaking changes.** Untested deployments to production at 3am.

Most teams face an impossible choice: give AI full access and move fast (but dangerously), or lock everything down and lose the productivity gains.

**Preloop solves this.** Govern what agents are allowed to do, route risky actions to the right human, attribute model spend to the right team, and keep a searchable record of every important decision — without rebuilding your stack or instrumenting SDKs.

```text
AI Agent → Preloop → [Policy check] → Allow / Deny / Require Approval → Execute
                   → [Gateway]       → Budget + attribution             → Model
```

## Core Capabilities

### Managed Agent Onboarding (`preloop agents discover`)
One command discovers and enrolls existing local agents into your control plane.

```bash
preloop agents discover
```

Preloop inspects local configurations for **Claude Code**, **Codex CLI**, **Cursor**, **Gemini CLI**, **[OpenClaw](https://github.com/openclaw/openclaw)**, **[OpenCode](https://github.com/sst/opencode)**, and other MCP-compatible runtimes, imports representable MCP servers and model metadata into your account, mints a durable credential, backs up the existing config, and rewrites the local agent to use Preloop-managed endpoints. Legacy and current config locations are supported, JSON5 parsing included. No SDK. No agent code changes.

### Access Policies & Approval Workflows
Define fine-grained access controls for any AI tool or operation. Tools support multiple ordered access rules that evaluate in priority order. When an AI attempts a protected operation, Preloop pauses and notifies you:
- **Instant notifications** via mobile app, email, Slack, Mattermost, or custom webhook.
- **One-tap approvals** from your phone, watch, or desktop.
- **Async approval mode** lets the agent poll for status instead of blocking network hooks.
- **Per-tool justification** — require (or optionally request) the agent to explain *why* a tool is being called.
- **Full Audit Trail** — every action is logged with full context: what was attempted, the matched policy, execution duration, and who approved it.

<div align="center">
  <video src="https://docs.preloop.ai/assets/animations/quickstart/access_rules.mp4" controls autoplay loop muted style="max-height: 480px; width: auto; max-width: 100%; border-radius: 8px; margin-right:10px;"></video>
  <video src="https://docs.preloop.ai/assets/animations/quickstart/mobile_approval.mp4" controls autoplay loop muted style="max-height: 480px; width: auto; max-width: 100%; border-radius: 8px; margin-left:10px;"></video>
</div>

### Policy-as-Code
Define policies in YAML and manage via CLI or API to version-control your safeguards alongside your infrastructure:

```yaml
# Example: Require approval for production deployments
version: "1.0"
metadata:
  name: "Production Safeguards"
  description: "Require approval before deploying"

approval_workflows:
  - name: "deploy-approval"
    timeout_seconds: 600
    required_approvals: 1
    async_approval: true

tools:
  - name: "bash"
    source: mcp
    approval_workflow: "deploy-approval"
    justification: required
    conditions:
      - expression: "args.command.contains('deploy') && args.command.contains('production')"
        action: require_approval
```

### AI Model Gateway
Preloop safely routes model traffic on behalf of managed runtimes instead of handing provider credentials to potentially vulnerable agent containers.
- **OpenAI-compatible** (`/openai/v1/models`, `/openai/v1/chat/completions`, `/openai/v1/responses`) and **Anthropic-compatible** (`/anthropic/v1/messages`) endpoints with SSE streaming.
- **Budget enforcement** at account, flow, and subject scopes using configurable cost tracking limits.
- **Allowed-model lists** per account, flow, API key, or managed agent.
- **Usage accounting** persisted as a canonical `ApiUsage` ledger — token usage, estimated cost, runtime-principal attribution, and provider-neutral conversation previews.
- **Secret custody** — provider API keys stay with Preloop; runtimes receive short-lived gateway tokens instead of raw credentials.

### Runtime Session Observability
A durable `RuntimeSession` layer gives you one timeline per managed runtime — flow executions today, and any onboarded CLI/desktop agent session going forward. Operator-scoped endpoints expose recent sessions plus captured gateway interactions so the console can drill from aggregate usage into a single session timeline. Operators can end a session explicitly; doing so updates runtime state, emits audit events, and refreshes managed-agent summaries.




## Getting Started

Install Preloop agents and components locally using our provisioning scripts.

```bash
# Install the standalone CLI
curl -fsSL https://preloop.ai/install/cli | sh

# Install the OSS platform stack
curl -fsSL https://preloop.ai/install/oss | sh
```

For extended details detailing comprehensive Docker builds, Kubernetes Helm topologies, GraphQL configuration, WebSocket streaming channels, and deep `.env` definitions, refer to the [Preloop Documentation Hub](https://docs.preloop.ai).

## The Open-Source Alternative to AWS Bedrock AgentCore

Preloop covers the same core jobs as AWS Bedrock AgentCore (runtime, gateway, identity, observability, policy) but is open source, self-hostable, MCP-native, and vendor-neutral. Many teams adopt Preloop specifically as an **open-source alternative to AWS Bedrock AgentCore** when they want to avoid hyperscaler lock-in or need to run governance inside their own VPC or on-prem.

| Feature | Preloop | AWS Bedrock AgentCore |
|---------|:-------:|:--------------:|
| Open source (Apache 2.0) | ✅ | ❌ |
| Self-hostable (VPC / on-prem) | ✅ | ❌ |
| Policy-as-code (YAML + CEL) | ✅ | Limited |
| MCP-native tool governance | ✅ | Partial |
| Model gateway with budgets & attribution | ✅ | ✅ |
| Human-in-the-loop approval workflows | ✅ (mobile, Slack, webhook) | Limited |
| Works with any agent runtime | ✅ | AWS-centric |
| Vendor lock-in | None | AWS |
| Onboard existing local agents with one command | ✅ (`preloop agents discover`) | ❌ |

## How Preloop Compares to Other Categories

| Category | Common tools | How Preloop differs |
|---|---|---|
| **AI gateways / LLM proxies** | Portkey, Helicone, LiteLLM, Kong AI | Preloop's gateway is bundled with an MCP firewall, approval workflows, and runtime observability — you do not need to stitch four products together. |
| **MCP gateways** | MintMCP, Lunar.dev MCPX, TrueFoundry | Preloop is open-source and includes a first-class AI model gateway, not just MCP tool routing. |
| **AgentOps / observability** | Langfuse, LangSmith, Braintrust, AgentOps.ai | Preloop adds runtime *enforcement* (policy, approvals, budgets), not just tracing. |
| **AI runtime security** | Lakera, Lasso, Zenity, Noma | Preloop is developer-facing, MCP-native, and self-hostable. Complementary to semantic content-safety firewalls. |
| **AI governance suites** | Credo AI, IBM watsonx, OneTrust | Preloop focuses on runtime controls agents actually hit, not just top-down inventory and risk artifacts. |

## Enterprise Features

Preloop Enterprise Edition extends the core open-source components with centralized RBAC capabilities:

| Feature | Open Source | Enterprise |
|---------|:-----------:|:----------:|
| Basic approval workflows | ✅ | ✅ |
| Issue tracker integrations | ✅ | ✅ |
| Agentic flows & Vector search | ✅ | ✅ |
| **Role-Based Access Control (RBAC)** | ❌ | ✅ |
| **Team management & Admin Dashboard** | ❌ | ✅ |
| **CEL conditional approval workflows** | ❌ | ✅ |
| **AI-driven approval logic** | ❌ | ✅ |
| **Team-based approvals with quorum** | ❌ | ✅ |
| **Approval escalation** | ❌ | ✅ |

Contact sales@preloop.ai for Enterprise Edition licensing requests.

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

## License

Preloop is open source software licensed under the [Apache License 2.0](LICENSE).
Copyright (c) 2026 Spacecode AI Inc.
