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

        // ToolCard.loadCurrentUser() request
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

        // Saving the condition uses the dedicated endpoint
        if (
          url.endsWith('/api/v1/tool-configurations/cfg-1/condition') &&
          method === 'PUT'
        ) {
          return new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
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

  it('does not create tool configuration twice when adding a condition immediately after enabling approvals', async () => {
    const element = (await fixture(
      html`<tools-view></tools-view>`
    )) as ToolsView;

    await waitUntil(
      () => (element as any).tools?.length === 1,
      'Tools did not load'
    );
    await element.updateComplete;

    const toolCard = element.shadowRoot?.querySelector(
      'tool-card'
    ) as HTMLElement;
    expect(toolCard).to.exist;

    expect((element as any).tools[0].config_id).to.equal(null);

    // Step 1: enable approvals via default policy (auto-creates config)
    toolCard.dispatchEvent(
      new CustomEvent('use-default-policy', {
        detail: { tool: (element as any).tools[0] },
        bubbles: true,
        composed: true,
      })
    );

    await waitUntil(
      () => (element as any).tools?.[0]?.config_id === 'cfg-1',
      'Tool config_id was not set after applying default policy'
    );
    await element.updateComplete;

    const updatedTool = (element as any).tools[0];
    expect(updatedTool.config_id).to.equal('cfg-1');

    // Step 2: immediately save a condition - must NOT try to create config again
    toolCard.dispatchEvent(
      new CustomEvent('save-condition', {
        detail: { tool: updatedTool, condition: 'true' },
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
