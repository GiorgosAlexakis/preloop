import { fixture, html, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './ai-models-view';
import type { AIModelsView } from './ai-models-view';

describe('AIModelsView', () => {
  let fetchStub: sinon.SinonStub;

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

    const nameLink = element.shadowRoot?.querySelector(
      'a.model-link[href="/console/settings/ai-models/model-1"]'
    );
    const viewButton = element.shadowRoot?.querySelector(
      'sl-button[href="/console/settings/ai-models/model-1"]'
    );

    expect(nameLink).to.not.equal(null);
    expect(viewButton).to.not.equal(null);
  });
});
