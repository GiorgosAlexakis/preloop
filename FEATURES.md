# Preloop feature inventory

This inventory is organized around the platform components exposed in the
Preloop Console and public web UI. It was compiled from the routed Lit views in
`frontend/src/components/lit-app.ts`, the console shell navigation, and the
corresponding view files under `frontend/src/views`.

## Public site, auth, and self-service entry points

- UI pages explored:
  - `/`
  - `/pricing`
  - `/request-demo`
  - `/login`
  - `/register`
  - `/forgot-password`
  - `/reset-password`
  - `/verify-email`
  - `/delete-account`
  - `/welcome`
  - `/about`
  - `/whatis-mcp`
  - `/docs`
  - `/terms`
  - `/privacy`
  - `/ai-act-readiness`
  - `/vs/:slug`
  - `/resources/ai-agent-control-plane-2026`
- Product landing page for the open-source AI agent control plane, with
  marketing sections, feature slides, videos, CTAs, pricing links, and FAQs.
- Brand-aware SEO pages rendered through static content wrappers and markdown
  content for legal, comparison, resource, documentation, and MCP explainer
  pages.
- Account registration, login, password recovery, password reset, email
  verification, demo request, and account deletion flows.
- Feature-gated registration that can redirect to login when public sign-up is
  disabled.
- OAuth return handling that stores tokens from URL fragments and can continue
  first-run setup or billing checkout after authentication.
- Welcome page for new users after account creation or setup completion.

## Console shell and realtime operator workspace

- UI pages explored:
  - `/console`
  - Global console shell around every authenticated console route
- Authenticated application shell with sidebar navigation for Overview, Agents,
  Flows, Tools, Trackers, Models, Sessions, Cost, Approvals, Audit, and
  Settings.
- Feature-gated navigation for audit logs and account/team administration.
- Upgrade modal and global notice surfaces for plan limits and platform-wide
  messages.
- Console header with global notifications for running flow executions, pending
  approvals, and other operator events.
- Unified WebSocket connection for account-scoped realtime updates across
  flows, approvals, audit, gateway usage, runtime sessions, budget health, and
  managed agents.

## Dashboard and control-plane overview

- UI pages explored:
  - `/console`
- Operator overview that combines agent, flow, model, tool, approval, gateway,
  cost, session, tracker, and audit signals in one dashboard.
- Setup prompts and summary cards for onboarding agents, configuring tools,
  adding models, creating flows, and connecting trackers.
- Gateway usage summaries with token, request, and cost context.
- Active runtime/session and flow execution visibility for work currently in
  progress.
- Pending approval and recent audit event previews for operational triage.
- Budget and feature-flag awareness so enterprise or gated areas can be shown
  conditionally.

## Onboarding and Agent Control

- UI pages explored:
  - `/console/onboarding`
  - `/console/agents`
  - `/console/agents/:agentId`
- Guided setup for connecting existing agents, including CLI setup, OpenClaw
  plugin setup, and API gateway setup instructions.
- Managed agent inventory for OpenClaw, OpenCode, Claude Code, Codex CLI,
  Gemini CLI, Hermes, Cursor, Windsurf, flows, and MCP-compatible runtimes.
- Agent detail pages with runtime status, sessions, tools, models, associated
  flows, owner/tags, budgets, governance, and control surfaces.
- Agent Control command and Talk workflows for connected runtimes that support
  the Preloop runtime control channel.
- Provisioning/deployment surfaces for creating or connecting managed agent
  runtimes while keeping tool and model traffic governed by Preloop.

## Flows and event-driven automations

- UI pages explored:
  - `/console/flows`
  - `/console/flows/new`
  - `/console/flows/:flowId`
  - `/console/flows/executions`
  - `/console/flows/executions/:executionId`
- Flow list with user-created flows, presets, active executions, run actions,
  edit links, delete actions, and realtime execution updates.
- Flow creation and editing for tracker triggers, webhook triggers,
  organizations/projects, model selection, MCP servers/tools, managed agents,
  custom commands, git clone settings, iteration limits, budget limits, icons,
  and presets.
- Webhook URL generation and configuration for external systems that trigger
  flows.
- Execution list with status filtering, pagination, and live refresh.
- Execution detail with status, metrics, logs, live output, command sending,
  retry actions, trigger details, summaries, gateway event inspection, tool
  activity, and model/tool cost metadata.

## Tools, MCP firewall, governance, and policy workflows

- UI pages explored:
  - `/console/tools`
  - `/console/governance` redirecting to `/console/tools`
- Tool catalog for built-in tools, HTTP tools, and proxied tools from external
  MCP servers.
- MCP server management through add/edit forms, server cards, setup dialogs,
  scans, and availability status.
- Tool enable/disable controls, grouped list views, summary statistics,
  filtering, approval-workflow filters, and search.
- Access-rule editor for ordered allow, deny, and require-approval policies.
- Rule conditions through simple builders or CEL expressions.
- Human and AI approval workflow configuration, including justification
  requirements and workflow selection.
- Policy import/export as YAML plus policy diff and upload flows.
- Starter policy generation for quickly creating a governed baseline.

## Approvals and human review

- UI pages explored:
  - `/console/approvals`
  - `/console/approval/:requestId`
- Approval request inbox for pending and resolved tool-call decisions.
- Search and filters by status, tool, and other request metadata.
- Approval metrics including approval rate and response-time summaries.
- Approval detail page with tool information, arguments, agent reasoning,
  matched policy/workflow context, request metadata, webhook delivery details,
  approver comments, and decision controls.
- Realtime updates for new requests and resolved approvals.
- Header notification shortcuts for quickly approving or declining pending
  requests.

## Trackers and issue intelligence

- UI pages explored:
  - `/console/trackers`
  - `/console/trackers/:trackerId`
  - `/console/issues`
  - `/console/issues/duplicates`
  - `/console/issues/compliance`
  - `/console/issues/dependencies`
  - `/console/issues/assignments`
- Tracker list and add/edit flows for issue tracker integrations.
- GitHub installation callback handling and redirect recovery after tracker
  setup.
- Tracker detail with metadata, validation status, sync actions, scope rules,
  linked projects, and issue analytics entry points.
- Issue list and analytics surfaces for synced tracker data.
- Duplicate issue detection with AI verdicts, resolution workflow, project/org
  filters, status filters, resolution filters, and pagination.
- Compliance search and evaluation with prompt selection, results, and
  improvement suggestions.
- Dependency detection with scan expansion and workflows for committing issue
  dependency relationships.
- Assignment intelligence page scaffold for future issue assignment workflows.

## Runtime sessions and observability

- UI pages explored:
  - `/console/runtime-sessions`
- Session explorer with date, source, status, and text filters.
- Session list/detail views for managed agent sessions and flow-related runtime
  sessions.
- Summary metrics, model breakdowns, interaction history, activity timeline,
  gateway events, and session metadata.
- Operator action to end a session explicitly.
- Shared session observer component reused from agent, API key, and model detail
  contexts.

## AI model gateway, model management, and API usage

- UI pages explored:
  - `/console/ai-models`
  - `/console/ai-models/:modelId`
  - `/console/api-usage`
- AI model inventory with provider/model metadata, gateway aliases, status,
  usage summaries, and managed-agent associations.
- Model create/edit/delete workflows for configuring gateway-backed model
  access.
- Model detail with usage summary, runtime sessions, interaction search,
  validation prompt testing, gateway enablement, allowed subjects, budget
  policies, and session observer integration.
- API usage dashboard with gateway summary metrics for tokens, cost, requests,
  daily breakdowns, and raw interaction search.
- Breakdowns by model, flow, runtime session, API key, and other attribution
  dimensions.
- OpenAI-compatible and Anthropic-compatible gateway traffic surfaced through
  model and usage views.

## Cost analytics, budgets, and billing

- UI pages explored:
  - `/console/cost`
  - `/console/settings/account`
  - `/console/pricing`
- Cost overview with spend, token volume, request counts, projected cost, and
  previous-period comparisons.
- Spend breakdowns by model and recent runtime session activity.
- Budget policy summaries and budget-health cards for tracking limits and
  burn-rate risk.
- Enterprise-gated controls for budget policy editing and model price
  overrides.
- Account and billing summary with subscription sync, available plans, custom
  plans, checkout session creation, and billing portal access.
- In-console upgrade path for plan-limit states.

## Audit and compliance evidence

- UI pages explored:
  - `/console/audit`
- Audit timeline grouped by correlation ID so related tool, model, session,
  policy, and approval events can be reviewed together.
- Filters by event type, outcome, tool name, and date range.
- Realtime refresh for newly emitted governance and runtime events.
- Coverage for tool calls, gateway requests, runtime session lifecycle events,
  tool/rule/workflow/MCP/tracker/flow configuration changes, approvals, budget
  denials, and failures.
- Evidence surface for security review, incident investigation, and AI Act
  readiness workflows.

## Settings, account administration, and notifications

- UI pages explored:
  - `/console/settings`
  - `/console/settings/profile`
  - `/console/settings/security`
  - `/console/settings/api-keys`
  - `/console/settings/api-keys/:keyId`
  - `/console/settings/appearance`
  - `/console/settings/account`
  - `/console/settings/users`
  - `/console/settings/teams`
  - `/console/settings/invitations`
  - `/console/settings/notification-preferences`
- Profile page for user identity display and full-name updates.
- Security page for password changes.
- Appearance page for light, dark, and system theme preferences.
- Account page for organization name, billing summary, plan state, and
  subscription actions.
- API key list and detail pages for creating, deleting, expiring, and observing
  keys.
- API-key governance controls for scoped tool rules, allowed models, live
  activity, usage, budget policies, and per-key session observation.
- User management for feature-gated user CRUD and role assignment.
- Team management for feature-gated team CRUD, membership, and team roles.
- Invitation management with create/list/resend/cancel flows and pending,
  accepted, and all tabs.
- Notification preferences for email and mobile push channels.
- Mobile device registration with QR-code setup and device removal.

## OAuth and delegated authorization

- UI pages explored:
  - `/console/authorize`
- Consent page for delegated CLI or external-client authorization.
- Successful authorization flow that can return users to the agent inventory
  after CLI connection.
- Token and redirect handling that keeps authenticated console navigation in
  the same operator workspace.

## Legacy, imported, and external admin surfaces

- UI files explored:
  - `frontend/src/views/public/whatis-mcp-view.ts`
  - `frontend/src/views/authed/settings-view.ts`
  - `frontend/src/views/authed/policies-view.ts`
  - `frontend/vite.config.ts` `/admin` proxy
- Legacy MCP explainer view still exists, while the active `/whatis-mcp` route
  uses the static content wrapper.
- Legacy settings tab wrapper exists, while active settings routes render
  dedicated pages directly.
- Legacy policy management view exists, while active governance navigation is
  integrated into the Tools page.
- `/admin` is proxied by Vite to a separate admin target rather than being a Lit
  route in this frontend application.
