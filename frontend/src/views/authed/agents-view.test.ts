import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';

import './agents-view.ts';
import type { AgentsView } from './agents-view';

describe('AgentsView', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');

    fetchStub = sinon.stub(window, 'fetch');
    fetchStub.callsFake(async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input.toString();

      if (url.startsWith('/api/v1/agents')) {
        return new Response(
          JSON.stringify({
            query: null,
            session_source_type: null,
            status: 'all',
            total: 1,
            limit: 50,
            offset: 0,
            items: [
              {
                id: 'agent-1',
                runtime_session_id: 'runtime-session-1',
                owner_user_id: null,
                owner_username: null,
                owner_email: null,
                display_name: 'Claude Code Workspace',
                session_source_type: 'claude_code',
                session_source_id: 'workspace-123',
                session_reference: 'claude-session-abc',
                enrolled_via: 'runtime_session_token',
                managed_mcp_servers: ['github', 'jira'],
                lifecycle_state: 'active',
                lifecycle_reason: null,
                lifecycle_updated_at: '2026-03-10T10:00:00Z',
                is_active_now: true,
                activity_status: 'active_now',
                last_seen_at: '2026-03-10T10:00:00Z',
                started_at: '2026-03-10T09:00:00Z',
                last_activity_at: '2026-03-10T10:00:00Z',
                ended_at: null,
                total_requests: 3,
                estimated_cost: 0.42,
                latest_model_alias: 'openai/gpt-5',
                latest_provider_name: 'openai',
                last_request_at: '2026-03-10T09:58:00Z',
                mcp_proxy_configured: true,
                model_gateway_configured: true,
                onboarding_state: 'fully_onboarded',
                live_validation_supported: true,
                live_validation_passed: true,
                live_validation_status: 'passed',
                last_validated_at: '2026-03-10T10:01:00Z',
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

  it('renders enrolled agents and links to agent detail', async () => {
    const el = await fixture<AgentsView>(html`<agents-view></agents-view>`);

    await waitUntil(() => !el.shadowRoot?.querySelector('sl-spinner'));

    const text = el.shadowRoot?.textContent || '';
    expect(text).to.contain('Claude Code Workspace');
    expect(text).to.contain('github');
    expect(text).to.contain('jira');
    expect(text).to.contain('openai/gpt-5');
    expect(text).to.contain('Fully onboarded');
    expect(text).to.contain('Live validated');
    expect(text).to.contain('Remove');

    const link = el.shadowRoot?.querySelector('a[href*="/console/agents/"]');
    expect(link).to.exist;
    expect(link?.getAttribute('href')).to.contain('/console/agents/agent-1');
  });
});
