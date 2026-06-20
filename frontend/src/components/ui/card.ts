import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-card')
export class SlCard extends UiElement {
  @property({ type: Boolean }) withHeader = false;
  @property({ type: Boolean }) withFooter = false;
  @property({ type: Boolean }) withImage = false;

  render() {
    return html`
      <div
        part="base"
        class="rounded-xl border bg-card text-card-foreground shadow"
      >
        <div part="image" class="overflow-hidden rounded-t-xl">
          <slot name="image"></slot>
        </div>
        <div part="header" class="flex flex-col space-y-1.5 p-6 pb-0">
          <slot name="header"></slot>
        </div>
        <div part="body" class="p-6 pt-4">
          <slot></slot>
        </div>
        <div part="footer" class="flex items-center p-6 pt-0">
          <slot name="footer"></slot>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-card': SlCard;
  }
}
