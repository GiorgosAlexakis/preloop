import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import '../../components/view-header';
import '../../components/tracker-list';
import '../../components/add-tracker-modal';
import './trackers-view';
describe('TrackersView', () => {
    let element;
    let fetchStub;
    function createFetchStub() {
        return sinon
            .stub(window, 'fetch')
            .callsFake(async (input, init) => {
            const url = typeof input === 'string' ? input : input.toString();
            const method = (init?.method || 'GET').toUpperCase();
            const json = (data) => new Response(JSON.stringify(data), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            });
            if (url.includes('/api/v1/trackers') && method === 'GET') {
                return json([]);
            }
            return json({ detail: `Unhandled: ${method} ${url}` });
        });
    }
    beforeEach(async () => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
        fetchStub = createFetchStub();
        element = await fixture(html `<trackers-view></trackers-view>`);
    });
    afterEach(() => {
        fetchStub.restore();
        localStorage.clear();
        // Reset URL
        window.history.replaceState({}, '', window.location.pathname);
    });
    it('renders the view with header', async () => {
        await element.updateComplete;
        const header = element.shadowRoot?.querySelector('view-header');
        expect(header).to.exist;
        const h1 = header?.shadowRoot?.querySelector('h1');
        expect(h1?.textContent?.trim()).to.equal('Trackers');
    });
    it('renders Add New Tracker button', async () => {
        await element.updateComplete;
        const addButton = element.shadowRoot?.querySelector('sl-button[variant="primary"]');
        expect(addButton).to.exist;
        expect(addButton?.textContent?.trim()).to.include('Add New Tracker');
    });
    it('renders tracker-list', async () => {
        await element.updateComplete;
        const trackerList = element.shadowRoot?.querySelector('tracker-list');
        expect(trackerList).to.exist;
    });
    it('opens add tracker modal when Add New Tracker button is clicked', async () => {
        await element.updateComplete;
        const addButton = element.shadowRoot?.querySelector('sl-button[variant="primary"]');
        expect(addButton).to.exist;
        addButton.click();
        await element.updateComplete;
        const addModal = element.shadowRoot?.querySelector('add-tracker-modal');
        expect(addModal).to.exist;
    });
    it('fetches trackers on load', async () => {
        await waitUntil(() => fetchStub.called, 'Fetch was not called');
        const urls = fetchStub.getCalls().map((c) => String(c.args[0]));
        expect(urls.some((u) => u.includes('/api/v1/trackers'))).to.be.true;
    });
});
