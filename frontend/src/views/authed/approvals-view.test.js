import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import '../../components/view-header.ts';
import './approvals-view';
describe('ApprovalsView', () => {
    let fetchStub;
    function createFetchStub(approvalRequests = []) {
        return sinon
            .stub(window, 'fetch')
            .callsFake(async (input, init) => {
            const url = typeof input === 'string' ? input : input.toString();
            const method = (init?.method || 'GET').toUpperCase();
            const json = (data) => new Response(JSON.stringify(data), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            });
            if (url.includes('/api/v1/approval-requests') && method === 'GET') {
                return json(approvalRequests);
            }
            return json({ detail: `Unhandled: ${method} ${url}` });
        });
    }
    beforeEach(() => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
    });
    afterEach(() => {
        fetchStub?.restore();
        localStorage.clear();
    });
    it('renders the approval list view', async () => {
        fetchStub = createFetchStub([]);
        const element = (await fixture(html `<approvals-view></approvals-view>`));
        await waitUntil(() => !element.loading, 'Approvals view did not finish loading');
        await element.updateComplete;
        const header = element.shadowRoot?.querySelector('view-header');
        expect(header).to.exist;
        expect(header?.getAttribute('headerText')).to.equal('Approval Requests');
    });
    it('shows empty state when no approval requests', async () => {
        fetchStub = createFetchStub([]);
        const element = (await fixture(html `<approvals-view></approvals-view>`));
        await waitUntil(() => !element.loading, 'Approvals view did not finish loading');
        await element.updateComplete;
        const emptyState = element.shadowRoot?.querySelector('.empty-state');
        expect(emptyState).to.exist;
        expect(emptyState?.textContent).to.include('No approval requests yet');
    });
    it('shows approval list when requests exist', async () => {
        const mockRequests = [
            {
                id: 'ar-1',
                account_id: 'acc-1',
                tool_configuration_id: 'tc-1',
                approval_workflow_id: 'aw-1',
                execution_id: null,
                tool_name: 'example_tool',
                tool_args: {},
                agent_reasoning: null,
                status: 'pending',
                requested_at: new Date().toISOString(),
                resolved_at: null,
                expires_at: null,
                approver_comment: null,
            },
        ];
        fetchStub = createFetchStub(mockRequests);
        const element = (await fixture(html `<approvals-view></approvals-view>`));
        await waitUntil(() => element.approvalRequests?.length === 1, 'Approval requests did not load');
        await element.updateComplete;
        const approvalList = element.shadowRoot?.querySelector('.approval-list');
        expect(approvalList).to.exist;
        const approvalItems = element.shadowRoot?.querySelectorAll('.approval-item');
        expect(approvalItems.length).to.equal(1);
    });
    it('stubs fetch for approval-requests API', async () => {
        fetchStub = createFetchStub([]);
        const element = (await fixture(html `<approvals-view></approvals-view>`));
        await waitUntil(() => !element.loading, 'Approvals view did not finish loading');
        expect(fetchStub).to.have.been.called;
        const urls = fetchStub.getCalls().map((c) => String(c.args[0]));
        expect(urls.some((u) => u.includes('/api/v1/approval-requests'))).to.be
            .true;
    });
});
