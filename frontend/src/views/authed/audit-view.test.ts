import { expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './audit-view';
import type { AuditView } from './audit-view';

describe('AuditView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url === '/api/v1/users') {
        return new Response(
          JSON.stringify([
            {
              id: 'user-1',
              username: 'alice',
              email: 'alice@example.com',
              full_name: 'Alice Example',
            },
          ]),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url.startsWith('/api/v1/audit-logs/grouped?')) {
        return new Response(
          JSON.stringify({
            groups: [
              {
                correlation_id: null,
                outcome: 'created',
                primary_event: {
                  id: 'audit-1',
                  account_id: 'account-1',
                  user_id: 'user-1',
                  action: 'runtime_session_created',
                  resource_type: 'runtime_session',
                  resource_id: 'runtime-session-1',
                  status: 'created',
                  ip_address: null,
                  user_agent: null,
                  timestamp: '2026-03-10T10:00:00Z',
                  details: {
                    runtime_session_id: 'runtime-session-1',
                    session_reference: 'claude-session-42',
                    session_source_type: 'claude_code',
                    session_source_id: 'workspace-42',
                    runtime_principal_name: 'Claude Workspace',
                    api_key_name: 'Claude Workspace Token',
                  },
                },
                sub_events: [],
              },
              {
                correlation_id: 'corr-1',
                outcome: 'approved',
                primary_event: {
                  id: 'audit-2',
                  account_id: 'account-1',
                  user_id: 'user-1',
                  action: 'tool_call',
                  resource_type: 'tool',
                  resource_id: 'search',
                  status: 'executed',
                  ip_address: null,
                  user_agent: null,
                  timestamp: '2026-03-10T10:02:00Z',
                  details: {
                    tool_name: 'search',
                    tool_args: { query: 'deployment risk' },
                    duration_ms: 125,
                    correlation_id: 'corr-1',
                    runtime_session_id: 'runtime-session-1',
                    api_key_name: 'Claude Workspace Token',
                  },
                },
                sub_events: [
                  {
                    id: 'audit-3',
                    action: 'policy_allow',
                    status: 'allow',
                    timestamp: '2026-03-10T10:01:59Z',
                    details: {
                      decision: 'allow',
                      correlation_id: 'corr-1',
                      api_key_name: 'Claude Workspace Token',
                    },
                  },
                ],
              },
              {
                correlation_id: null,
                outcome: 'budget_denied',
                primary_event: {
                  id: 'audit-4',
                  account_id: 'account-1',
                  user_id: 'user-1',
                  action: 'model_gateway_request',
                  resource_type: 'model_gateway',
                  resource_id: 'openai/gpt-5',
                  status: 'budget_denied',
                  ip_address: null,
                  user_agent: null,
                  timestamp: '2026-03-10T10:03:00Z',
                  details: {
                    endpoint: '/openai/v1/responses',
                    endpoint_kind: 'responses',
                    status_code: 403,
                    requested_model: 'openai/gpt-5',
                    model_alias: 'openai/gpt-5',
                    provider_name: 'openai',
                    gateway_provider: 'preloop',
                    runtime_session_id: 'runtime-session-1',
                    api_key_name: 'Claude Workspace Token',
                    error_detail:
                      'Model gateway budget exceeded: account monthly limit reached',
                    error_type: 'budget_limit_exceeded',
                    budget: { hard_limit_exceeded: true, account_limit_usd: 5 },
                  },
                },
                sub_events: [],
              },
            ],
            total: 3,
            skip: 0,
            limit: 50,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
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

  it('renders expandable runtime session events and API token attribution', async () => {
    const element = document.createElement('audit-view') as AuditView;
    document.body.appendChild(element);

    await waitUntil(
      () => !(element as any)._loading,
      'Audit view did not finish loading'
    );
    await element.updateComplete;

    const content = element.shadowRoot?.textContent || '';
    expect(content).to.contain('Audit Timeline');
    expect(content).to.contain('Runtime session started');
    expect(content).to.contain('search');
    expect(content).to.contain('Alice Example via Claude Workspace Token');

    const rows = Array.from(
      element.shadowRoot?.querySelectorAll('.primary-row') || []
    ) as HTMLElement[];
    rows[0].click();
    await element.updateComplete;

    const expandedContent = element.shadowRoot?.textContent || '';
    expect(expandedContent).to.contain('claude-session-42');
    expect(expandedContent).to.contain('Claude Workspace');
    expect(expandedContent).to.contain('Runtime Session Id');

    document.body.removeChild(element);
  });

  it('renders gateway request failures with readable labels and details', async () => {
    const element = document.createElement('audit-view') as AuditView;
    document.body.appendChild(element);

    await waitUntil(
      () => !(element as any)._loading,
      'Audit view did not finish loading'
    );
    await element.updateComplete;

    const rows = Array.from(
      element.shadowRoot?.querySelectorAll('.primary-row') || []
    ) as HTMLElement[];
    const gatewayRow = rows.find((row) =>
      row.textContent?.includes('budget denied: openai/gpt-5')
    );

    expect(gatewayRow).to.exist;
    expect(element.shadowRoot?.textContent || '').to.contain('Budget Denied');

    gatewayRow?.click();
    await element.updateComplete;

    const expandedContent = element.shadowRoot?.textContent || '';
    expect(expandedContent).to.contain('Status Code');
    expect(expandedContent).to.contain('403');
    expect(expandedContent).to.contain('budget_limit_exceeded');
    expect(expandedContent).to.contain('Claude Workspace Token');

    document.body.removeChild(element);
  });
});
