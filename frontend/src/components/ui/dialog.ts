import { html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-dialog')
export class SlDialog extends UiElement {
  @property({ type: String }) label = '';
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: Boolean, attribute: 'no-header' }) noHeader = false;

  show() {
    this.open = true;
  }

  hide() {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('sl-hide', { bubbles: true, composed: true })
    );
  }

  private _onBackdropClick(e: MouseEvent) {
    if (e.target === e.currentTarget) {
      this._requestClose();
    }
  }

  private _requestClose() {
    this.dispatchEvent(
      new CustomEvent('sl-request-close', {
        bubbles: true,
        composed: true,
        cancelable: true,
      })
    );
    if (!this.open) return;
    this.hide();
  }

  private _onKeydown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      this._requestClose();
    }
  }

  updated(changed: Map<string, unknown>) {
    if (changed.has('open')) {
      if (this.open) {
        document.body.style.overflow = 'hidden';
        window.addEventListener('keydown', this._onKeydown.bind(this));
      } else {
        document.body.style.overflow = '';
      }
    }
  }

  render() {
    if (!this.open) return nothing;

    return html`
      <div
        part="overlay"
        class="fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out"
        @click=${this._onBackdropClick}
      >
        <div
          part="panel"
          class="fixed left-1/2 top-1/2 z-50 grid w-full max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 border bg-background p-6 shadow-lg sm:rounded-lg"
          role="dialog"
          aria-modal="true"
          aria-label=${this.label || 'Dialog'}
          @click=${(e: Event) => e.stopPropagation()}
        >
          ${!this.noHeader
            ? html`
                <div part="header" class="flex flex-col space-y-1.5 text-center sm:text-left">
                  <h2 class="text-lg font-semibold leading-none tracking-tight">
                    ${this.label || html`<slot name="label"></slot>`}
                  </h2>
                  <button
                    type="button"
                    class="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                    @click=${this._requestClose}
                    aria-label="Close"
                  >
                    <sl-icon name="x"></sl-icon>
                  </button>
                </div>
              `
            : nothing}
          <div part="body" class="max-h-[70vh] overflow-y-auto">
            <slot></slot>
          </div>
          <div part="footer" class="flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-dialog': SlDialog;
  }
}
