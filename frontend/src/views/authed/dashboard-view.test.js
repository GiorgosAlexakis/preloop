import { expect, fixture, html, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import '../../components/view-header.ts';
import { unifiedWebSocketManager } from '../../services/unified-websocket-manager';
import './dashboard-control-plane-view';
describe('DashboardView', () => {
    let fetchStub;
    let connectStub;
    let subscribeStub;
    let gatewaySummaryResponse;
    let runtimeSessionsResponse;
    let agentsResponse;
    let gatewaySearchResponse;
    let auditResponse;
    let trackersResponse;
    let apiUsageResponse;
    let issueCountResponse;
    let mcpServersResponse;
    let toolsResponse;
    let flowsResponse;
    let flowExecutionsResponse;
    let pendingApprovalRequestsResponse;
    let allApprovalRequestsResponse;
    let aiModelsResponse;
    let usersResponse;
    beforeEach(() => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
        gatewaySummaryResponse = {
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            total_requests: 22,
            successful_requests: 19,
            failed_requests: 3,
            token_usage: {
                prompt_tokens: 1000,
                completion_tokens: 500,
                total_tokens: 1500,
            },
            estimated_cost: 12.34,
            budget: {
                monthly_limit_usd: 50,
                soft_limit_usd: 40,
                current_spend_usd: 12.34,
                soft_limit_exceeded: false,
                hard_limit_exceeded: false,
            },
            requests_by_day: [],
            usage_by_model: [
                {
                    ai_model_id: 'model-1',
                    model_alias: 'gpt-4.1',
                    provider_name: 'openai',
                    request_count: 10,
                    token_usage: {
                        prompt_tokens: 100,
                        completion_tokens: 50,
                        total_tokens: 150,
                    },
                    estimated_cost: 6.5,
                },
            ],
            usage_by_flow: [],
            usage_by_session: [
                {
                    runtime_session_id: 'runtime-session-1',
                    session_source_type: 'managed_agent',
                    session_source_id: 'agent-1',
                    flow_execution_id: null,
                    flow_id: null,
                    flow_name: null,
                    session_reference: 'Agent Session',
                    model_alias: 'gpt-4.1',
                    provider_name: 'openai',
                    request_count: 8,
                    token_usage: {
                        prompt_tokens: 10,
                        completion_tokens: 5,
                        total_tokens: 15,
                    },
                    estimated_cost: 4.2,
                    last_request_at: '2026-03-07T10:00:00Z',
                },
            ],
        };
        runtimeSessionsResponse = {
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            query: null,
            session_source_type: null,
            status: 'all',
            total: 1,
            limit: 12,
            offset: 0,
            items: [
                {
                    id: 'runtime-session-1',
                    session_source_type: 'managed_agent',
                    session_source_id: 'agent-1',
                    session_reference: 'Agent Session',
                    runtime_principal_type: 'managed_agent',
                    runtime_principal_id: 'agent-1',
                    runtime_principal_name: 'Ops Agent',
                    started_at: '2026-03-07T09:00:00Z',
                    last_activity_at: '2026-03-07T10:05:00Z',
                    ended_at: null,
                    flow_id: null,
                    flow_name: null,
                    flow_execution_id: null,
                    latest_model_alias: 'gpt-4.1',
                    latest_provider_name: 'openai',
                    total_requests: 8,
                    successful_requests: 7,
                    failed_requests: 1,
                    token_usage: {
                        prompt_tokens: 10,
                        completion_tokens: 5,
                        total_tokens: 15,
                    },
                    estimated_cost: 4.2,
                    last_request_at: '2026-03-07T10:00:00Z',
                    activity_status: 'active_now',
                },
            ],
        };
        agentsResponse = {
            query: null,
            session_source_type: null,
            status: 'all',
            total: 1,
            limit: 12,
            offset: 0,
            items: [
                {
                    id: 'agent-1',
                    runtime_session_id: 'runtime-session-1',
                    display_name: 'Ops Agent',
                    session_source_type: 'managed_agent',
                    session_source_id: 'agent-1',
                    session_reference: 'Agent Session',
                    enrolled_via: 'runtime_session_token',
                    managed_mcp_servers: ['github'],
                    last_seen_at: '2026-03-07T10:05:00Z',
                    started_at: '2026-03-07T09:00:00Z',
                    last_activity_at: '2026-03-07T10:05:00Z',
                    ended_at: null,
                    total_requests: 8,
                    estimated_cost: 4.2,
                    latest_model_alias: 'gpt-4.1',
                    latest_provider_name: 'openai',
                    last_request_at: '2026-03-07T10:00:00Z',
                    activity_status: 'active_now',
                },
            ],
        };
        gatewaySearchResponse = {
            period_start: '2026-03-01T00:00:00Z',
            period_end: '2026-03-31T00:00:00Z',
            query: null,
            total: 2,
            limit: 12,
            offset: 0,
            items: [
                {
                    api_usage_id: 'usage-1',
                    timestamp: '2026-03-07T10:00:00Z',
                    status_code: 502,
                    outcome: 'error',
                    endpoint: '/openai/v1/responses',
                    method: 'POST',
                    provider_name: 'openai',
                    model_alias: 'gpt-4.1',
                    flow_id: null,
                    flow_name: null,
                    flow_execution_id: null,
                    runtime_session_id: 'runtime-session-1',
                    session_source_type: 'managed_agent',
                    session_source_id: 'agent-1',
                    session_reference: 'Agent Session',
                    runtime_principal_type: 'managed_agent',
                    runtime_principal_id: 'agent-1',
                    runtime_principal_name: 'Ops Agent',
                    auth_subject_type: 'api_key',
                    api_key_id: 'api-key-1',
                    api_key_name: 'Runtime Session managed_agent:agent-1',
                    estimated_cost: 0,
                    token_usage: {
                        prompt_tokens: 0,
                        completion_tokens: 0,
                        total_tokens: 0,
                    },
                    excerpt: '',
                    meta_data: {},
                },
            ],
        };
        auditResponse = {
            groups: [
                {
                    correlation_id: null,
                    outcome: 'failed',
                    primary_event: {
                        id: 'audit-1',
                        action: 'model_gateway_request',
                        status: 'failed',
                        timestamp: '2026-03-07T10:00:00Z',
                        details: { requested_model: 'gpt-4.1' },
                    },
                    sub_events: [],
                },
            ],
            total: 1,
        };
        trackersResponse = [
            { id: 'tracker-1', name: 'GitHub', type: 'github' },
            { id: 'tracker-2', name: 'Jira', type: 'jira' },
        ];
        apiUsageResponse = { total_requests: 321 };
        issueCountResponse = { total_issues: 27 };
        mcpServersResponse = [
            {
                id: 'mcp-1',
                name: 'Example MCP Server',
                url: 'http://localhost:8001/mcp',
                status: 'active',
            },
        ];
        toolsResponse = [
            {
                name: 'verify_refund_eligibility',
                source: 'builtin',
                source_id: null,
                source_name: 'builtin',
                schema: {},
                is_enabled: true,
                approval_workflow_id: null,
                has_approval_condition: false,
            },
            {
                name: 'refund_order',
                source: 'mcp',
                source_id: 'mcp-1',
                source_name: 'Example MCP Server',
                schema: {},
                is_enabled: true,
                approval_workflow_id: 'approval-1',
                has_approval_condition: true,
            },
        ];
        flowsResponse = [{ id: 'flow-1', name: 'Refund Assistant' }];
        flowExecutionsResponse = [
            {
                id: 'execution-1',
                flow_id: 'flow-1',
                flow_name: 'Refund Assistant',
                status: 'FAILED',
                start_time: '2026-03-07T10:00:00Z',
                end_time: '2026-03-07T10:03:00Z',
                error_message: 'Provider timeout',
            },
        ];
        pendingApprovalRequestsResponse = [
            {
                id: 'approval-1',
                tool_name: 'refund_order',
                status: 'pending',
                requested_at: '2026-03-07T10:01:00Z',
            },
        ];
        allApprovalRequestsResponse = [
            ...pendingApprovalRequestsResponse,
            {
                id: 'approval-2',
                tool_name: 'send_email',
                status: 'approved',
                requested_at: '2026-03-07T09:00:00Z',
                resolved_at: '2026-03-07T09:02:00Z',
            },
            {
                id: 'approval-3',
                tool_name: 'rollback_deployment',
                status: 'declined',
                requested_at: '2026-03-07T08:00:00Z',
                resolved_at: '2026-03-07T08:10:00Z',
            },
        ];
        aiModelsResponse = [
            {
                id: 'model-1',
                name: 'OpenAI GPT-4.1',
                provider_name: 'openai',
                model_identifier: 'gpt-4.1',
            },
        ];
        usersResponse = {
            users: [{ id: 'user-1', is_active: true }],
            total: 1,
            skip: 0,
            limit: 100,
        };
        fetchStub = sinon
            .stub(window, 'fetch')
            .callsFake(async (input) => {
            const url = typeof input === 'string' ? input : input.toString();
            const json = (data) => new Response(JSON.stringify(data), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            });
            if (url.startsWith('/api/v1/account/gateway-usage/summary')) {
                return json(gatewaySummaryResponse);
            }
            if (url.startsWith('/api/v1/runtime-sessions')) {
                return json(runtimeSessionsResponse);
            }
            if (url.startsWith('/api/v1/agents')) {
                return json(agentsResponse);
            }
            if (url.startsWith('/api/v1/account/gateway-usage/search')) {
                return json(gatewaySearchResponse);
            }
            if (url.startsWith('/api/v1/audit-logs/grouped')) {
                return json(auditResponse);
            }
            if (url === '/api/v1/trackers') {
                return json(trackersResponse);
            }
            if (url === '/api/v1/auth/api-usage') {
                return json(apiUsageResponse);
            }
            if (url === '/api/v1/issue-count') {
                return json(issueCountResponse);
            }
            if (url === '/api/v1/mcp-servers') {
                return json(mcpServersResponse);
            }
            if (url === '/api/v1/tools') {
                return json(toolsResponse);
            }
            if (url === '/api/v1/flows') {
                return json(flowsResponse);
            }
            if (url.startsWith('/api/v1/flows/executions')) {
                return json(flowExecutionsResponse);
            }
            if (url === '/api/v1/approval-requests?limit=3&status=pending') {
                return json(pendingApprovalRequestsResponse);
            }
            if (url === '/api/v1/approval-requests?limit=100') {
                return json(allApprovalRequestsResponse);
            }
            if (url === '/api/v1/ai-models') {
                return json(aiModelsResponse);
            }
            if (url === '/api/v1/users?skip=0&limit=100') {
                return json(usersResponse);
            }
            return json({ detail: `Unhandled ${url}` });
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
    async function mountDashboard() {
        return fixture(html `<dashboard-view></dashboard-view>`);
    }
    it('renders the merged overview dashboard with legacy and control-plane cards', async () => {
        const element = await mountDashboard();
        await waitUntil(() => !element['loading'], 'dashboard did not finish loading');
        await element.updateComplete;
        const header = element.shadowRoot?.querySelector('view-header');
        expect(header?.getAttribute('headerText')).to.equal('Overview');
        expect(element.shadowRoot?.textContent).to.contain('Welcome to Preloop');
        expect(element.shadowRoot?.textContent).to.contain('Recent flow executions');
        expect(element.shadowRoot?.textContent).to.contain('MCP server');
        expect(element.shadowRoot?.textContent).to.contain('Approval analytics');
        expect(element.shadowRoot?.textContent).to.contain('Key metrics');
        expect(element.shadowRoot?.textContent).to.contain('Active agents');
        expect(element.shadowRoot?.textContent).to.contain('Gateway failures');
        expect(element.shadowRoot?.textContent).to.contain('Audit exceptions');
        expect(element.shadowRoot?.textContent).to.contain('Pending approvals');
    });
    it('subscribes to realtime topics and fetches dashboard data', async () => {
        const element = await mountDashboard();
        await waitUntil(() => !element['loading'], 'dashboard did not finish loading');
        expect(connectStub).to.have.been.calledOnce;
        expect(subscribeStub.callCount).to.equal(8);
        const urls = fetchStub.getCalls().map((call) => String(call.args[0]));
        expect(urls.some((url) => url.startsWith('/api/v1/account/gateway-usage/summary'))).to.be.true;
        expect(urls.some((url) => url.startsWith('/api/v1/runtime-sessions'))).to.be
            .true;
        expect(urls.some((url) => url.startsWith('/api/v1/agents'))).to.be.true;
        expect(urls.some((url) => url.startsWith('/api/v1/audit-logs/grouped'))).to
            .be.true;
        expect(urls).to.include('/api/v1/trackers');
        expect(urls).to.include('/api/v1/mcp-servers');
        expect(urls).to.include('/api/v1/tools');
        expect(urls).to.include('/api/v1/flows');
        expect(urls.some((url) => url.startsWith('/api/v1/approval-requests'))).to
            .be.true;
    });
    it('hides exception cards when there is nothing actionable to show', async () => {
        gatewaySearchResponse = {
            ...gatewaySearchResponse,
            items: [],
        };
        auditResponse = {
            groups: [],
            total: 0,
        };
        const element = await mountDashboard();
        await waitUntil(() => !element['loading'], 'dashboard did not finish loading');
        await element.updateComplete;
        const content = element.shadowRoot?.textContent || '';
        expect(content).to.not.contain('Gateway failures needing attention');
        expect(content).to.not.contain('Audit exceptions');
    });
});
