import { fixture, html, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './api-usage-view';
import type { ApiUsageView } from './api-usage-view';

describe('ApiUsageView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.startsWith('/api/v1/account/gateway-usage/summary')) {
        return new Response(
          JSON.stringify({
            period_start: '2026-02-08T00:00:00Z',
            period_end: '2026-03-09T23:59:59Z',
            total_requests: 42,
            successful_requests: 39,
            failed_requests: 3,
            token_usage: {
              prompt_tokens: 12000,
              completion_tokens: 4500,
              total_tokens: 16500,
            },
            estimated_cost: 3.456,
            budget: {
              monthly_limit_usd: 50,
              soft_limit_usd: 25,
              current_spend_usd: 12.5,
              soft_limit_exceeded: false,
              hard_limit_exceeded: false,
            },
            requests_by_day: [
              {
                date: '2026-03-08',
                request_count: 12,
                estimated_cost: 1.23,
                total_tokens: 5000,
              },
              {
                date: '2026-03-09',
                request_count: 30,
                estimated_cost: 2.226,
                total_tokens: 11500,
              },
            ],
            usage_by_model: [
              {
                ai_model_id: 'model-1',
                model_alias: 'openai/gpt-5',
                provider_name: 'OpenAI',
                request_count: 28,
                token_usage: {
                  prompt_tokens: 8000,
                  completion_tokens: 3200,
                  total_tokens: 11200,
                },
                estimated_cost: 2.75,
              },
              {
                ai_model_id: 'model-2',
                model_alias: 'anthropic/claude-sonnet-4',
                provider_name: 'Anthropic',
                request_count: 14,
                token_usage: {
                  prompt_tokens: 4000,
                  completion_tokens: 1300,
                  total_tokens: 5300,
                },
                estimated_cost: 0.706,
              },
            ],
            usage_by_flow: [
              {
                flow_id: 'flow-1',
                flow_name: 'Triage Assistant',
                request_count: 24,
                token_usage: {
                  prompt_tokens: 7000,
                  completion_tokens: 2500,
                  total_tokens: 9500,
                },
                estimated_cost: 1.98,
              },
              {
                flow_id: 'flow-2',
                flow_name: 'PR Reviewer',
                request_count: 18,
                token_usage: {
                  prompt_tokens: 5000,
                  completion_tokens: 2000,
                  total_tokens: 7000,
                },
                estimated_cost: 1.476,
              },
            ],
            usage_by_session: [
              {
                runtime_session_id: 'runtime-session-1',
                runtime_session_name: 'Triage Assistant',
                session_source_type: 'flow_execution',
                session_source_id: 'execution-1',
                runtime_principal_type: 'flow_execution',
                runtime_principal_id: 'execution-1',
                runtime_principal_name: 'Triage Assistant',
                flow_execution_id: 'execution-1',
                flow_id: 'flow-1',
                flow_name: 'Triage Assistant',
                session_reference: 'session-abc123',
                model_alias: 'openai/gpt-5',
                provider_name: 'OpenAI',
                request_count: 16,
                token_usage: {
                  prompt_tokens: 5000,
                  completion_tokens: 1900,
                  total_tokens: 6900,
                },
                estimated_cost: 1.64,
                last_activity_at: '2026-03-09T19:15:00Z',
                last_request_at: '2026-03-09T19:15:00Z',
              },
              {
                runtime_session_id: 'runtime-session-2',
                runtime_session_name: 'Workspace Agent',
                session_source_type: 'codex',
                session_source_id: 'codex-run-1',
                runtime_principal_type: 'codex',
                runtime_principal_id: 'workspace-agent',
                runtime_principal_name: 'Workspace Agent',
                flow_execution_id: null,
                flow_id: null,
                flow_name: null,
                session_reference: 'terminal-session-42',
                model_alias: 'anthropic/claude-sonnet-4',
                provider_name: 'Anthropic',
                request_count: 4,
                token_usage: {
                  prompt_tokens: 1000,
                  completion_tokens: 400,
                  total_tokens: 1400,
                },
                estimated_cost: 0.12,
                started_at: '2026-03-09T18:00:00Z',
                last_activity_at: '2026-03-09T20:00:00Z',
                last_request_at: '2026-03-09T20:00:00Z',
                ended_at: null,
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

  it('renders account gateway usage totals with runtime session breakdowns', async () => {
    const element = (await fixture(
      html`<api-usage-view></api-usage-view>`
    )) as ApiUsageView;

    await waitUntil(
      () => !(element as any).loading && (element as any).summary !== null,
      'API usage view did not finish loading'
    );
    await element.updateComplete;

    const content = element.shadowRoot?.textContent || '';

    expect(content).to.contain('Gateway Usage Filters');
    expect(content).to.contain('42');
    expect(content).to.contain('$3.46');
    expect(content).to.contain('16,500');
    expect(content).to.contain('92.9%');
    expect(content).to.contain('openai/gpt-5');
    expect(content).to.contain('Triage Assistant');
    expect(content).to.contain('Recent Runtime Sessions');
    expect(content).to.contain('execution-1');
    expect(content).to.contain('session-abc123');
    expect(content).to.contain('Workspace Agent');
    expect(content).to.contain('Source: Codex');
    expect(content).to.contain('codex-run-1');
    expect(content).to.contain('Budget Snapshot');
    expect(content).to.contain('$12.50');

    const flowExecutionLink = element.shadowRoot?.querySelector(
      'a[href="/console/flows/executions/execution-1"]'
    );
    const nonFlowLink = element.shadowRoot?.querySelector(
      'a[href="/console/flows/executions/codex-run-1"]'
    );

    expect(flowExecutionLink).to.not.equal(null);
    expect(nonFlowLink).to.equal(null);

    const summaryCall = fetchStub
      .getCalls()
      .find((call) =>
        String(call.args[0]).startsWith('/api/v1/account/gateway-usage/summary')
      );

    expect(summaryCall).to.not.equal(undefined);
    expect(String(summaryCall?.args[0])).to.contain('start_date=');
    expect(String(summaryCall?.args[0])).to.contain('end_date=');
  });
});
