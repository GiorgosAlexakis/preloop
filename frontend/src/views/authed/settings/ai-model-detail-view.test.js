import { expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import { unifiedWebSocketManager } from '../../../services/unified-websocket-manager';
import './ai-model-detail-view';
describe('AIModelDetailView', () => {
    let fetchStub;
    let connectStub;
    let subscribeStub;
    beforeEach(() => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
        fetchStub = sinon.stub(window, 'fetch');
        fetchStub.callsFake(async (input) => {
            const url = typeof input === 'string' ? input : input.toString();
            if (url === '/api/v1/ai-models/model-1') {
                return new Response(JSON.stringify({
                    id: 'model-1',
                    name: 'Claude Sonnet Primary',
                    provider_name: 'Anthropic',
                    model_identifier: 'claude-sonnet-4',
                    is_default: true,
                    created_at: '2026-03-01T10:00:00Z',
                    updated_at: '2026-03-09T18:30:00Z',
                }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                });
            }
            if (url.startsWith('/api/v1/ai-models/model-1/summary')) {
                return new Response(JSON.stringify({
                    ai_model_id: 'model-1',
                    model_name: 'Claude Sonnet Primary',
                    provider_name: 'Anthropic',
                    model_identifier: 'claude-sonnet-4',
                    period_start: '2026-02-08T00:00:00Z',
                    period_end: '2026-03-09T23:59:59Z',
                    total_requests: 18,
                    successful_requests: 16,
                    failed_requests: 2,
                    token_usage: {
                        prompt_tokens: 6400,
                        completion_tokens: 2100,
                        total_tokens: 8500,
                    },
                    estimated_cost: 1.42,
                    requests_by_day: [
                        {
                            date: '2026-03-08',
                            request_count: 7,
                            estimated_cost: 0.51,
                            total_tokens: 3200,
                        },
                        {
                            date: '2026-03-09',
                            request_count: 11,
                            estimated_cost: 0.91,
                            total_tokens: 5300,
                        },
                    ],
                    usage_by_session: [],
                }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                });
            }
            if (url.startsWith('/api/v1/ai-models/model-1/runtime-sessions')) {
                return new Response(JSON.stringify({
                    period_start: '2026-02-08T00:00:00Z',
                    period_end: '2026-03-09T23:59:59Z',
                    query: null,
                    session_source_type: null,
                    status: 'all',
                    total: 1,
                    limit: 10,
                    offset: 0,
                    items: [
                        {
                            id: 'runtime-session-1',
                            session_source_type: 'flow_execution',
                            session_source_id: 'execution-1',
                            session_reference: 'session-abc123',
                            runtime_principal_type: 'flow_execution',
                            runtime_principal_id: 'execution-1',
                            runtime_principal_name: 'Triage Assistant',
                            started_at: '2026-03-09T19:00:00Z',
                            last_activity_at: '2026-03-09T19:15:00Z',
                            ended_at: '2026-03-09T19:20:00Z',
                            flow_id: 'flow-1',
                            flow_name: 'Triage Assistant',
                            flow_execution_id: 'execution-1',
                            latest_model_alias: 'anthropic/claude-sonnet-4',
                            latest_provider_name: 'Anthropic',
                            total_requests: 6,
                            successful_requests: 6,
                            failed_requests: 0,
                            token_usage: {
                                prompt_tokens: 2200,
                                completion_tokens: 700,
                                total_tokens: 2900,
                            },
                            estimated_cost: 0.48,
                            last_request_at: '2026-03-09T19:15:00Z',
                        },
                    ],
                }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                });
            }
            if (url.startsWith('/api/v1/ai-models/model-1/interactions')) {
                return new Response(JSON.stringify({
                    period_start: '2026-02-08T00:00:00Z',
                    period_end: '2026-03-09T23:59:59Z',
                    query: null,
                    total: 1,
                    limit: 10,
                    offset: 0,
                    items: [
                        {
                            api_usage_id: 'usage-1',
                            timestamp: '2026-03-09T19:15:00Z',
                            status_code: 200,
                            outcome: 'success',
                            endpoint: '/anthropic/v1/messages',
                            method: 'POST',
                            provider_name: 'Anthropic',
                            model_alias: 'anthropic/claude-sonnet-4',
                            flow_id: 'flow-1',
                            flow_name: 'Triage Assistant',
                            flow_execution_id: 'execution-1',
                            runtime_session_id: 'runtime-session-1',
                            session_source_type: 'flow_execution',
                            session_source_id: 'execution-1',
                            session_reference: 'session-abc123',
                            runtime_principal_type: 'flow_execution',
                            runtime_principal_id: 'execution-1',
                            runtime_principal_name: 'Triage Assistant',
                            estimated_cost: 0.12,
                            token_usage: {
                                prompt_tokens: 300,
                                completion_tokens: 95,
                                total_tokens: 395,
                            },
                            excerpt: 'request.input: Summarize deployment risk response.output_text: Deployment risk summary completed',
                            meta_data: {
                                source: 'gateway_interaction',
                            },
                        },
                    ],
                }), {
                    status: 200,
                    headers: { 'Content-Type': 'application/json' },
                });
            }
            return new Response(JSON.stringify({ detail: `Unhandled request: ${url}` }), {
                status: 500,
                headers: { 'Content-Type': 'application/json' },
            });
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
    it('renders model observability summary, sessions, and interactions', async () => {
        const element = document.createElement('ai-model-detail-view');
        element.modelId = 'model-1';
        document.body.appendChild(element);
        await waitUntil(() => !element.loading, 'AI model detail view did not finish loading');
        await element.updateComplete;
        const content = element.shadowRoot?.textContent || '';
        expect(content).to.contain('Claude Sonnet Primary');
        expect(content).to.contain('Model Observability');
        expect(content).to.contain('Anthropic');
        expect(content).to.contain('claude-sonnet-4');
        expect(content).to.contain('18');
        expect(content).to.contain('$1.42');
        expect(content).to.contain('8,500');
        expect(content).to.contain('Runtime Sessions');
        expect(content).to.contain('Triage Assistant');
        expect(content).to.contain('session-abc123');
        expect(content).to.contain('Captured Interactions');
        expect(content).to.contain('Deployment risk summary completed');
        const runtimeSessionLink = element.shadowRoot?.querySelector('a[href="/console/runtime-sessions?sessionId=runtime-session-1"]');
        const flowExecutionLink = element.shadowRoot?.querySelector('a[href="/console/flows/executions/execution-1"]');
        expect(runtimeSessionLink).to.not.equal(null);
        expect(flowExecutionLink).to.not.equal(null);
        const summaryCall = fetchStub
            .getCalls()
            .find((call) => String(call.args[0]).startsWith('/api/v1/ai-models/model-1/summary'));
        const sessionsCall = fetchStub
            .getCalls()
            .find((call) => String(call.args[0]).startsWith('/api/v1/ai-models/model-1/runtime-sessions'));
        const interactionsCall = fetchStub
            .getCalls()
            .find((call) => String(call.args[0]).startsWith('/api/v1/ai-models/model-1/interactions'));
        expect(summaryCall).to.not.equal(undefined);
        expect(String(summaryCall?.args[0])).to.contain('start_date=');
        expect(String(summaryCall?.args[0])).to.contain('end_date=');
        expect(sessionsCall).to.not.equal(undefined);
        expect(String(sessionsCall?.args[0])).to.contain('limit=10');
        expect(interactionsCall).to.not.equal(undefined);
        expect(String(interactionsCall?.args[0])).to.contain('limit=10');
        expect(connectStub).to.have.been.calledOnce;
        expect(subscribeStub.callCount).to.equal(4);
        document.body.removeChild(element);
    });
});
