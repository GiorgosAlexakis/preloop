import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import '../../components/view-header.ts';
import './dashboard-view';
import type { DashboardView } from './dashboard-view';

describe('DashboardView', () => {
  let element: DashboardView;
  let fetchStub: sinon.SinonStub;

  function createFetchStub() {
    return sinon
      .stub(window, 'fetch')
      .callsFake(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method || 'GET').toUpperCase();

        const json = (data: unknown) =>
          new Response(JSON.stringify(data), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });

        if (url.includes('/api/v1/trackers') && method === 'GET') {
          return json([]);
        }
        if (url.includes('/api/v1/auth/api-usage') && method === 'GET') {
          return json({
            total_requests: 42,
            issues_created: 10,
            issues_updated: 5,
            issues_closed: 2,
          });
        }
        if (url.includes('/api/v1/issues-count') && method === 'GET') {
          return json({ total_issues: 0 });
        }
        if (url.includes('/api/v1/mcp-servers') && method === 'GET') {
          return json([]);
        }
        if (url.includes('/api/v1/tools') && method === 'GET') {
          return json([]);
        }
        if (
          url.includes('/api/v1/flows') &&
          !url.includes('executions') &&
          method === 'GET'
        ) {
          return json([]);
        }
        if (url.includes('/api/v1/flows/executions') && method === 'GET') {
          return json([]);
        }
        if (url.includes('/api/v1/approval-requests') && method === 'GET') {
          return json([]);
        }
        if (url.includes('/api/v1/users') && method === 'GET') {
          return json({ users: [], total: 0, skip: 0, limit: 0 });
        }
        if (url.includes('/api/v1/ai-models') && method === 'GET') {
          return json([]);
        }

        return json({ detail: `Unhandled: ${method} ${url}` });
      });
  }

  beforeEach(async () => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    (window as any).BRAND_CONFIG = {
      name: 'Test',
      domain: 'test.example.com',
      edition: 'selfhosted',
      company: { legal_name: 'Test', address: '', city: '' },
      branding: {
        logo_light: '',
        logo_dark: '',
        favicon: '',
        primary_color: '',
        gradient_product: '',
        gradient_ai: '',
      },
      social: { twitter: '', linkedin: '', instagram: '' },
    };

    fetchStub = createFetchStub();
    element = await fixture(html`<dashboard-view></dashboard-view>`);
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
    delete (window as any).BRAND_CONFIG;
  });

  it('renders the dashboard', async () => {
    await waitUntil(
      () => !(element as any).isLoading,
      'Dashboard did not finish loading'
    );
    await element.updateComplete;

    const header = element.shadowRoot?.querySelector('view-header');
    expect(header).to.exist;
    expect(header?.getAttribute('headerText')).to.equal('Overview');
  });

  it('shows stats/placeholders when data is loaded', async () => {
    await waitUntil(
      () => !(element as any).isLoading,
      'Dashboard did not finish loading'
    );
    await element.updateComplete;

    const keyMetrics = element.shadowRoot?.querySelector('.summary-list');
    expect(keyMetrics).to.exist;

    const mcpCard = element.shadowRoot?.querySelector('sl-card');
    expect(mcpCard).to.exist;
  });

  it('stubs fetch for dashboard API calls', async () => {
    await waitUntil(
      () => !(element as any).isLoading,
      'Dashboard did not finish loading'
    );

    expect(fetchStub).to.have.been.called;
    const urls = fetchStub.getCalls().map((c) => String(c.args[0]));
    expect(urls.some((u) => u.includes('/api/v1/trackers'))).to.be.true;
    expect(urls.some((u) => u.includes('/api/v1/flows'))).to.be.true;
    expect(urls.some((u) => u.includes('/api/v1/tools'))).to.be.true;
  });
});
