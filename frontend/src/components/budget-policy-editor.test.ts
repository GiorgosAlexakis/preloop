import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import './budget-policy-editor.ts';
import type { BudgetPolicyEditor } from './budget-policy-editor';

describe('BudgetPolicyEditor', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');
    fetchStub = sinon.stub(window, 'fetch');
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  const stubBillingFetch = (opts?: { failModels?: boolean }) => {
    fetchStub.callsFake(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method || 'GET').toUpperCase();

        if (url.includes('/api/v1/features')) {
          return new Response(JSON.stringify({ features: { billing: true } }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/v1/auth/users/me')) {
          return new Response(JSON.stringify({ email: 'owner@example.com' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/v1/users?')) {
          return new Response(
            JSON.stringify({ users: [], total: 0, skip: 0, limit: 100 }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/v1/ai-models') && opts?.failModels) {
          return new Response('models unavailable', { status: 500 });
        }
        if (url.includes('/api/v1/ai-models')) {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.includes('/api/v1/agents')) {
          return new Response(
            JSON.stringify({
              query: null,
              agent_kind: null,
              last_seen_after: null,
              status: 'all',
              total: 0,
              limit: 100,
              offset: 0,
              items: [],
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } }
          );
        }
        if (url.includes('/api/v1/budget/policies') && method === 'GET') {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response('{}', { status: 200 });
      }
    );
  };

  it('renders budget policy region when billing is enabled', async () => {
    stubBillingFetch();
    const element = (await fixture(
      html`<budget-policy-editor></budget-policy-editor>`
    )) as BudgetPolicyEditor;
    await waitUntil(() =>
      Boolean(element.shadowRoot?.querySelector('#budget-policy-editor-title'))
    );

    const title = element.shadowRoot?.querySelector(
      '#budget-policy-editor-title'
    );
    expect(title?.textContent?.trim()).to.equal('Budget Policies');
    expect(element.shadowRoot?.querySelector('[role="region"]')).to.exist;
  });

  it('surfaces subject load failures instead of failing silently', async () => {
    stubBillingFetch({ failModels: true });
    const element = (await fixture(
      html`<budget-policy-editor></budget-policy-editor>`
    )) as BudgetPolicyEditor;
    await waitUntil(() =>
      Boolean(element.shadowRoot?.querySelector('#budget-policy-editor-title'))
    );

    await element.loadSubjects();
    await element.updateComplete;

    expect(element.shadowRoot?.querySelector('sl-alert[role="alert"]')).to
      .exist;
  });
});
