import { fixture, html, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './runtime-sessions-view';
import type { RuntimeSessionsView } from './runtime-sessions-view';

describe('RuntimeSessionsView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.startsWith('/api/v1/account/runtime-sessions?')) {
        return new Response(
          JSON.stringify({
            period_start: '2026-02-08T00:00:00Z',
            period_end: '2026-03-09T23:59:59Z',
            query: null,
            session_source_type: null,
            status: 'all',
            total: 2,
            limit: 50,
            offset: 0,
            items: [
              {
                id: 'runtime-session-1',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-42',
                session_reference: 'claude-session-42',
                runtime_principal_type: 'claude_code',
                runtime_principal_id: 'workspace-42',
                runtime_principal_name: 'Claude Workspace',
                started_at: '2026-03-09T18:00:00Z',
                last_activity_at: '2026-03-09T20:00:00Z',
                ended_at: null,
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'anthropic/claude-sonnet-4',
                latest_provider_name: 'Anthropic',
                total_requests: 4,
                successful_requests: 3,
                failed_requests: 1,
                token_usage: {
                  prompt_tokens: 1200,
                  completion_tokens: 450,
                  total_tokens: 1650,
                },
                estimated_cost: 0.42,
                last_request_at: '2026-03-09T20:00:00Z',
              },
              {
                id: 'runtime-session-2',
                session_source_type: 'flow_execution',
                session_source_id: 'execution-1',
                session_reference: 'session-abc123',
                runtime_principal_type: 'flow_execution',
                runtime_principal_id: 'execution-1',
                runtime_principal_name: 'Triage Assistant',
                started_at: '2026-03-09T19:00:00Z',
                last_activity_at: '2026-03-09T19:15:00Z',
                ended_at: '2026-03-09T19:20:00Z',
                flow_id: 'flow-1',
                flow_name: 'Triage Assistant',
                flow_execution_id: 'execution-1',
                latest_model_alias: 'openai/gpt-5',
                latest_provider_name: 'OpenAI',
                total_requests: 2,
                successful_requests: 2,
                failed_requests: 0,
                token_usage: {
                  prompt_tokens: 500,
                  completion_tokens: 200,
                  total_tokens: 700,
                },
                estimated_cost: 0.11,
                last_request_at: '2026-03-09T19:15:00Z',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (
        url.startsWith('/api/v1/account/runtime-sessions/runtime-session-1')
      ) {
        return new Response(
          JSON.stringify({
            period_start: '2026-02-08T00:00:00Z',
            period_end: '2026-03-09T23:59:59Z',
            session: {
              id: 'runtime-session-1',
              session_source_type: 'claude_code',
              session_source_id: 'workspace-42',
              session_reference: 'claude-session-42',
              runtime_principal_type: 'claude_code',
              runtime_principal_id: 'workspace-42',
              runtime_principal_name: 'Claude Workspace',
              started_at: '2026-03-09T18:00:00Z',
              last_activity_at: '2026-03-09T20:00:00Z',
              ended_at: null,
              flow_id: null,
              flow_name: null,
              flow_execution_id: null,
              latest_model_alias: 'anthropic/claude-sonnet-4',
              latest_provider_name: 'Anthropic',
              total_requests: 4,
              successful_requests: 3,
              failed_requests: 1,
              token_usage: {
                prompt_tokens: 1200,
                completion_tokens: 450,
                total_tokens: 1650,
              },
              estimated_cost: 0.42,
              last_request_at: '2026-03-09T20:00:00Z',
            },
            usage_by_model: [
              {
                ai_model_id: 'model-1',
                model_alias: 'anthropic/claude-sonnet-4',
                provider_name: 'Anthropic',
                request_count: 4,
                token_usage: {
                  prompt_tokens: 1200,
                  completion_tokens: 450,
                  total_tokens: 1650,
                },
                estimated_cost: 0.42,
              },
            ],
            interactions: {
              period_start: '2026-02-08T00:00:00Z',
              period_end: '2026-03-09T23:59:59Z',
              query: null,
              total: 1,
              limit: 50,
              offset: 0,
              items: [
                {
                  api_usage_id: 'usage-1',
                  timestamp: '2026-03-09T20:00:00Z',
                  status_code: 200,
                  outcome: 'success',
                  endpoint: '/anthropic/v1/messages',
                  method: 'POST',
                  provider_name: 'Anthropic',
                  model_alias: 'anthropic/claude-sonnet-4',
                  flow_id: null,
                  flow_name: null,
                  flow_execution_id: null,
                  runtime_session_id: 'runtime-session-1',
                  session_source_type: 'claude_code',
                  session_source_id: 'workspace-42',
                  session_reference: 'claude-session-42',
                  runtime_principal_type: 'claude_code',
                  runtime_principal_id: 'workspace-42',
                  runtime_principal_name: 'Claude Workspace',
                  auth_subject_type: 'api_key',
                  api_key_id: 'api-key-1',
                  api_key_name: 'Claude Workspace Token',
                  estimated_cost: 0.12,
                  token_usage: {
                    prompt_tokens: 200,
                    completion_tokens: 75,
                    total_tokens: 275,
                  },
                  excerpt:
                    'request.input: Summarize the deployment risk review response.output_text: Deployment risk review summarized',
                  meta_data: {
                    source: 'gateway_interaction',
                  },
                },
              ],
            },
            activity_timeline: [
              {
                activity_type: 'session_started',
                timestamp: '2026-03-09T18:00:00Z',
                title: 'Session started',
                summary: 'claude-session-42',
                status: 'info',
                api_usage_id: null,
                tool_name: null,
                server_name: null,
                auth_subject_type: null,
                api_key_id: null,
                api_key_name: null,
                estimated_cost: null,
                total_tokens: null,
              },
              {
                activity_type: 'tool_call',
                timestamp: '2026-03-09T20:00:01Z',
                title: 'search_issues',
                summary: 'Found similar issues',
                status: 'success',
                api_usage_id: null,
                tool_name: 'search_issues',
                server_name: 'preloop-mcp',
                auth_subject_type: null,
                api_key_id: null,
                api_key_name: null,
                estimated_cost: null,
                total_tokens: null,
              },
              {
                activity_type: 'model_interaction',
                timestamp: '2026-03-09T20:00:00Z',
                title: 'anthropic/claude-sonnet-4',
                summary: 'POST /anthropic/v1/messages',
                status: 'success',
                api_usage_id: 'usage-1',
                tool_name: null,
                server_name: null,
                auth_subject_type: 'api_key',
                api_key_id: 'api-key-1',
                api_key_name: 'Claude Workspace Token',
                estimated_cost: 0.12,
                total_tokens: 275,
              },
              {
                activity_type: 'session_ended',
                timestamp: '2026-03-09T20:30:00Z',
                title: 'Session ended',
                summary: 'claude-session-42',
                status: 'completed',
                api_usage_id: null,
                tool_name: null,
                server_name: null,
                auth_subject_type: null,
                api_key_id: null,
                api_key_name: null,
                estimated_cost: null,
                total_tokens: null,
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      return new Response(
        JSON.stringify({ detail: `Unhandled request: ${url}` }),
        {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        }
      );
    });
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
    window.history.replaceState({}, '', '/console/runtime-sessions');
  });

  it('renders runtime session list and selected session detail', async () => {
    const element = (await fixture(
      html`<runtime-sessions-view></runtime-sessions-view>`
    )) as RuntimeSessionsView;

    await waitUntil(
      () => !(element as any).loading && !(element as any).detailLoading,
      'Runtime sessions view did not finish loading'
    );
    await element.updateComplete;

    const content = element.shadowRoot?.textContent || '';
    expect(content).to.contain('Runtime Sessions');
    expect(content).to.contain('Claude Workspace');
    expect(content).to.contain('Activity Timeline');
    expect(content).to.contain('search_issues');
    expect(content).to.contain('Captured Interactions');
    expect(content).to.contain('deployment risk review');
    expect(content).to.contain('anthropic/claude-sonnet-4');
    expect(content).to.contain('Session started');
    expect(content).to.contain('Session ended');
    expect(content).to.contain('Claude Workspace Token');

    const listCall = fetchStub
      .getCalls()
      .find((call) =>
        String(call.args[0]).startsWith('/api/v1/account/runtime-sessions?')
      );
    const detailCall = fetchStub
      .getCalls()
      .find((call) =>
        String(call.args[0]).startsWith(
          '/api/v1/account/runtime-sessions/runtime-session-1'
        )
      );

    expect(listCall).to.not.equal(undefined);
    expect(detailCall).to.not.equal(undefined);
  });
});
