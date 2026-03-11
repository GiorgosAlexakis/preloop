import { fixture, html, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import { unifiedWebSocketManager } from '../../../services/unified-websocket-manager';
import './ai-models-view';
import type { AIModelsView } from './ai-models-view';

describe('AIModelsView', () => {
  let fetchStub: sinon.SinonStub;
  let connectStub: sinon.SinonStub;
  let subscribeStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url === '/api/v1/ai-models') {
        return new Response(
          JSON.stringify([
            {
              id: 'model-1',
              name: 'Claude Sonnet Primary',
              provider_name: 'Anthropic',
              model_identifier: 'claude-sonnet-4',
              is_default: true,
              created_at: '2026-03-01T10:00:00Z',
              updated_at: '2026-03-09T18:30:00Z',
            },
          ]),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url.startsWith('/api/v1/ai-models/model-1/summary')) {
        return new Response(
          JSON.stringify({
            ai_model_id: 'model-1',
            model_name: 'Claude Sonnet Primary',
            provider_name: 'Anthropic',
            model_identifier: 'claude-sonnet-4',
            period_start: '2026-02-09T00:00:00Z',
            period_end: '2026-03-09T23:59:59Z',
            total_requests: 42,
            successful_requests: 40,
            failed_requests: 2,
            token_usage: {
              prompt_tokens: 1200,
              completion_tokens: 800,
              total_tokens: 2000,
            },
            estimated_cost: 12.34,
            requests_by_day: [],
            usage_by_session: [],
          }),
          {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }

      if (url.startsWith('/api/v1/ai-models/model-1/runtime-sessions')) {
        return new Response(
          JSON.stringify({
            period_start: '2026-02-09T00:00:00Z',
            period_end: '2026-03-09T23:59:59Z',
            query: null,
            session_source_type: null,
            status: 'active',
            total: 3,
            limit: 100,
            offset: 0,
            items: [],
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

    connectStub = sinon.stub(unifiedWebSocketManager, 'connect').resolves();
    subscribeStub = sinon
      .stub(unifiedWebSocketManager, 'subscribe')
      .callsFake(() => () => undefined);
  });

  afterEach(() => {
    fetchStub.restore();
    connectStub.restore();
    subscribeStub.restore();
    localStorage.clear();
  });

  it('links each configured model to its observability detail page', async () => {
    const element = (await fixture(
      html`<ai-models-view></ai-models-view>`
    )) as AIModelsView;

    await waitUntil(
      () => !(element as any).isLoading,
      'AI models view did not finish loading'
    );
    await element.updateComplete;

    const content = element.shadowRoot?.textContent || '';
    expect(content).to.contain('Claude Sonnet Primary');
    expect(content).to.contain('View');
    expect(content).to.contain('Fleet spend');
    expect(content).to.contain('$12.34');
    expect(content).to.contain('42 requests');
    expect(content).to.contain('3 active sessions');
    expect(content).to.contain('Attention');

    const nameLink = element.shadowRoot?.querySelector(
      'a.model-link[href="/console/settings/ai-models/model-1"]'
    );
    const viewButton = element.shadowRoot?.querySelector(
      'sl-button[href="/console/settings/ai-models/model-1"]'
    );

    expect(nameLink).to.not.equal(null);
    expect(viewButton).to.not.equal(null);
    expect(connectStub).to.have.been.calledOnce;
    expect(subscribeStub.callCount).to.equal(5);
  });
});
