# AI Control Plane UX And Integration Review

This note captures the current UX and integration findings for the delivered AI workforce/control-plane work.

## Summary

The core observability and operator primitives are now real:

- AI model fleet and detail observability
- managed-agent registry and lifecycle controls
- runtime-session explorer and operator session ending
- audit-linked runtime and gateway evidence
- account-scoped realtime refresh across the major control-plane surfaces

The biggest remaining gap is not telemetry. It is the operator journey into those features, especially enrollment and remediation.

## Priority Findings

### P1: Enrollment Is Implemented But Not Productized

The durable onboarding path exists in the backend and CLI, but it is not discoverable from the console.

Relevant files:

- `preloop/backend/preloop/api/auth/router.py`
- `preloop/cli/internal/cmd/agents.go`
- `preloop/frontend/src/api.ts`
- `preloop/frontend/src/views/public/welcome-view.ts`

Impact:

- A user can browse and manage agents after enrollment
- A user cannot naturally discover how to enroll one from the product itself

Recommendation:

- Add a first-class enrollment entry point from the dashboard and/or agents page
- Expose runtime-session token issuance in the console

### P1: Home Page Drifted Too Far From The Original Overview

The new control-plane dashboard improved AI observability, but it removed too much of the previous overview context.

Relevant files:

- `preloop/frontend/src/views/authed/dashboard-control-plane-view.ts`
- `preloop/frontend/src/views/authed/console-shell.ts`

Impact:

- Flows, MCP/tool setup, approvals, and onboarding became less visible
- The home page stopped feeling like the primary operator landing page

Recommendation:

- Keep the merged dashboard approach
- Treat classic overview cards as stable anchors
- Use conditional visibility mainly for exception-oriented cards

### P1: Failure Discovery Is Better Than Failure Remediation

Users can see that something is wrong, but they still have to hop around too much to fix it.

Relevant files:

- `preloop/frontend/src/views/authed/settings/ai-models-view.ts`
- `preloop/frontend/src/views/authed/settings/ai-model-detail-view.ts`
- `preloop/frontend/src/views/authed/runtime-sessions-view.ts`
- `preloop/frontend/src/views/authed/agent-detail-view.ts`

Impact:

- Triage is possible
- Remediation is inconsistently placed

Recommendation:

- Add scoped “next action” CTAs from failure states
- Reuse existing actions first: suspend, resume, decommission, re-enroll, end session, open approvals

## Discoverability Findings

### AI Model Placement Feels Secondary

`AI Models` remains under Settings even though it is now a primary control-plane surface.

Relevant file:

- `preloop/frontend/src/views/authed/settings/ai-models-view.ts`

Recommendation:

- Either promote AI models in navigation
- Or make the dashboard a stronger launcher into model-centric operations

### Runtime Session Versus Agent Is Still Hard To Learn

The concepts are correct, but the product still expects the operator to infer the distinction.

Relevant files:

- `preloop/frontend/src/views/authed/agents-view.ts`
- `preloop/frontend/src/views/authed/agent-detail-view.ts`
- `preloop/frontend/src/views/authed/runtime-sessions-view.ts`

Recommendation:

- Add short, persistent explanatory copy in at least one control-plane landing surface
- Strengthen cross-links in both directions between session and agent views

## Cross-Surface Duplication Findings

The same operational evidence now appears in multiple valid places:

- dashboard
- API usage
- AI model detail
- runtime session detail
- audit

This is useful, but the triage hierarchy is not obvious.

Recommendation:

- Define a primary “start here” path for each kind of problem:
  - model problem -> model detail
  - runtime problem -> runtime session detail
  - agent/operator problem -> agent detail
  - forensic/compliance problem -> audit

## Audit Findings

Audit has become much more useful, but it still feels more forensic than operational.

Relevant file:

- `preloop/frontend/src/views/authed/audit-view.ts`

Recommendation:

- Add better links and filters for agent, runtime session, and AI model identities
- Make operator lifecycle actions easier to find from audit outcomes

## Docs And Messaging Gaps

Docs and product messaging do not yet reflect the current reality consistently.

Relevant files:

- `preloop/README.md`
- `preloop/ARCHITECTURE.md`
- `preloop/frontend/README.md`
- `docs/guide/integrations/claude-code.md`
- `docs/guide/integrations/openclaw.md`

Recommendation:

- Separate “implemented now” from “coming next”
- Add one explicit operator-oriented onboarding guide covering:
  - runtime-session token issuance
  - managed-agent registry behavior
  - where to inspect traffic after onboarding

## Review Checklist

Use this when manually reviewing the current product:

1. From `Overview`, can an operator tell what to configure next?
2. Can they find flows, MCP, approvals, models, agents, sessions, and audit without guessing?
3. After a failed model call, can they reach the right remediation surface in one or two clicks?
4. After onboarding an external client, can they explain the difference between the durable agent and the session it produced?
5. Does audit help close the loop, or only confirm that something already known happened?

## Recommended Next Fixes

### Must-Fix Soon

- Productize enrollment in the console
- Add reason capture for operator lifecycle actions where supported
- Improve dashboard remediation paths

### Strong Follow-Ups

- Add shared alert definitions across dashboard/model/session/agent views
- Improve audit filtering and linking by control-plane identity
- Clarify runtime session vs managed agent semantics in-product
