import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './agent-detail-view.ts';
import type { AgentDetailView } from './agent-detail-view';

describe('AgentDetailView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url === '/api/v1/agents/agent-1') {
        return new Response(
          JSON.stringify({
            agent: {
              id: 'agent-1',
              runtime_session_id: 'runtime-session-2',
              display_name: 'Claude Code Workspace',
              session_source_type: 'claude_code',
              session_source_id: 'claude-code-agent-1',
              session_reference: 'claude-session-2',
              enrolled_via: 'runtime_session_token',
              managed_mcp_servers: ['github', 'jira'],
              lifecycle_state: 'active',
              lifecycle_reason: null,
              lifecycle_updated_at: '2026-03-10T10:00:00Z',
              is_active_now: true,
              activity_status: 'active_now',
              last_seen_at: '2026-03-10T10:00:00Z',
              started_at: '2026-03-10T09:00:00Z',
              last_activity_at: '2026-03-10T10:00:00Z',
              ended_at: null,
              total_requests: 1,
              estimated_cost: 0.12,
              configured_model_alias: 'openai/gpt-5',
              configured_model_id: 'configured-model-1',
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              last_request_at: '2026-03-10T09:58:00Z',
              mcp_proxy_configured: true,
              model_gateway_configured: true,
              onboarding_state: 'fully_onboarded',
              live_validation_supported: true,
              live_validation_passed: true,
              live_validation_status: 'passed',
              last_validated_at: '2026-03-10T10:01:00Z',
              owner_user_id: null,
              owner_username: null,
              owner_email: null,
            },
            aggregate: {
              session_count: 2,
              total_requests: 4,
              successful_requests: 3,
              failed_requests: 1,
              token_usage: {
                prompt_tokens: 300,
                completion_tokens: 120,
                total_tokens: 420,
              },
              estimated_cost: 0.57,
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              last_request_at: '2026-03-10T09:58:00Z',
            },
            usage_by_model: [
              {
                ai_model_id: 'model-1',
                model_alias: 'openai/gpt-5',
                provider_name: 'openai',
                request_count: 4,
                token_usage: {
                  prompt_tokens: 300,
                  completion_tokens: 120,
                  total_tokens: 420,
                },
                estimated_cost: 0.57,
              },
            ],
            activity_by_server: [
              {
                server_name: 'github',
                call_count: 2,
                successful_calls: 2,
                failed_calls: 0,
                last_activity_at: '2026-03-10T10:00:00Z',
              },
            ],
            activity_by_tool: [
              {
                server_name: 'github',
                tool_name: 'search_issues',
                call_count: 2,
                successful_calls: 2,
                failed_calls: 0,
                last_activity_at: '2026-03-10T10:00:00Z',
              },
            ],
            sessions: [
              {
                id: 'runtime-session-2',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-2',
                session_reference: null,
                runtime_principal_type: 'claude_code',
                runtime_principal_id: 'claude-code-agent-1',
                runtime_principal_name: 'Claude Code Workspace',
                started_at: '2026-03-10T09:30:00Z',
                last_activity_at: '2026-03-10T09:59:00Z',
                ended_at: null,
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'openai/gpt-5',
                latest_provider_name: 'openai',
                is_active_now: true,
                activity_status: 'active_now',
                total_requests: 1,
                successful_requests: 1,
                failed_requests: 0,
                token_usage: {
                  prompt_tokens: 100,
                  completion_tokens: 20,
                  total_tokens: 120,
                },
                estimated_cost: 0.12,
                last_request_at: '2026-03-10T09:59:00Z',
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url === '/api/v1/agents/agent-1/governance') {
        return new Response(
          JSON.stringify({
            subject_type: 'managed_agents',
            subject_id: 'agent-1',
            config: {
              allowed_models: ['openai/gpt-5'],
              model_budgets: {
                'openai/gpt-5': { monthly_usd_limit: 25 },
              },
              tool_rules: {
                search_issues: [{ action: 'allow', condition_type: 'simple' }],
              },
            },
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url === '/api/v1/runtime-sessions/runtime-session-2') {
        return new Response(
          JSON.stringify({
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-10T23:59:59Z',
            session: {
              id: 'runtime-session-2',
              session_source_type: 'claude_code',
              session_source_id: 'workspace-2',
              session_reference: null,
              runtime_principal_type: 'claude_code',
              runtime_principal_id: 'claude-code-agent-1',
              runtime_principal_name: 'Claude Code Workspace',
              started_at: '2026-03-10T09:30:00Z',
              last_activity_at: '2026-03-10T09:59:00Z',
              ended_at: null,
              flow_id: null,
              flow_name: null,
              flow_execution_id: null,
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              is_active_now: true,
              activity_status: 'active_now',
              total_requests: 1,
              successful_requests: 1,
              failed_requests: 0,
              token_usage: {
                prompt_tokens: 100,
                completion_tokens: 20,
                total_tokens: 120,
              },
              estimated_cost: 0.12,
              last_request_at: '2026-03-10T09:59:00Z',
            },
            usage_by_model: [],
            interactions: {
              period_start: '2026-03-01T00:00:00Z',
              period_end: '2026-03-10T23:59:59Z',
              query: null,
              total: 0,
              limit: 10,
              offset: 0,
              items: [],
            },
            activity_timeline: [
              {
                activity_type: 'tool_call',
                timestamp: '2026-03-10T09:59:00Z',
                title: 'github / search_issues',
                summary: 'Completed successfully',
                status: 'success',
                api_usage_id: null,
                tool_name: 'search_issues',
                server_name: 'github',
                auth_subject_type: null,
                api_key_id: null,
                api_key_name: null,
                estimated_cost: null,
                total_tokens: null,
              },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url === '/api/v1/users') {
        return new Response(JSON.stringify({ users: [] }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (url === '/api/v1/tools') {
        return new Response(
          JSON.stringify([
            {
              name: 'search_issues',
              description: 'Search GitHub issues',
              schema: {
                properties: {
                  query: { type: 'string' },
                },
              },
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url === '/api/v1/approval-workflows') {
        return new Response(
          JSON.stringify([
            {
              id: 'wf-1',
              name: 'Default Approval',
              approval_type: 'standard',
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url === '/api/v1/features') {
        return new Response(JSON.stringify({ features: {} }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (url === '/api/v1/mcp-servers') {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      if (url === '/api/v1/ai-models') {
        return new Response(JSON.stringify([]), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }

      return new Response(
        JSON.stringify({ detail: `Unhandled request: ${url}` }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    });
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  it('renders live validation and scoped governance', async () => {
    const element = await fixture<AgentDetailView>(
      html`<agent-detail-view agentId="agent-1"></agent-detail-view>`
    );

    await waitUntil(
      () => !(element as any).loading && (element as any).agent !== null,
      'Agent detail view did not finish loading'
    );
    await element.updateComplete;

    const viewHeader = element.shadowRoot?.querySelector('view-header');
    expect(viewHeader?.getAttribute('headertext')).to.equal(
      'Claude Code Workspace'
    );

    const content = element.shadowRoot?.textContent || '';
    expect(content).to.contain('Live validated');
    expect(content).to.contain('openai/gpt-5');
    expect(content).to.contain(
      'Tool calls and model traffic both flow through Preloop.'
    );
    const modelLink = element.shadowRoot?.querySelector(
      'a.session-link[href="/console/settings/ai-models/configured-model-1"]'
    );
    expect(modelLink).to.exist;
    const wrongModelLink = element.shadowRoot?.querySelector(
      'a.session-link[href="/console/settings/ai-models/model-1"]'
    );
    expect(wrongModelLink).to.not.exist;
  });
});
