import { html } from 'lit';
import {
  fixture,
  expect,
  aTimeout,
  waitUntil,
  oneEvent,
} from '@open-wc/testing';
import sinon from 'sinon';
import './tracker-list';
import type { TrackerList } from './tracker-list';
import type { TrackerItem } from './tracker-item';
import type { Tracker } from './tracker-item';

describe('TrackerList', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    fetchStub = sinon.stub(window, 'fetch');
  });

  afterEach(() => {
    if (fetchStub) {
      fetchStub.restore();
    }
  });

  it('renders a list of trackers', async () => {
    const trackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
      { id: '2', name: 'Tracker 2', tracker_type: 'jira' },
    ];
    fetchStub.resolves(new Response(JSON.stringify(trackers), { status: 200 }));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0); // Wait for the fetch to complete

    const items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(2);
    expect(items[0].tracker).to.deep.equal(trackers[0]);
    expect(items[1].tracker).to.deep.equal(trackers[1]);
  });

  it('displays a loading spinner', async () => {
    fetchStub.returns(new Promise(() => {})); // Never resolves

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;

    const spinner = el.shadowRoot!.querySelector('sl-spinner');
    expect(spinner).to.exist;
  });

  it('displays an error message on fetch failure', async () => {
    fetchStub.rejects(new Error('Failed to fetch'));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    const alertElement = el.shadowRoot!.querySelector('sl-alert');
    expect(alertElement).to.exist;
    expect(alertElement!.textContent).to.include('Error: Failed to fetch');
  });

  it('deletes a tracker and refreshes the list', async () => {
    const trackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
      { id: '2', name: 'Tracker 2', tracker_type: 'jira' },
    ];
    fetchStub
      .onFirstCall()
      .resolves(new Response(JSON.stringify(trackers), { status: 200 }));
    fetchStub
      .withArgs('/api/v1/trackers/1', sinon.match({ method: 'DELETE' }))
      .resolves(new Response(null, { status: 204 }));
    fetchStub
      .onThirdCall()
      .resolves(new Response(JSON.stringify([trackers[1]]), { status: 200 }));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    let items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(2);

    const trackerItem = items[0];
    trackerItem.dispatchEvent(
      new CustomEvent('tracker-deleted', {
        detail: { id: '1' },
        bubbles: true,
        composed: true,
      })
    );

    await el.updateComplete;
    await aTimeout(0);

    items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(1);
    expect(items[0].tracker).to.deep.equal(trackers[1]);
  });

  it('dispatches a tracker-edit event when a child item emits it', async () => {
    const trackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
    ];
    fetchStub.resolves(new Response(JSON.stringify(trackers), { status: 200 }));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0); // wait for render

    const trackerItem =
      el.shadowRoot!.querySelector<TrackerItem>('tracker-item')!;
    const listener = oneEvent(el, 'tracker-edit');

    trackerItem.dispatchEvent(
      new CustomEvent('tracker-edit', {
        detail: { tracker: trackers[0] },
        bubbles: true,
        composed: true,
      })
    );

    const event = await listener;
    expect(event).to.exist;
    expect(event.detail.tracker).to.deep.equal(trackers[0]);
  });
});
