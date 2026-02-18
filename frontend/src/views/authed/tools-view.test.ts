import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './tools-view';
import type { ToolsView } from './tools-view';

describe('ToolsView (approvals + conditions)', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    // fetchWithAuth requires an access token to exist
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');

    const tool = {
      name: 'example_tool',
      description: 'Example tool',
      source: 'builtin',
      source_id: null,
      source_name: 'Built-in',
      schema: {},
      is_enabled: true,
      is_supported: true,
      approval_policy_id: null,
      has_approval_condition: false,
      config_id: null,
    };

    const defaultPolicy = {
      id: 'policy-1',
      name: 'Default',
      description: 'Default policy',
      approval_type: 'standard',
      is_default: true,
    };

    fetchStub.callsFake(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method || 'GET').toUpperCase();

        // Initial ToolsView.loadData() requests
        if (url.endsWith('/api/v1/tools') && method === 'GET') {
          return new Response(JSON.stringify([tool]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        if (url.endsWith('/api/v1/mcp-servers') && method === 'GET') {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        if (url.endsWith('/api/v1/approval-policies') && method === 'GET') {
          return new Response(JSON.stringify([defaultPolicy]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        if (url.endsWith('/api/v1/features') && method === 'GET') {
          return new Response(JSON.stringify({ features: {} }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        // ToolListItem / loadCurrentUser() request
        if (url.endsWith('/api/v1/auth/users/me') && method === 'GET') {
          return new Response(JSON.stringify({ id: 'user-1' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        // Regression path: enable approval => create tool configuration
        if (url.endsWith('/api/v1/tool-configurations') && method === 'POST') {
          return new Response(JSON.stringify({ id: 'cfg-1' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }

        // Saving an access rule uses the dedicated endpoint
        if (
          url.endsWith('/api/v1/tool-configurations/cfg-1/access-rules') &&
          method === 'POST'
        ) {
          return new Response(
            JSON.stringify({ id: 'rule-1', action: 'require_approval' }),
            {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }
          );
        }

        return new Response(
          JSON.stringify({ detail: `Unhandled request: ${method} ${url}` }),
          {
            status: 500,
            headers: { 'Content-Type': 'application/json' },
          }
        );
      }
    );
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  it('does not create tool configuration twice when adding a rule immediately after toggling enabled', async () => {
    const element = (await fixture(
      html`<tools-view></tools-view>`
    )) as ToolsView;

    await waitUntil(
      () => (element as any).tools?.length === 1,
      'Tools did not load'
    );
    await element.updateComplete;

    const toolItem = element.shadowRoot?.querySelector(
      'tool-list-item'
    ) as HTMLElement;
    expect(toolItem).to.exist;

    expect((element as any).tools[0].config_id).to.equal(null);

    // Step 1: toggle enabled (auto-creates config since config_id is null)
    toolItem.dispatchEvent(
      new CustomEvent('toggle-enabled', {
        detail: { tool: (element as any).tools[0] },
        bubbles: true,
        composed: true,
      })
    );

    await waitUntil(
      () => (element as any).tools?.[0]?.config_id === 'cfg-1',
      'Tool config_id was not set after toggling enabled'
    );
    await element.updateComplete;

    const updatedTool = (element as any).tools[0];
    expect(updatedTool.config_id).to.equal('cfg-1');

    // Step 2: immediately save a rule - must NOT try to create config again
    toolItem.dispatchEvent(
      new CustomEvent('save-rule', {
        detail: {
          tool: updatedTool,
          existingRule: null,
          formData: {
            action: 'require_approval',
            condition_expression: null,
            condition_type: 'cel',
            description: null,
            is_enabled: true,
            approval_policy_id: 'policy-1',
          },
        },
        bubbles: true,
        composed: true,
      })
    );

    await new Promise((r) => setTimeout(r, 0));
    await element.updateComplete;

    const toolConfigCreateCalls = fetchStub.getCalls().filter((c) => {
      const url = String(c.args[0]);
      const method = String(
        (c.args[1] as RequestInit | undefined)?.method || 'GET'
      ).toUpperCase();
      return url.endsWith('/api/v1/tool-configurations') && method === 'POST';
    });

    expect(toolConfigCreateCalls.length).to.equal(1);
    expect((element as any).error).to.equal(null);
  });
});

describe('ToolsView – filter persistence', () => {
  let fetchStub: sinon.SinonStub;

  const STORAGE_KEY = 'preloop:tools-filter';

  function stubLoadData() {
    fetchStub.callsFake(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method || 'GET').toUpperCase();

        if (url.endsWith('/api/v1/tools') && method === 'GET') {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.endsWith('/api/v1/mcp-servers') && method === 'GET') {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.endsWith('/api/v1/approval-policies') && method === 'GET') {
          return new Response(JSON.stringify([]), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.endsWith('/api/v1/features') && method === 'GET') {
          return new Response(JSON.stringify({ features: {} }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        if (url.endsWith('/api/v1/auth/users/me') && method === 'GET') {
          return new Response(JSON.stringify({ id: 'user-1' }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        }
        return new Response(JSON.stringify({}), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    );
  }

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');
    fetchStub = sinon.stub(window, 'fetch');
    stubLoadData();
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  it('defaults to "available" filter when no saved preference', async () => {
    const el = (await fixture(html`<tools-view></tools-view>`)) as ToolsView;
    await waitUntil(() => !(el as any).loading, 'Still loading');
    await el.updateComplete;

    expect((el as any).activeFilter).to.equal('available');
  });

  it('restores saved filter from localStorage on mount', async () => {
    localStorage.setItem(STORAGE_KEY, 'prelooped');

    const el = (await fixture(html`<tools-view></tools-view>`)) as ToolsView;
    await waitUntil(() => !(el as any).loading, 'Still loading');
    await el.updateComplete;

    expect((el as any).activeFilter).to.equal('prelooped');
  });

  it('persists filter to localStorage when changed', async () => {
    const el = (await fixture(html`<tools-view></tools-view>`)) as ToolsView;
    await waitUntil(() => !(el as any).loading, 'Still loading');
    await el.updateComplete;

    (el as any)._setFilter('prelooped');
    expect(localStorage.getItem(STORAGE_KEY)).to.equal('prelooped');
    expect((el as any).activeFilter).to.equal('prelooped');
  });

  it('survives round-trip: set filter → remount → filter restored', async () => {
    // Mount first instance, set filter
    const el1 = (await fixture(html`<tools-view></tools-view>`)) as ToolsView;
    await waitUntil(() => !(el1 as any).loading, 'Still loading');
    (el1 as any)._setFilter('mcp');
    el1.remove();

    // Mount second instance — should pick up the saved filter
    const el2 = (await fixture(html`<tools-view></tools-view>`)) as ToolsView;
    await waitUntil(() => !(el2 as any).loading, 'Still loading');
    await el2.updateComplete;

    expect((el2 as any).activeFilter).to.equal('mcp');
  });
});
