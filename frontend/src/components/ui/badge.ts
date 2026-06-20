import { html } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        primary:
          'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80',
        success:
          'border-transparent bg-emerald-600 text-white shadow hover:bg-emerald-600/80',
        warning:
          'border-transparent bg-amber-500 text-white shadow hover:bg-amber-500/80',
        danger:
          'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80',
        neutral:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
      },
      pill: {
        true: 'rounded-full',
        false: '',
      },
    },
    defaultVariants: {
      variant: 'primary',
      pill: false,
    },
  }
);

@customElement('sl-badge')
export class SlBadge extends UiElement {
  @property({ type: String }) variant = 'primary';
  @property({ type: Boolean }) pill = false;

  render() {
    return html`
      <span
        part="base"
        class=${cn(
          badgeVariants({
            variant: this.variant as 'primary',
            pill: this.pill,
          })
        )}
      >
        <slot></slot>
      </span>
    `;
  }
}

@customElement('sl-tag')
export class SlTag extends UiElement {
  @property({ type: String }) variant = 'neutral';
  @property({ type: Boolean }) pill = false;
  @property({ type: Boolean }) removable = false;
  @property({ type: String }) size = 'medium';

  private _remove() {
    this.dispatchEvent(
      new CustomEvent('sl-remove', { bubbles: true, composed: true })
    );
    this.remove();
  }

  render() {
    return html`
      <span
        part="base"
        class=${cn(
          badgeVariants({
            variant: this.variant as 'neutral',
            pill: this.pill || true,
          }),
          'gap-1'
        )}
      >
        <slot></slot>
        ${this.removable
          ? html`
              <button
                type="button"
                part="remove-button"
                class="ml-0.5 rounded-full hover:bg-black/10"
                @click=${this._remove}
                aria-label="Remove"
              >
                <sl-icon name="x"></sl-icon>
              </button>
            `
          : ''}
      </span>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-badge': SlBadge;
    'sl-tag': SlTag;
  }
}
