import { html } from 'lit';
import { fixture, expect, oneEvent } from '@open-wc/testing';
import './tracker-item.ts';
import type { TrackerItem } from './tracker-item.ts';

describe('TrackerItem', () => {
  it('renders tracker name and type', async () => {
    const tracker = { id: '1', name: 'Test Tracker', tracker_type: 'github' };
    const el = await fixture<TrackerItem>(
      html`<tracker-item .tracker=${tracker}></tracker-item>`
    );

    await el.updateComplete;

    const nameElement = el.shadowRoot!.querySelector('div:first-child');
    const typeElement = el.shadowRoot!.querySelector('div:nth-child(2)');

    expect(nameElement).to.contain.text('Test Tracker');
    expect(typeElement).to.contain.text('github');
  });

  it('renders nothing when no tracker is provided', async () => {
    const el = await fixture<TrackerItem>(html`<tracker-item></tracker-item>`);
    await el.updateComplete;
    expect(el.shadowRoot!.firstElementChild).to.be.null;
  });

  it('dispatches a "tracker-deleted" event when the delete button is clicked', async () => {
    const tracker = { id: '1', name: 'Test Tracker', tracker_type: 'github' };
    const el = await fixture<TrackerItem>(
      html`<tracker-item .tracker=${tracker}></tracker-item>`
    );
    await el.updateComplete;

    const button = el.shadowRoot!.querySelector('button')!;
    setTimeout(() => button.click());

    const { detail } = await oneEvent(el, 'tracker-deleted');
    expect(detail.id).to.equal('1');
  });
  it('dispatches a "tracker-edit" event when the edit button is clicked', async () => {
    const tracker = { id: '1', name: 'Test Tracker', tracker_type: 'github' };
    const el = await fixture<TrackerItem>(
      html`<tracker-item .tracker=${tracker}></tracker-item>`
    );
    await el.updateComplete;

    const button = el.shadowRoot!.querySelector('.edit-button') as HTMLElement;
    setTimeout(() => button.click());

    const { detail } = await oneEvent(el, 'tracker-edit');
    expect(detail.tracker).to.deep.equal(tracker);
  });
});
