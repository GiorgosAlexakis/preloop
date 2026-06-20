import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

const alertVariants = cva(
  'relative w-full rounded-lg border px-4 py-3 text-sm [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground [&>svg~*]:pl-7',
  {
    variants: {
      variant: {
        primary: 'bg-background text-foreground',
        success:
          'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-800 dark:bg-emerald-950 dark:text-emerald-100',
        warning:
          'border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100',
        danger:
          'border-destructive/50 bg-destructive/10 text-destructive dark:border-destructive [&>svg]:text-destructive',
        neutral: 'bg-muted text-muted-foreground',
      },
    },
    defaultVariants: {
      variant: 'primary',
    },
  }
);

@customElement('sl-alert')
export class SlAlert extends UiElement {
  @property({ type: String }) variant = 'primary';
  @property({ type: Boolean, reflect: true }) open = true;
  @property({ type: Boolean }) closable = false;
  @property({ type: Number }) duration = 0;

  private _close() {
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('sl-hide', { bubbles: true, composed: true })
    );
  }

  connectedCallback() {
    super.connectedCallback();
    if (this.duration > 0) {
      setTimeout(() => this._close(), this.duration);
    }
  }

  render() {
    if (!this.open) return nothing;

    return html`
      <div
        part="base"
        class=${cn(alertVariants({ variant: this.variant as 'primary' }))}
        role="alert"
      >
        <slot name="icon"></slot>
        <div>
          <slot></slot>
        </div>
        ${this.closable
          ? html`
              <button
                type="button"
                class="absolute right-2 top-2 rounded-sm opacity-70 hover:opacity-100"
                @click=${this._close}
                aria-label="Close"
              >
                <sl-icon name="x"></sl-icon>
              </button>
            `
          : nothing}
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-alert': SlAlert;
  }
}
