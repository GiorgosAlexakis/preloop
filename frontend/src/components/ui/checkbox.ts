import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-checkbox')
export class SlCheckbox extends UiElement {
  @property({ type: Boolean }) checked = false;
  @property({ type: Boolean, reflect: true }) indeterminate = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) value = '';
  @property({ type: String }) name = '';
  @property({ type: String }) size = 'medium';

  private _onChange(e: Event) {
    const target = e.target as HTMLInputElement;
    this.checked = target.checked;
    this.indeterminate = false;
    this.dispatchEvent(
      new CustomEvent('sl-change', {
        bubbles: true,
        composed: true,
        detail: { checked: this.checked },
      })
    );
  }

  render() {
    return html`
      <label
        part="base"
        class=${cn(
          'inline-flex items-center gap-2 text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
          this.disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <input
          part="control"
          type="checkbox"
          class="peer h-4 w-4 shrink-0 rounded-sm border border-primary shadow focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50 accent-primary"
          .checked=${this.checked}
          .indeterminate=${this.indeterminate}
          ?disabled=${this.disabled}
          name=${this.name || nothing}
          value=${this.value || nothing}
          @change=${this._onChange}
        />
        <slot></slot>
      </label>
    `;
  }
}

@customElement('sl-switch')
export class SlSwitch extends UiElement {
  @property({ type: Boolean }) checked = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) name = '';
  @property({ type: String }) value = '';

  private _onChange(e: Event) {
    const target = e.target as HTMLInputElement;
    this.checked = target.checked;
    this.dispatchEvent(
      new CustomEvent('sl-change', {
        bubbles: true,
        composed: true,
        detail: { checked: this.checked },
      })
    );
  }

  render() {
    return html`
      <label
        part="base"
        class=${cn(
          'inline-flex cursor-pointer items-center gap-2',
          this.disabled && 'cursor-not-allowed opacity-50'
        )}
      >
        <button
          part="control"
          type="button"
          role="switch"
          aria-checked=${this.checked}
          ?disabled=${this.disabled}
          class=${cn(
            'peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            this.checked ? 'bg-primary' : 'bg-input'
          )}
          @click=${() => {
            if (!this.disabled) {
              this.checked = !this.checked;
              this.dispatchEvent(
                new CustomEvent('sl-change', {
                  bubbles: true,
                  composed: true,
                  detail: { checked: this.checked },
                })
              );
            }
          }}
        >
          <span
            class=${cn(
              'pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform',
              this.checked ? 'translate-x-4' : 'translate-x-0'
            )}
          ></span>
        </button>
        <input
          type="checkbox"
          class="sr-only"
          .checked=${this.checked}
          name=${this.name || nothing}
          @change=${this._onChange}
        />
        <slot></slot>
      </label>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-checkbox': SlCheckbox;
    'sl-switch': SlSwitch;
  }
}
