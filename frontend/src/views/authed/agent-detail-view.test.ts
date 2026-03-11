import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './agent-detail-view';
import type { AgentDetailView } from './agent-detail-view';

describe('AgentDetailView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.endsWith('/api/v1/agents/agent-1')) {
        return new Response(
          JSON.stringify({
            agent: {
              id: 'agent-1',
              runtime_session_id: 'runtime-session-1',
              display_name: 'Claude Code Workspace',
              session_source_type: 'claude_code',
              session_source_id: 'claude-code-agent-1',
              session_reference: 'claude-session-abc',
              enrolled_via: 'runtime_session_token',
              managed_mcp_servers: ['github', 'jira'],
              last_seen_at: '2026-03-10T10:00:00Z',
              started_at: '2026-03-10T09:00:00Z',
              last_activity_at: '2026-03-10T10:00:00Z',
              ended_at: null,
              total_requests: 2,
              estimated_cost: 0.3,
              latest_model_alias: 'openai/gpt-5-mini',
              latest_provider_name: 'openai',
              last_request_at: '2026-03-10T09:58:00Z',
            },
            aggregate: {
              session_count: 2,
              total_requests: 2,
              successful_requests: 1,
              failed_requests: 1,
              token_usage: {
                prompt_tokens: 150,
                completion_tokens: 30,
                total_tokens: 180,
              },
              estimated_cost: 0.3,
              latest_model_alias: 'openai/gpt-5-mini',
              latest_provider_name: 'openai',
              last_request_at: '2026-03-10T09:58:00Z',
            },
            usage_by_model: [
              {
                ai_model_id: 'model-1',
                model_alias: 'openai/gpt-5',
                provider_name: 'openai',
                request_count: 1,
                token_usage: {
                  prompt_tokens: 100,
                  completion_tokens: 20,
                  total_tokens: 120,
                },
                estimated_cost: 0.25,
              },
              {
                ai_model_id: 'model-2',
                model_alias: 'openai/gpt-5-mini',
                provider_name: 'openai',
                request_count: 1,
                token_usage: {
                  prompt_tokens: 50,
                  completion_tokens: 10,
                  total_tokens: 60,
                },
                estimated_cost: 0.05,
              },
            ],
            activity_by_server: [
              {
                server_name: 'github',
                call_count: 2,
                successful_calls: 1,
                failed_calls: 1,
                last_activity_at: '2026-03-10T09:59:00Z',
              },
              {
                server_name: 'jira',
                call_count: 1,
                successful_calls: 1,
                failed_calls: 0,
                last_activity_at: '2026-03-10T09:58:30Z',
              },
            ],
            activity_by_tool: [
              {
                server_name: 'github',
                tool_name: 'search_issues',
                call_count: 2,
                successful_calls: 1,
                failed_calls: 1,
                last_activity_at: '2026-03-10T09:59:00Z',
              },
              {
                server_name: 'jira',
                tool_name: 'get_issue',
                call_count: 1,
                successful_calls: 1,
                failed_calls: 0,
                last_activity_at: '2026-03-10T09:58:30Z',
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
                latest_model_alias: 'openai/gpt-5-mini',
                latest_provider_name: 'openai',
                total_requests: 1,
                successful_requests: 0,
                failed_requests: 1,
                token_usage: {
                  prompt_tokens: 50,
                  completion_tokens: 10,
                  total_tokens: 60,
                },
                estimated_cost: 0.05,
                last_request_at: '2026-03-10T09:59:00Z',
              },
              {
                id: 'runtime-session-1',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-1',
                session_reference: null,
                runtime_principal_type: 'claude_code',
                runtime_principal_id: 'claude-code-agent-1',
                runtime_principal_name: 'Claude Code Workspace',
                started_at: '2026-03-10T09:00:00Z',
                last_activity_at: '2026-03-10T09:45:00Z',
                ended_at: '2026-03-10T09:46:00Z',
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'openai/gpt-5',
                latest_provider_name: 'openai',
                total_requests: 1,
                successful_requests: 1,
                failed_requests: 0,
                token_usage: {
                  prompt_tokens: 100,
                  completion_tokens: 20,
                  total_tokens: 120,
                },
                estimated_cost: 0.25,
                last_request_at: '2026-03-10T09:45:00Z',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url.endsWith('/api/v1/runtime-sessions/runtime-session-1')) {
        return new Response(
          JSON.stringify({
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-10T23:59:59Z',
            session: {
              id: 'runtime-session-1',
              session_source_type: 'claude_code',
              session_source_id: 'workspace-1',
              session_reference: null,
              runtime_principal_type: 'claude_code',
              runtime_principal_id: 'claude-code-agent-1',
              runtime_principal_name: 'Claude Code Workspace',
              started_at: '2026-03-10T09:00:00Z',
              last_activity_at: '2026-03-10T09:45:00Z',
              ended_at: '2026-03-10T09:46:00Z',
              flow_id: null,
              flow_name: null,
              flow_execution_id: null,
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              total_requests: 1,
              successful_requests: 1,
              failed_requests: 0,
              token_usage: {
                prompt_tokens: 100,
                completion_tokens: 20,
                total_tokens: 120,
              },
              estimated_cost: 0.25,
              last_request_at: '2026-03-10T09:45:00Z',
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
                timestamp: '2026-03-10T09:44:00Z',
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
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url.endsWith('/api/v1/runtime-sessions/runtime-session-2')) {
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
              latest_model_alias: 'openai/gpt-5-mini',
              latest_provider_name: 'openai',
              total_requests: 1,
              successful_requests: 0,
              failed_requests: 1,
              token_usage: {
                prompt_tokens: 50,
                completion_tokens: 10,
                total_tokens: 60,
              },
              estimated_cost: 0.05,
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
                title: 'jira / get_issue',
                summary: 'rate limited',
                status: 'failed',
                api_usage_id: null,
                tool_name: 'get_issue',
                server_name: 'jira',
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
  });

  it('renders managed agent aggregates and session activity history', async () => {
    const element = await fixture<AgentDetailView>(
      html`<agent-detail-view agentId="agent-1"></agent-detail-view>`
    );

    await waitUntil(
      () => !(element as any).loading && (element as any).agent !== null,
      'Agent detail view did not finish loading'
    );
    await element.updateComplete;

    const initialContent = element.shadowRoot?.textContent || '';
    expect(initialContent).to.contain('Claude Code Workspace');
    expect(initialContent).to.contain('Historical Model Usage');
    expect(initialContent).to.contain('Historical MCP Server Activity');
    expect(initialContent).to.contain('Historical Tool Activity');
    expect(initialContent).to.contain('openai/gpt-5');
    expect(initialContent).to.contain('openai/gpt-5-mini');
    expect(initialContent).to.contain('github');
    expect(initialContent).to.contain('jira');
    expect(initialContent).to.contain('search_issues');
    expect(initialContent).to.contain('get_issue');
    expect(initialContent).to.contain('Historical Sessions');
    expect(initialContent).to.contain('$0.30');
    expect(initialContent).to.contain('180');

    await (element as any).selectSession('runtime-session-2');
    await waitUntil(
      () => (element as any).runtimeDetail?.session?.id === 'runtime-session-2',
      'Second session detail did not load'
    );
    await element.updateComplete;

    const updatedContent = element.shadowRoot?.textContent || '';
    expect(updatedContent).to.contain('workspace-2');
    expect(updatedContent).to.contain('rate limited');

    const sessionTwoCall = fetchStub
      .getCalls()
      .find((call) =>
        String(call.args[0]).endsWith(
          '/api/v1/runtime-sessions/runtime-session-2'
        )
      );
    expect(sessionTwoCall).to.not.equal(undefined);
  });
});
import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './agent-detail-view';
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
              last_seen_at: '2026-03-10T10:00:00Z',
              started_at: '2026-03-10T09:00:00Z',
              last_activity_at: '2026-03-10T10:00:00Z',
              ended_at: null,
              total_requests: 1,
              estimated_cost: 0.12,
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              last_request_at: '2026-03-10T09:58:00Z',
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
                ai_model_id: null,
                model_alias: 'openai/gpt-5',
                provider_name: 'openai',
                request_count: 3,
                token_usage: {
                  prompt_tokens: 240,
                  completion_tokens: 90,
                  total_tokens: 330,
                },
                estimated_cost: 0.45,
              },
              {
                ai_model_id: null,
                model_alias: 'openai/gpt-5-mini',
                provider_name: 'openai',
                request_count: 1,
                token_usage: {
                  prompt_tokens: 60,
                  completion_tokens: 30,
                  total_tokens: 90,
                },
                estimated_cost: 0.12,
              },
            ],
            activity_by_server: [
              {
                server_name: 'github',
                call_count: 3,
                successful_calls: 2,
                failed_calls: 1,
                last_activity_at: '2026-03-10T09:58:00Z',
              },
              {
                server_name: 'jira',
                call_count: 1,
                successful_calls: 1,
                failed_calls: 0,
                last_activity_at: '2026-03-10T09:40:00Z',
              },
            ],
            activity_by_tool: [
              {
                server_name: 'github',
                tool_name: 'search_issues',
                call_count: 2,
                successful_calls: 1,
                failed_calls: 1,
                last_activity_at: '2026-03-10T09:58:00Z',
              },
              {
                server_name: 'jira',
                tool_name: 'get_issue',
                call_count: 1,
                successful_calls: 1,
                failed_calls: 0,
                last_activity_at: '2026-03-10T09:40:00Z',
              },
            ],
            sessions: [
              {
                id: 'runtime-session-2',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-2',
                session_reference: 'claude-session-2',
                runtime_principal_type: 'claude_code',
                runtime_principal_id: 'claude-code-agent-1',
                runtime_principal_name: 'Claude Code Workspace',
                started_at: '2026-03-10T09:30:00Z',
                last_activity_at: '2026-03-10T10:00:00Z',
                ended_at: null,
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'openai/gpt-5',
                latest_provider_name: 'openai',
                total_requests: 3,
                successful_requests: 3,
                failed_requests: 0,
                token_usage: {
                  prompt_tokens: 240,
                  completion_tokens: 90,
                  total_tokens: 330,
                },
                estimated_cost: 0.45,
                last_request_at: '2026-03-10T09:58:00Z',
              },
              {
                id: 'runtime-session-1',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-1',
                session_reference: 'claude-session-1',
                runtime_principal_type: 'claude_code',
                runtime_principal_id: 'claude-code-agent-1',
                runtime_principal_name: 'Claude Code Workspace',
                started_at: '2026-03-10T09:00:00Z',
                last_activity_at: '2026-03-10T09:20:00Z',
                ended_at: '2026-03-10T09:25:00Z',
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'openai/gpt-5-mini',
                latest_provider_name: 'openai',
                total_requests: 1,
                successful_requests: 0,
                failed_requests: 1,
                token_usage: {
                  prompt_tokens: 60,
                  completion_tokens: 30,
                  total_tokens: 90,
                },
                estimated_cost: 0.12,
                last_request_at: '2026-03-10T09:20:00Z',
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url === '/api/v1/runtime-sessions/runtime-session-2') {
        return new Response(
          JSON.stringify({
            period_start: '2026-02-09T10:00:00Z',
            period_end: '2026-03-10T10:00:00Z',
            session: {
              id: 'runtime-session-2',
              session_source_type: 'claude_code',
              session_source_id: 'workspace-2',
              session_reference: 'claude-session-2',
              runtime_principal_type: 'claude_code',
              runtime_principal_id: 'claude-code-agent-1',
              runtime_principal_name: 'Claude Code Workspace',
              started_at: '2026-03-10T09:30:00Z',
              last_activity_at: '2026-03-10T10:00:00Z',
              ended_at: null,
              flow_id: null,
              flow_name: null,
              flow_execution_id: null,
              latest_model_alias: 'openai/gpt-5',
              latest_provider_name: 'openai',
              total_requests: 3,
              successful_requests: 3,
              failed_requests: 0,
              token_usage: {
                prompt_tokens: 240,
                completion_tokens: 90,
                total_tokens: 330,
              },
              estimated_cost: 0.45,
              last_request_at: '2026-03-10T09:58:00Z',
            },
            usage_by_model: [],
            interactions: {
              period_start: '2026-02-09T10:00:00Z',
              period_end: '2026-03-10T10:00:00Z',
              query: null,
              total: 0,
              limit: 50,
              offset: 0,
              items: [],
            },
            activity_timeline: [
              {
                activity_type: 'model_interaction',
                timestamp: '2026-03-10T09:58:00Z',
                title: 'openai/gpt-5',
                summary: 'POST /openai/v1/responses',
                status: 'success',
                api_usage_id: 'usage-1',
                tool_name: null,
                server_name: null,
                auth_subject_type: null,
                api_key_id: null,
                api_key_name: null,
                estimated_cost: 0.45,
                total_tokens: 330,
              },
            ],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      return new Response('Not found', { status: 404 });
    });
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  it('renders historical aggregates for the managed agent', async () => {
    const el = await fixture<AgentDetailView>(
      html`<agent-detail-view agentId="agent-1"></agent-detail-view>`
    );

    await waitUntil(() => !el.shadowRoot?.querySelector('sl-spinner'));

    const text = el.shadowRoot?.textContent || '';
    expect(text).to.contain('Historical Sessions');
    expect(text).to.contain('2');
    expect(text).to.contain('Total Requests');
    expect(text).to.contain('4');
    expect(text).to.contain('Historical Tokens');
    expect(text).to.contain('420');
    expect(text).to.contain('$0.57');
    expect(text).to.contain('3 success · 1 failed');
    expect(text).to.contain('Historical Model Usage');
    expect(text).to.contain('openai/gpt-5');
    expect(text).to.contain('330 tokens');
    expect(text).to.contain('openai/gpt-5-mini');
    expect(text).to.contain('90 tokens');
    expect(text).to.contain('Historical MCP Server Activity');
    expect(text).to.contain('github');
    expect(text).to.contain('3 call(s)');
    expect(text).to.contain('Historical Tool Activity');
    expect(text).to.contain('search_issues');
    expect(text).to.contain('get_issue');
    expect(text).to.contain('workspace-2');
    expect(text).to.contain('workspace-1');
  });
});
