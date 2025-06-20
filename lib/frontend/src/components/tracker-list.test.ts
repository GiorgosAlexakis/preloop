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
import { AddTrackerForm } from './add-tracker-form';

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

  it('displays a loading message', async () => {
    fetchStub.returns(new Promise(() => {})); // Never resolves

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;

    const loadingElement = el.shadowRoot!.querySelector('p');
    expect(loadingElement).to.contain.text('Loading...');
  });

  it('displays an error message on fetch failure', async () => {
    fetchStub.rejects(new Error('Failed to fetch'));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    const errorElement = el.shadowRoot!.querySelector('.error');
    expect(errorElement).to.contain.text('Error: Failed to fetch');
  });

  it('toggles the add tracker form', async () => {
    fetchStub.resolves(new Response(JSON.stringify([]), { status: 200 }));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;

    let form = el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(form).to.not.exist;

    await aTimeout(100);
    const button = el.shadowRoot!.querySelector('md-filled-button');
    if (button) {
      (button as HTMLElement).click();
      await el.updateComplete;
    }

    form = el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(form).to.exist;

    if (button) {
      button.click();
    }
    await el.updateComplete;

    form = el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(form).to.not.exist;
  });

  it('refreshes the list when a tracker is added', async () => {
    const initialTrackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
    ];
    const newTracker: Tracker = {
      id: '2',
      name: 'New Tracker',
      tracker_type: 'gitlab',
    };

    fetchStub
      .onFirstCall()
      .resolves(new Response(JSON.stringify(initialTrackers), { status: 200 }));
    fetchStub.onSecondCall().resolves(
      new Response(JSON.stringify([...initialTrackers, newTracker]), {
        status: 200,
      })
    );

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    let items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(1);

    await aTimeout(100);
    const button = el.shadowRoot!.querySelector('md-filled-button');
    if (button) {
      (button as HTMLElement).click();
      await el.updateComplete;
    }

    const form =
      el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form')!;
    const trackerAddedPromise = oneEvent(el, 'tracker-added');
    form.dispatchEvent(
      new CustomEvent('tracker-added', { bubbles: true, composed: true })
    );
    await trackerAddedPromise;
    await el.updateComplete;
    await aTimeout(0);

    items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(2);
    expect(items[1].tracker).to.deep.equal(newTracker);

    const formAfterAdd =
      el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(formAfterAdd).to.not.exist;
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
  it('shows the edit form when a tracker-edit event is dispatched', async () => {
    const trackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
    ];
    fetchStub.resolves(new Response(JSON.stringify(trackers), { status: 200 }));

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    let form = el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(form).to.not.exist;

    const item = el.shadowRoot!.querySelector<TrackerItem>('tracker-item')!;
    item.dispatchEvent(
      new CustomEvent('tracker-edit', {
        detail: { tracker: trackers[0] },
        bubbles: true,
        composed: true,
      })
    );
    await el.updateComplete;

    form = el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(form).to.exist;
    expect(form!.tracker).to.deep.equal(trackers[0]);
  });

  it('refreshes the list when a tracker is updated', async () => {
    const initialTrackers: Tracker[] = [
      { id: '1', name: 'Tracker 1', tracker_type: 'github' },
    ];
    const updatedTracker: Tracker = {
      id: '1',
      name: 'Updated Tracker',
      tracker_type: 'github',
    };

    fetchStub
      .onFirstCall()
      .resolves(new Response(JSON.stringify(initialTrackers), { status: 200 }));
    fetchStub
      .onSecondCall()
      .resolves(
        new Response(JSON.stringify([updatedTracker]), { status: 200 })
      );

    const el = await fixture<TrackerList>(html`<tracker-list></tracker-list>`);
    await el.updateComplete;
    await aTimeout(0);

    const item = el.shadowRoot!.querySelector<TrackerItem>('tracker-item')!;
    item.dispatchEvent(
      new CustomEvent('tracker-edit', {
        detail: { tracker: initialTrackers[0] },
        bubbles: true,
        composed: true,
      })
    );
    await el.updateComplete;

    const form =
      el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form')!;
    form.dispatchEvent(
      new CustomEvent('tracker-updated', { bubbles: true, composed: true })
    );
    await el.updateComplete;
    await aTimeout(0);

    const items = el.shadowRoot!.querySelectorAll<TrackerItem>('tracker-item');
    expect(items.length).to.equal(1);
    expect(items[0].tracker).to.deep.equal(updatedTracker);

    const formAfterUpdate =
      el.shadowRoot!.querySelector<AddTrackerForm>('add-tracker-form');
    expect(formAfterUpdate).to.not.exist;
  });
});
