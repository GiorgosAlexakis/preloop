import { html } from 'lit';
import { fixture, expect } from '@open-wc/testing';
import './lit-app.js';

describe('LitApp', () => {
  it('renders the header and the hello-world component', async () => {
    const el = await fixture(html`<lit-app></lit-app>`);
    const header = el.shadowRoot!.querySelector('header');
    const trackerList = el.shadowRoot!.querySelector('tracker-list');

    expect(header).to.exist;
    expect(header!.textContent).to.include('SpaceBridge v2');
    expect(trackerList).to.exist;
  });

  it('passes accessibility audit', async () => {
    const el = await fixture(html`<lit-app></lit-app>`);
    await expect(el).to.be.accessible();
  });
});
