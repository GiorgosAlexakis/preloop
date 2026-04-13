# <img alt="Preloop Logo" src="frontend/public/assets/preloop-badge.png" style="height: 21px;" height="18px" /> Preloop: AI Safety, Control, and Observability for AI Agents

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

Preloop is a safety and control platform for teams deploying AI agents into real workflows. It gives you policy enforcement, human approvals, observability, budget controls, and audit trails across both tool use and model traffic.

Use Preloop to **onboard existing agents** and to **deploy event-driven agentic automations**.

**Works with OpenClaw, OpenCode, Claude Code, Codex CLI, Gemini CLI, Cursor, and any MCP-compatible agent or managed runtime.**

Once an agent is onboarded it routes prompts through the Preloop Gateway and tool calls through the Preloop MCP firewall.

Deploy automations using the built-in flow templates like the [Pull Request Reviewer](./backend/presets/002-pull-request-reviewer.yaml) or create your own.

> **Read the official documentation:** Full guides and tutorials are available at [docs.preloop.ai](https://docs.preloop.ai).

<a href="https://youtu.be/yTtXn8WibTY" target="_blank" title="Watch the video">
  <img alt="Preloop Video" src="frontend/public/assets/mcp-firewall.svg" style="width: 100%; max-width: 1135px;" />
</a>

## Why Preloop?

AI agents like Claude Code, Cursor, and OpenClaw are transforming how we work. But with great power comes great risk:

- **Accidental deletions.** One wrong command and your production database is gone.
- **Leaked secrets.** API keys pushed to public repos before anyone notices.
- **Runaway costs.** Agents spinning up expensive resources without limits.
- **Breaking changes.** Untested deployments to production at 3am.

Most teams face an impossible choice: give AI full access and move fast (but dangerously), or lock everything down and lose the productivity gains.

**Preloop solves this.** You can govern what agents are allowed to do, route risky actions to the right human workflow, track every important decision, and keep model usage and spend visible in one place. You stay in control while AI handles the routine work.

```text
AI Agent -> Preloop -> [Policy check] -> Allow / Deny / Require Approval -> Execute
```

## Core Capabilities

### Access Policies & Approval Workflows
Define fine-grained access controls for any AI tool or operation. Tools support multiple ordered access rules that evaluate in priority order. When an AI attempts a protected operation, Preloop pauses and notifies you:
- **Instant notifications** via mobile app, email, Slack, or Mattermost.
- **One-tap approvals** from your phone, watch, or desktop.
- **Async approval mode** allows the agent to poll for status instead of blocking network hooks.
- **Full Audit Trail:** Every action is logged with full context: what was attempted, the matched policy, execution duration, and who approved it.

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
- Exposes OpenAI-compatible and Anthropic-compatible endpoints with SSE streaming.
- Account-level and flow-level budget enforcement using configurable cost tracking limits.
- Usage persistence for detailed telemetry, letting operators see which projects or flows cost what over time.

### Managed Agent Onboarding
Discover and securely enroll existing local agents into your control plane effortlessly using native CLI tools (`preloop agents discover`). Connect **OpenClaw**, **OpenCode**, **Claude Code**, **Codex CLI**, or **Gemini CLI**. Preloop will map the agent's MCP interfaces to your account and transparently bind their execution constraints into your unified approval interface.

## Getting Started

Install Preloop agents and components locally using our provisioning scripts.

```bash
# Install the standalone CLI
curl -fsSL https://preloop.ai/install/cli | sh

# Install the OSS platform stack
curl -fsSL https://preloop.ai/install/oss | sh
```

For extended details detailing comprehensive Docker builds, Kubernetes Helm topologies, GraphQL configuration, WebSocket streaming channels, and deep `.env` definitions, refer to the [Preloop Documentation Hub](https://docs.preloop.ai).

## Comparison: AWS Agent Core

| Feature | Preloop | AWS Agent Core |
|---------|:-------:|:--------------:|
| Open source | ✅ | ❌ |
| Self-hosted option | ✅ | ❌ |
| Policy-as-code (YAML) | ✅ | Limited |
| MCP native | ✅ | ❌ |
| Works with any agent | ✅ | AWS-focused |

**Preloop is the open-source alternative to AWS Agent Core** for teams who want vendor-neutral, self-hosted AI governance.

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
| **Audit impersonation tracking** | ❌ | ✅ |

Contact sales@preloop.ai for Enterprise Edition licensing requests.

## Contributing

Contributions are welcome! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details on how to get started.

## License

Preloop is open source software licensed under the [Apache License 2.0](LICENSE).
Copyright (c) 2026 Spacecode AI Inc.
