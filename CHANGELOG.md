# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.9.0-rc.1] - 2026-04-14

## [0.9.0-rc.0] - 2026-04-13

### Added

- **Managed agent enrollment lifecycle**: Added durable enrollment validate/restore control-plane actions plus richer enrollment snapshots so CLI-driven onboarding can persist apply, validation, and rollback state per managed agent.
- **CLI agent enrollment workflow**: `preloop agents discover` is now inventory-first while `preloop agents enroll`, `status`, and `restore` handle backup-aware local MCP rewiring, durable credential bootstrap, and restore reporting for supported desktop/CLI agents.
- **OpenClaw managed enrollment adapter**: OpenClaw onboarding now uses an explicit adapter for `mcp.servers.preloop` config writes and validation, matching the documented `transport: "http"` plus bearer-header integration shape.
- **Subject-scoped governance**: Managed-agent and API-key subjects can now carry their own `allowed_models`, tool rules, and tool enable/disable overrides, with API-key scope taking precedence over the enrolled agent when both are present.
- **CLI release version reporting**: The `preloop version` command now reports the same release version as the rest of the shipped components by default instead of falling back to `dev` in local builds.
- **Responsive console sidebar**: Sidebar is now fully responsive with distinct behavior per breakpoint. On large screens (≥768px): sidebar is visible by default and stays visible while working in the main panel; hamburger toggle hides or shows it. On small screens: overlay behavior with backdrop; hamburger opens/closes the slide-in menu. Removed collapsed icon-only state in favor of fully visible or fully hidden.
- **AI Model Gateway foundations**: Flow executions now resolve models through explicit runtime transport settings and can hand gateway-enabled agents a Preloop gateway URL, short-lived bearer token, model alias, and provider adapter instead of raw provider credentials.
- **Preloop OpenAI-compatible gateway**: Added `/openai/v1/models`, `/openai/v1/chat/completions`, and `/openai/v1/responses` backed by LiteLLM, with bearer-token auth that preserves runtime API key context for attribution.
- **Anthropic-compatible gateway ingress**: Added `POST /anthropic/v1/messages` so Anthropic-format clients can route through the same Preloop gateway control plane, including a first-pass text-only streaming/SSE path.
- **Gateway streaming support**: Added SSE streaming support for `/openai/v1/chat/completions` and `/openai/v1/responses` so OpenAI-compatible clients can use streamed model output through the Preloop gateway.
- **Gateway usage ledger**: Model gateway requests are now recorded in `api_usage` with account, API key, flow, flow execution, model alias, provider, token usage, estimated cost, and runtime principal attribution.
- **Gateway budget controls**: Added preflight account-level and flow-level model gateway budget checks with soft-limit annotations and hard-limit denials.
- **Gateway reporting endpoints**: Added `GET /api/v1/account/gateway-usage/summary` and `GET /api/v1/flows/{flow_id}/gateway-usage/summary` to expose spend and token summaries from the gateway usage ledger.
- **Provider-agnostic secret references**: Added `SecretReference` plus a `SecretService` abstraction for AI model credentials, with a built-in `local_encrypted` backend.
- **Gateway runtime events**: Added normalized `model_gateway_call` execution events with redaction-aware request/response payload capture and flow execution log persistence.
- **Gateway event endpoint**: Added `GET /api/v1/flows/executions/{execution_id}/gateway-events` for execution-scoped inspection of normalized model gateway events.
- **Gateway events UI**: Flow execution detail now includes a dedicated Gateway Events tab that renders normalized model-call events, key spend/token metadata, and sanitized payload previews.
- **Gateway usage summaries UI**: The API usage page now renders real account-level gateway usage summaries with date filtering, budget state, and model/flow activity breakdowns.
- **Gateway session explorer UI**: The API usage page now includes a session/execution-oriented view so operators can inspect which flow executions and agent sessions have been using AI models.
- **AI model observability views**: AI model settings now expose per-model usage summaries, runtime-session drill-downs, and searchable captured interactions so operators can inspect one configured model in detail.
- **AI model fleet overview**: The AI model list now doubles as a fleet overview with 30-day spend, traffic, failure, and active-session signals for each configured model.
- **Gateway conversation previews**: `model_gateway_call` events now include a provider-neutral conversation preview plus capture-policy metadata describing redaction/truncation state.
- **Gateway search corpus foundation**: Added a dedicated `GatewayUsageSearchDocument` corpus keyed to `ApiUsage`, with normalized searchable text, content hashing, and a placeholder vector column for future semantic indexing.
- **Opt-in gateway interaction indexing**: Successful gateway requests, and failed requests when separately enabled, can now be automatically indexed into the `GatewayUsageSearchDocument` corpus. When content capture is disabled, indexing stays metadata-only.
- **Runtime session identity foundation**: Added a new `RuntimeSession` layer and `ApiUsage.runtime_session_id` so session browsing/search can evolve beyond flow-only execution identities while keeping current flow-backed paths intact.
- **Runtime session explorer APIs and UI**: Added account-scoped runtime session list/detail endpoints plus a dedicated console view for drilling into one managed session's model usage, model breakdowns, and captured gateway interactions.
- **Dashboard telemetry endpoint**: Added `GET /api/v1/account/telemetry/dashboard` to aggregate active runtime sessions, recent tool-call volume, daily spend, and success rate for the global operator dashboard.
- **Audit timeline session enrichment**: The grouped Audit timeline now includes runtime session lifecycle events, richer expandable metadata, and API token attribution on tool-policy activity so operators can trace session onboarding and guarded tool execution from the real Audit page.
- **Runtime session operator actions**: Operators can now end managed runtime sessions explicitly, with account events and managed-agent refreshes emitted from the same control-plane action.
- **Starter policy diff review**: MCP server onboarding now includes generated starter-policy diff previews and explicit review-before-apply flows in both the console and CLI.
- **Hash-only runtime API tokens**: Flow runtime API keys can now be stored and authenticated via hash/prefix fields without persisting the plaintext token.
- **Managed agent registry**: Added a durable `ManagedAgent` registry plus `GET /api/v1/agents` and `GET /api/v1/agents/{agent_id}` so onboarded external agents can be browsed independently from one runtime session.
- **Agents console surfaces**: Added `/console/agents` and `/console/agents/:agentId` so operators can inspect enrolled agents, linked MCP servers, session history, and recent runtime activity using the existing session drill-down surfaces.
- **Runtime session activity ledger**: Added normalized `RuntimeSessionActivity` records for MCP tool calls so runtime-session and managed-agent activity can be persisted beyond flow-backed execution logs.
- **Managed agent tool activity views**: Agent detail now includes historical model usage plus MCP server and tool activity breakdowns across all sessions owned by the same durable runtime principal.
- **ANSI log rendering**: Console execution logs now correctly parse and render ANSI color codes.

### Changed

- **Flow gateway usage summary**: `GET /api/v1/flows/{flow_id}/gateway-usage/summary` now loads the account through the account CRUD layer instead of an ad-hoc SQLAlchemy query.
- **Codex and OpenCode model transport**: Gateway-enabled executions now prefer Preloop gateway settings over direct-provider model credentials, while retaining compatibility fallbacks during rollout.
- **AI model credential storage**: New AI model credentials are stored via `SecretReference` instead of directly returning persisted plaintext API keys from the model record.
- **External secret backends**: AI models can now reference optional Vault/OpenBao-compatible KV v2 secrets through `credentials_backend_type` and `credentials_external_ref`.
- **Gateway client compatibility**: OpenAI-compatible and Anthropic-compatible ingress now return provider-native error envelopes for auth failures, validation errors, budget denials, and surfaced upstream gateway errors.
- **Agent identity model**: External-agent onboarding now separates durable `runtime_principal_id` from per-session `session_source_id`, allowing one enrolled agent to accumulate multiple runtime sessions over time.
- **Runtime session tenancy**: `RuntimeSession` source identity is now scoped by account so independently onboarded agents cannot collide across tenants.

### Security

- **Runtime token hardening**: Temporary flow runtime credentials are now revocable hash-only tokens rather than plaintext-only database entries.
- **Credential custody groundwork**: AI model secrets are now encrypted behind the secret-service abstraction, creating a clear path for external secret-manager backends without changing gateway callers.
- **Gemini fail-closed gateway behavior**: Gateway-enabled Gemini flows now error explicitly instead of falling back to direct provider traffic, preserving the requirement that managed model traffic must pass through Preloop.
- **Sensitive data redaction**: Centralized redaction of secrets and sensitive fields before logging, persisting to audit surfaces, or sending notifications. Tool arguments, approval payloads, and configuration changes are redacted in MCP execution logs, approval flows, flow execution logs, audit trail, and approval emails. See `preloop.utils.redaction` and ARCHITECTURE.md Redaction Policy.
- **Runtime session token scope validation**: Runtime-session token issuance now rejects caller-supplied scope escalation and only accepts account-authorized MCP server/tool restrictions.
- **Vault/OpenBao secret path hardening**: Secret reference validation now rejects traversal segments, encoded paths, and malformed external references before resolving secrets from Vault-compatible backends.

### Fixed

- **OpenClaw + Gemini onboarding**: Preloop AI models imported from OpenClaw now enable `meta_data.gateway` only when upstream provider credentials are actually stored (or already present on an existing model). This prevents gateway test calls from failing with “Model credentials are not configured” while the UI still showed gateway routing as enabled. OpenClaw `auth.profiles` entries with `mode: api_key` can now resolve inline or `${ENV}` API keys when the provider block does not expose `apiKey`.
- **AI model gateway controls in the console**: Adding or editing an AI model includes an explicit “route through Preloop gateway” option, and the model detail page can enable gateway routing when upstream credentials exist—addressing cases where Gemini (and other) models were configured with credentials but never received `meta_data.gateway.enabled`.
- **Dashboard telemetry query**: The account dashboard telemetry endpoint now filters gateway usage by `ApiUsage.timestamp`, restoring the intended active-session and daily-spend aggregation path.
- **Trial hosted-model denials**: Trial hosted-model hard-cap checks now use a consistent enforcement reason so direct budget-service callers return the intended BYOK guidance instead of a generic budget-exceeded error.
- **Runtime-session gateway inspection scoping**: When a `runtime_session_id` filter is present, gateway interaction search and per-model gateway totals now require matching `ApiUsage.runtime_session_id` rows only. Legacy rows attributed only to `flow_execution_id` with a null runtime session are no longer folded into session-scoped views (avoids mixing traffic across sessions that share execution lineage).
- **OpenCode gateway provider registry**: OpenCode `provider.*.models` keys now use a provider-local model id (with a single optional leading `{gateway_provider}/` stripped) so lookups stay aligned with the top-level `model` field after the gateway/provider refactor.
- **Gateway search performance**: Account interaction search now uses PostgreSQL full-text search plus a GIN index instead of broad `%...%` `ilike` scans on `GatewayUsageSearchDocument.searchable_text`.
- **AI model secret cleanup**: Deleting an AI model now removes its credential secret reference when no other model still depends on it.
- **Global default AI model seeding**: `scripts/init_db.py --force` can seed system-wide default AI models again by allowing global `SecretReference` rows without an account owner.
- **Gateway tool-call logging**: Anthropic payload normalization no longer emits raw LiteLLM tool-call argument payloads to debug logs, keeping the parsing fallback while aligning better with the branch's redaction posture.
- **Execution cancellation**: Restored the missing Cancel button for running executions.

## [0.8.0] - 2026-03-08

### Added

- **Async Approvals**: Tool calls can now return immediately with a `pending_approval` status when async approvals are enabled on a policy. Agents poll `get_approval_status` for the result instead of blocking, avoiding timeouts in CLI clients (Claude Code, Codex CLI). Approved tool results are cached for idempotent retrieval.
- **Per-Tool Justification Settings**: Configure `justification_mode` (`disabled`, `optional`, `required`) per tool via `ToolConfiguration`. When enabled, a `justification` parameter is injected into the tool schema and enforced server-side.
- **OpenCode Agent Support**: Added OpenCode as a supported agent type for flow execution alongside Codex, Gemini CLI, Aider, and OpenHands.

### Fixed

- **Async approval double-execution**: Concurrent poll requests could both execute an approved tool when `tool_result` was `None`. Fixed with `SELECT ... FOR UPDATE` row locking.
- **Approval remaining_seconds TypeError**: Subtracting a timezone-aware `datetime.now(timezone.utc)` from a naive `expires_at` column raised `TypeError`. Fixed to use consistent naive UTC datetimes.
- **Event timestamp serialization**: `event.timestamp.isoformat() + "Z"` produced invalid RFC 3339 when the timestamp already included a timezone offset. Fixed by stripping tzinfo before serialization.
- **Justification bypass**: `justification_mode=required` was only enforced via schema injection. Clients skipping schema validation could call tools without justification. Added server-side enforcement in `_call_tool`.
- **OSS 404 errors**: Frontend components (`approval-workflow-dialog`, settings views) unconditionally fetched `/api/v1/users`, `/api/v1/teams`, `/api/v1/roles` which don't exist in the open-source edition. Gated behind `advanced_approvals` and `user_management` feature flags.
- **Flow edit form empty values**: When editing an existing flow, select fields (model, tracker, tools) appeared empty until reference data loaded. Added loading spinners and parallelized API calls.

- **OAuth Sign-in/Sign-up**: Authenticate users via external OAuth providers (GitHub, Google, GitLab)
  - Plugin-based architecture: `plugins/oauth_signin/` with per-provider implementations
  - Auto-links OAuth identity to existing accounts by verified email
  - GitHub/GitLab sign-ups prompt for tracker installation after sign-in
  - Stripe checkout integration for new users when billing is enabled
  - Gated by `mcpOauth.enabled=true` Helm value; configure via `GOOGLE_OAUTH_CLIENT_ID/SECRET`, `GITLAB_OAUTH_CLIENT_ID/SECRET`, `GITHUB_APP_*` env vars
- **MCP OAuth 2.1 Authorization Server**: Full OAuth 2.1 server for MCP client authentication
  - Dynamic Client Registration (RFC 7591) at `POST /oauth/register`
  - Authorization Code + PKCE flow for MCP clients (Claude Desktop, etc.)
  - JWT token flow for CLI authentication (no PKCE)
  - Token revocation at `POST /oauth/revoke`
  - Discovery via `/.well-known/oauth-authorization-server` and `/.well-known/oauth-protected-resource`

### Security

- **OAuth consent validation**: Validate `client_id` exists and `redirect_uri` is registered before issuing authorization codes
- **XSS prevention**: HTML-escape all user-controlled values in OAuth consent page template
- **PKCE enforcement**: Require `code_verifier` when authorization code was created with `code_challenge`
- **Token delivery**: Use URL fragments instead of query parameters for OAuth callback tokens to prevent leakage via browser history, server logs, and Referrer headers
- **Redirect URI validation**: Verify `redirect_uri` at token exchange matches the original authorization request

### Fixed

- **OAuth refresh tokens**: MCP clients can now refresh opaque OAuth tokens (previously only JWT refresh worked)
- **Codex custom models**: Properly generate `~/.codex/config.toml` with `model_provider`, `base_url`, `env_key`, and `wire_api` for non-OpenAI models

- **Policy-as-Code**: Define and manage policies declaratively via YAML files
  - `POST /api/v1/policies/import`: Import policy from YAML with validation and diff preview
  - `GET /api/v1/policies/export`: Export current configuration as YAML
  - `POST /api/v1/policies/validate`: Validate policy syntax without applying
  - `POST /api/v1/policies/diff`: Compare policy document against current state
  - Supports MCP servers, approval workflows, tool configurations, and access rules
- **Policy Versioning & Rollback**: Version control for policy configurations
  - `GET /api/v1/policies/versions`: List all policy versions
  - `POST /api/v1/policies/versions`: Create a snapshot of current policy state
  - `PUT /api/v1/policies/versions/{id}/tag`: Tag versions for identification (e.g., "production", "v1.0")
  - `POST /api/v1/policies/versions/{id}/rollback`: Rollback to a previous version with diff preview
  - `DELETE /api/v1/policies/versions/{id}`: Delete old versions (supports pruning by age)
  - Credential-safe rollbacks: MCP server credentials are preserved during rollback
- **AI-Driven Approvals**: New approval type where an AI model evaluates tool call requests
  - Configure approval workflows with `approval_mode: "ai_driven"`
  - Set AI model, custom guidelines, confidence threshold (0.0-1.0)
  - Fallback behavior when AI is uncertain: escalate to human, auto-approve, or auto-deny
  - Full audit logging of AI decisions with reasoning and confidence scores
- **Tool Access Rules**: Fine-grained access control for tools beyond approvals
  - Define multiple rules per tool with `allow`, `deny`, or `require_approval` actions
  - Priority-based rule evaluation (higher priority rules are checked first)
  - Condition expressions for parameter-based rules (e.g., `args.amount > 500`)
  - Replaces the simpler `tool_approval_conditions` table
- **Policy Analysis**: Analyze policies for potential issues
  - `POST /api/v1/policies/analyze`: Detect always-match, never-match, unreachable, or conflicting rules
  - Natural language policy authoring assistance via configured AI model
- **CLI Tool**: Go-based command-line interface for policy management (`preloop/cli/`)
  - `preloop auth login/logout/status`: Authentication management
  - `preloop policy import/export/validate/diff`: Policy operations
  - `preloop tools list/configure`: Tool management
  - Daily version check with update prompts
- **Flow Execution Retry**: Failed, stopped, timed out, or cancelled flow executions can now be retried via `POST /api/v1/flows/executions/{id}/retry`. The new execution is linked to the original via `retry_of_execution_id` and uses the same trigger event data. UI retry button available in the execution detail view.
- **update_comment Issue Comment Support**: The `update_comment` tool now supports PR conversation comments (issue comments) in addition to inline review comments. Use the optional `comment_type` parameter to specify the type, or let the tool auto-detect by trying review_comment first then issue_comment.
- **Pull Request/Merge Request MCP Tools**: New built-in tools for PR/MR management:
  - `get_pull_request`: Fetch PR/MR details including comments and diff
  - `update_pull_request`: Update PR/MR state, submit reviews (approve, request changes, comment), add/remove reactions
  - `add_comment`: Add comments to PRs/MRs (general, inline code comments, threaded replies)
  - `update_comment`: Update or resolve existing PR/MR comments
  - `create_pull_request`: Create new PRs/MRs with full metadata support
  - Works with both GitHub Pull Requests and GitLab Merge Requests
- **PR/MR Reactions**: `update_pull_request` now supports adding and removing emoji reactions (GitHub: +1, -1, laugh, confused, heart, hooray, rocket, eyes; GitLab: thumbsup, thumbsdown, smile, eyes, rocket, etc.)
- **Commit Status Updates**: Flow executions now appear as commit status checks in GitHub/GitLab, showing "pending" while running and "success"/"failure" on completion
- **Bot Event Filtering**: Flow trigger service now detects and ignores events triggered by Preloop's own actions to prevent infinite loops
- **Android Push Notifications (FCM)**: Native Firebase Cloud Messaging support for Android mobile app push notifications
- **Push Proxy**: Proxy endpoint allowing OSS instances to send push notifications via production infrastructure
- **Message-based WebSocket Authentication**: Secure WebSocket auth via message after connection (tokens no longer in URLs)
- **Periodic Version Checker**: Automatic daily version check against preloop.ai (configurable interval, opt-out available)
- **Admin Activity Monitor**: Click-to-navigate from session to user/account details

### Changed

- **Tool Access Control**: Replaced `tool_approval_conditions` table with `tool_access_rules` supporting multiple rules per tool with allow/deny/require_approval actions and priority-based evaluation
- **Approval Workflow Schema**: Added AI-driven approval fields (`approval_mode`, `ai_model`, `ai_guidelines`, `ai_context`, `ai_confidence_threshold`, `ai_fallback_behavior`, `escalation_workflow_id`)
- **[BREAKING CHANGE] Policy & Configuration Rename**: `approval_policies` and `approval_policy_id` properties in policy definition files and SDK API models have been renamed to `approval_workflows` and `approval_workflow_id` respectively. Ensure you update any exported/custom YAML policies and API client integrations. Backward compatibility responses are provided where applicable.
- **FCM Service**: Moved Firebase SDK calls to thread pool executor to avoid blocking the event loop
- **Session Manager**: Database writes now run in thread pool to prevent event loop blocking during connection spikes
- **WebSocket Endpoints**: Updated to support message-based authentication for browsers

### Deprecated

- **`get_merge_request` MCP Tool**: Use `get_pull_request` instead. Works with both GitHub PRs and GitLab MRs.
- **`update_merge_request` MCP Tool**: Use `update_pull_request` instead. Works with both GitHub PRs and GitLab MRs.

### Fixed

- **GitHub Assignees/Reviewers Clearing**: `update_pull_request` with `assignees=[]` or `reviewers=[]` now correctly clears all assignees/reviewers on GitHub (previously it did nothing because GitHub's POST endpoints only add). Consistent behavior with GitLab.
- **GitHub App Reaction Removal**: `remove_issue_reaction` now safely handles GitHub App installation tokens by checking for `app_slug` in connection_details. Previously it attempted to call GET /app which fails with installation tokens.
- **GitHub Inline Comment ID**: `add_comment` now returns the actual comment ID instead of the review ID for GitHub inline comments, enabling proper follow-up updates via `update_comment`
- **Thread Resolution Validation**: `update_comment` now properly validates that `thread_id` is required for resolving threads. GitHub requires a thread ID (format: `PRRT_...`), not a comment ID. Automatic GraphQL lookup added for GitHub.
- **Inline Comment Side Parameter**: `add_comment` no longer validates the `side` parameter for non-inline comments, fixing errors when `side` was passed for regular comments
- **GitLab Inline Comments**: Now properly returns 501 error explaining that inline diff comments require position data not available in this API, instead of creating non-anchored discussions
- **GitLab Assignees/Reviewers**: `update_pull_request` and `create_pull_request` now correctly look up user IDs from usernames for GitLab, with clear warnings when lookups fail
- **Review Comments Validation**: `update_pull_request` now validates that each item in `review_comments` has required fields (path, line, body), returning 400 with clear error instead of 500
- **Git Clone Fallback**: When `git_clone_config.enabled = true` but `repositories` is empty, now falls back to using the trigger project for cloning
- **Self-hosted GitLab URLs**: Fixed URL parsing for self-hosted GitLab instances (no longer requires "gitlab" in hostname)
- **Milestone Pagination**: GitHub milestone lookup now paginates through all milestones instead of only checking the first page
- **HTTPException Wrapping**: Fixed exception handlers that were incorrectly wrapping HTTPException in 502 errors
- **Event Loop Blocking**: FCM notifications and session DB writes no longer block the FastAPI event loop
- **WebSocket Middleware Paths**: Middleware now handles `/api/v1/ws` prefixed paths correctly
- **Telemetry Env Var**: Both `PRELOOP_DISABLE_TELEMETRY` and `DISABLE_VERSION_CHECK` now work to disable telemetry
- **Session Manager Thread Safety**: DB writes now use thread-local sessions to avoid SQLAlchemy thread-safety issues
- **WebSocket Auth Upgrade**: Anonymous users upgrading to authenticated are now properly registered for broadcast messages
- **OpenAI API Errors**: Issue duplicates endpoint now returns 503 for API auth/rate limit errors instead of 500

### Configuration

New environment variables (see `.env.example`):
- `FCM_CREDENTIALS_JSON` / `FCM_CREDENTIALS_PATH`: Firebase service account credentials
- `PUSH_PROXY_URL` / `PUSH_PROXY_API_KEY`: Push proxy configuration for OSS instances
- `PRELOOP_DISABLE_TELEMETRY`: Disable version check telemetry
- `VERSION_CHECK_INTERVAL`: Seconds between version checks (default: 86400 = 24h)

### Database

New migration `20260201_policy_engine_enhancements`:
- Creates `tool_access_rules` table (replaces `tool_approval_conditions`)
- Creates `policy_snapshot` table for policy versioning
- Adds AI approval columns to `approval_workflow` table
- Migrates existing `tool_approval_conditions` data to new schema
- Run `alembic upgrade head` after updating
