import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import '../../components/view-header.ts';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import './dashboard-control-plane-view';
import type { DashboardView } from './dashboard-control-plane-view';

describe('DashboardView', () => {
  let element: DashboardView;
  let fetchStub: sinon.SinonStub;
  let connectStub: sinon.SinonStub;
  let subscribeStub: sinon.SinonStub;

  beforeEach(async () => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon
      .stub(window, 'fetch')
      .callsFake(async (input: RequestInfo | URL) => {
        const url = typeof input === 'string' ? input : input.toString();
        const json = (data: unknown) =>
          new Response(JSON.stringify(data), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });

        if (url.startsWith('/api/v1/account/gateway-usage/summary')) {
          return json({
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            total_requests: 22,
            successful_requests: 19,
            failed_requests: 3,
            token_usage: {
              prompt_tokens: 1000,
              completion_tokens: 500,
              total_tokens: 1500,
            },
            estimated_cost: 12.34,
            budget: {
              monthly_limit_usd: 50,
              soft_limit_usd: 40,
              current_spend_usd: 12.34,
              soft_limit_exceeded: false,
              hard_limit_exceeded: false,
            },
            requests_by_day: [],
            usage_by_model: [
              {
                ai_model_id: 'model-1',
                model_alias: 'gpt-4.1',
                provider_name: 'openai',
                request_count: 10,
                token_usage: {
                  prompt_tokens: 100,
                  completion_tokens: 50,
                  total_tokens: 150,
                },
                estimated_cost: 6.5,
              },
            ],
            usage_by_flow: [],
            usage_by_session: [
              {
                runtime_session_id: 'runtime-session-1',
                session_source_type: 'managed_agent',
                session_source_id: 'agent-1',
                flow_execution_id: null,
                flow_id: null,
                flow_name: null,
                session_reference: 'Agent Session',
                model_alias: 'gpt-4.1',
                provider_name: 'openai',
                request_count: 8,
                token_usage: {
                  prompt_tokens: 10,
                  completion_tokens: 5,
                  total_tokens: 15,
                },
                estimated_cost: 4.2,
                last_request_at: '2026-03-07T10:00:00Z',
              },
            ],
          });
        }

        if (url.startsWith('/api/v1/runtime-sessions')) {
          return json({
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            query: null,
            session_source_type: null,
            status: 'all',
            total: 1,
            limit: 12,
            offset: 0,
            items: [
              {
                id: 'runtime-session-1',
                session_source_type: 'managed_agent',
                session_source_id: 'agent-1',
                session_reference: 'Agent Session',
                runtime_principal_type: 'managed_agent',
                runtime_principal_id: 'agent-1',
                runtime_principal_name: 'Ops Agent',
                started_at: '2026-03-07T09:00:00Z',
                last_activity_at: '2026-03-07T10:05:00Z',
                ended_at: null,
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                latest_model_alias: 'gpt-4.1',
                latest_provider_name: 'openai',
                total_requests: 8,
                successful_requests: 7,
                failed_requests: 1,
                token_usage: {
                  prompt_tokens: 10,
                  completion_tokens: 5,
                  total_tokens: 15,
                },
                estimated_cost: 4.2,
                last_request_at: '2026-03-07T10:00:00Z',
              },
            ],
          });
        }

        if (url.startsWith('/api/v1/agents')) {
          return json({
            query: null,
            session_source_type: null,
            status: 'all',
            total: 1,
            limit: 12,
            offset: 0,
            items: [
              {
                id: 'agent-1',
                runtime_session_id: 'runtime-session-1',
                display_name: 'Ops Agent',
                session_source_type: 'managed_agent',
                session_source_id: 'agent-1',
                session_reference: 'Agent Session',
                enrolled_via: 'runtime_session_token',
                managed_mcp_servers: ['github'],
                last_seen_at: '2026-03-07T10:05:00Z',
                started_at: '2026-03-07T09:00:00Z',
                last_activity_at: '2026-03-07T10:05:00Z',
                ended_at: null,
                total_requests: 8,
                estimated_cost: 4.2,
                latest_model_alias: 'gpt-4.1',
                latest_provider_name: 'openai',
                last_request_at: '2026-03-07T10:00:00Z',
              },
            ],
          });
        }

        if (url.startsWith('/api/v1/account/gateway-usage/search')) {
          return json({
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            query: null,
            total: 2,
            limit: 12,
            offset: 0,
            items: [
              {
                api_usage_id: 'usage-1',
                timestamp: '2026-03-07T10:00:00Z',
                status_code: 502,
                outcome: 'error',
                endpoint: '/openai/v1/responses',
                method: 'POST',
                provider_name: 'openai',
                model_alias: 'gpt-4.1',
                flow_id: null,
                flow_name: null,
                flow_execution_id: null,
                runtime_session_id: 'runtime-session-1',
                session_source_type: 'managed_agent',
                session_source_id: 'agent-1',
                session_reference: 'Agent Session',
                runtime_principal_type: 'managed_agent',
                runtime_principal_id: 'agent-1',
                runtime_principal_name: 'Ops Agent',
                auth_subject_type: 'api_key',
                api_key_id: 'api-key-1',
                api_key_name: 'Runtime Session managed_agent:agent-1',
                estimated_cost: 0,
                token_usage: {
                  prompt_tokens: 0,
                  completion_tokens: 0,
                  total_tokens: 0,
                },
                excerpt: '',
                meta_data: {},
              },
            ],
          });
        }

        if (url.startsWith('/api/v1/audit-logs/grouped')) {
          return json({
            groups: [
              {
                correlation_id: null,
                outcome: 'failed',
                primary_event: {
                  id: 'audit-1',
                  action: 'model_gateway_request',
                  status: 'failed',
                  timestamp: '2026-03-07T10:00:00Z',
                  details: { requested_model: 'gpt-4.1' },
                },
                sub_events: [],
              },
            ],
            total: 1,
          });
        }

        return json({ detail: `Unhandled ${url}` });
      });

    connectStub = sinon.stub(unifiedWebSocketManager, 'connect').resolves();
    subscribeStub = sinon
      .stub(unifiedWebSocketManager, 'subscribe')
      .callsFake(() => () => undefined);

    element = await fixture(html`<dashboard-view></dashboard-view>`);
  });

  afterEach(() => {
    fetchStub.restore();
    connectStub.restore();
    subscribeStub.restore();
    localStorage.clear();
  });

  it('renders the AI control plane dashboard', async () => {
    await waitUntil(
      () => !element['loading'],
      'dashboard did not finish loading'
    );
    await element.updateComplete;

    const header = element.shadowRoot?.querySelector('view-header');
    expect(header?.getAttribute('headerText')).to.equal('AI Control Plane');
    expect(element.shadowRoot?.textContent).to.contain('Active agents');
    expect(element.shadowRoot?.textContent).to.contain('Gateway failures');
    expect(element.shadowRoot?.textContent).to.contain('Audit exceptions');
  });

  it('subscribes to realtime topics and fetches dashboard data', async () => {
    await waitUntil(
      () => !element['loading'],
      'dashboard did not finish loading'
    );

    expect(connectStub).to.have.been.calledOnce;
    expect(subscribeStub.callCount).to.equal(6);

    const urls = fetchStub.getCalls().map((call) => String(call.args[0]));
    expect(
      urls.some((url) =>
        url.startsWith('/api/v1/account/gateway-usage/summary')
      )
    ).to.be.true;
    expect(urls.some((url) => url.startsWith('/api/v1/runtime-sessions'))).to.be
      .true;
    expect(urls.some((url) => url.startsWith('/api/v1/agents'))).to.be.true;
    expect(urls.some((url) => url.startsWith('/api/v1/audit-logs/grouped'))).to
      .be.true;
  });
});
