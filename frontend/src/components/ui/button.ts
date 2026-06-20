import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cva } from 'class-variance-authority';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 cursor-pointer',
  {
    variants: {
      variant: {
        default:
          'border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground',
        primary:
          'bg-primary text-primary-foreground shadow hover:bg-primary/90',
        success:
          'bg-emerald-600 text-white shadow hover:bg-emerald-600/90',
        warning:
          'bg-amber-500 text-white shadow hover:bg-amber-500/90',
        danger:
          'bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90',
        text: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        small: 'h-8 rounded-md px-3 text-xs',
        medium: 'h-9 px-4 py-2',
        large: 'h-10 rounded-md px-8',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'medium',
    },
  }
);

@customElement('sl-button')
export class SlButton extends UiElement {
  @property({ type: String }) variant = 'default';
  @property({ type: String }) size = 'medium';
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) loading = false;
  @property({ type: Boolean }) outline = false;
  @property({ type: Boolean, attribute: 'caret' }) caret = false;
  @property({ type: String }) href = '';
  @property({ type: String }) target = '';
  @property({ type: String }) type: 'button' | 'submit' | 'reset' = 'button';
  @property({ type: String }) pill = '';
  @property({ type: String }) circle = '';

  private get resolvedVariant(): string {
    if (this.outline) return 'default';
    return this.variant;
  }

  render() {
    const classes = cn(
      buttonVariants({
        variant: this.resolvedVariant as 'default',
        size: this.size as 'medium',
      }),
      this.outline &&
        'border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground',
      (this.pill !== null && this.hasAttribute('pill')) && 'rounded-full',
      (this.circle !== null && this.hasAttribute('circle')) &&
        'h-9 w-9 rounded-full p-0'
    );

    const content = html`
      <slot name="prefix"></slot>
      <slot></slot>
      <slot name="suffix"></slot>
      ${this.loading ? html`<sl-spinner></sl-spinner>` : nothing}
      ${this.caret ? html`<sl-icon name="chevron-down"></sl-icon>` : nothing}
    `;

    if (this.href) {
      return html`
        <a
          part="base"
          class=${classes}
          href=${this.href}
          target=${this.target || nothing}
        >
          ${content}
        </a>
      `;
    }

    return html`
      <button
        part="base"
        class=${classes}
        type=${this.type}
        ?disabled=${this.disabled || this.loading}
      >
        ${content}
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-button': SlButton;
  }
}
