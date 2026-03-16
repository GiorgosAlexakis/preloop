import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import './agents-view';
describe('AgentsView', () => {
    let fetchStub;
    beforeEach(() => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
        fetchStub = sinon.stub(window, 'fetch');
        fetchStub.callsFake(async (input) => {
            const url = typeof input === 'string' ? input : input.toString();
            if (url.startsWith('/api/v1/agents')) {
                return new Response(JSON.stringify({
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
                            display_name: 'Claude Code Workspace',
                            session_source_type: 'claude_code',
                            session_source_id: 'workspace-123',
                            session_reference: 'claude-session-abc',
                            enrolled_via: 'runtime_session_token',
                            managed_mcp_servers: ['github', 'jira'],
                            last_seen_at: '2026-03-10T10:00:00Z',
                            started_at: '2026-03-10T09:00:00Z',
                            last_activity_at: '2026-03-10T10:00:00Z',
                            ended_at: null,
                            total_requests: 3,
                            estimated_cost: 0.42,
                            latest_model_alias: 'openai/gpt-5',
                            latest_provider_name: 'openai',
                            last_request_at: '2026-03-10T09:58:00Z',
                        },
                    ],
                }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                });
            }
            return new Response('Not found', { status: 404 });
        });
    });
    afterEach(() => {
        fetchStub.restore();
        localStorage.clear();
    });
    it('renders enrolled agents and links to agent detail', async () => {
        const el = await fixture(html `<agents-view></agents-view>`);
        await waitUntil(() => !el.shadowRoot?.querySelector('sl-spinner'));
        const text = el.shadowRoot?.textContent || '';
        expect(text).to.contain('Claude Code Workspace');
        expect(text).to.contain('github');
        expect(text).to.contain('jira');
        expect(text).to.contain('openai/gpt-5');
        const link = el.shadowRoot?.querySelector('a[href*="/console/agents/"]');
        expect(link).to.exist;
        expect(link?.getAttribute('href')).to.contain('/console/agents/agent-1');
    });
});
