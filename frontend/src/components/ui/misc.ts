import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-icon-button')
export class SlIconButton extends UiElement {
  @property({ type: String }) name = '';
  @property({ type: String }) label = '';
  @property({ type: String }) href = '';
  @property({ type: String }) target = '';
  @property({ type: Boolean }) disabled = false;

  render() {
    const classes =
      'inline-flex h-9 w-9 items-center justify-center rounded-md text-sm transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50';

    if (this.href) {
      return html`
        <a
          part="base"
          class=${classes}
          href=${this.href}
          target=${this.target || nothing}
          aria-label=${this.label || this.name}
        >
          <sl-icon name=${this.name}></sl-icon>
        </a>
      `;
    }

    return html`
      <button
        part="base"
        class=${classes}
        type="button"
        ?disabled=${this.disabled}
        aria-label=${this.label || this.name}
      >
        <sl-icon name=${this.name}></sl-icon>
      </button>
    `;
  }
}

@customElement('sl-button-group')
export class SlButtonGroup extends UiElement {
  render() {
    return html`
      <div part="base" class="inline-flex rounded-md shadow-sm [&>sl-button]:rounded-none [&>sl-button:first-child]:rounded-l-md [&>sl-button:last-child]:rounded-r-md [&>sl-button:not(:first-child)]:border-l-0" role="group">
        <slot></slot>
      </div>
    `;
  }
}

@customElement('sl-spinner')
export class SlSpinner extends UiElement {
  render() {
    return html`
      <sl-icon
        part="base"
        name="loader"
        class="animate-spin text-muted-foreground"
      ></sl-icon>
    `;
  }
}

@customElement('sl-divider')
export class SlDivider extends UiElement {
  @property({ type: String }) vertical = '';

  render() {
    const isVertical = this.hasAttribute('vertical');
    return html`
      <div
        part="base"
        role="separator"
        class=${cn(
          'shrink-0 bg-border',
          isVertical ? 'h-full w-px' : 'h-px w-full'
        )}
      ></div>
    `;
  }
}

@customElement('sl-details')
export class SlDetails extends UiElement {
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) summary = '';

  private _toggle() {
    if (this.disabled) return;
    this.open = !this.open;
    this.dispatchEvent(
      new CustomEvent(this.open ? 'sl-show' : 'sl-hide', {
        bubbles: true,
        composed: true,
      })
    );
  }

  render() {
    return html`
      <details
        part="base"
        class="rounded-lg border bg-card text-card-foreground"
        ?open=${this.open}
        @toggle=${(e: Event) => {
          const target = e.target as HTMLDetailsElement;
          this.open = target.open;
        }}
      >
        <summary
          part="header"
          class="flex cursor-pointer list-none items-center justify-between p-4 font-medium [&::-webkit-details-marker]:hidden"
          @click=${(e: Event) => {
            if (this.disabled) e.preventDefault();
          }}
        >
          <slot name="summary">${this.summary}</slot>
          <sl-icon
            name="chevron-down"
            class=${cn('transition-transform', this.open && 'rotate-180')}
          ></sl-icon>
        </summary>
        <div part="content" class="border-t px-4 pb-4 pt-2">
          <slot></slot>
        </div>
      </details>
    `;
  }
}

@customElement('sl-progress-bar')
export class SlProgressBar extends UiElement {
  @property({ type: Number }) value = 0;
  @property({ type: String }) variant = 'primary';
  @property({ type: Boolean }) indeterminate = false;

  render() {
    const percent = Math.min(100, Math.max(0, this.value));
    return html`
      <div
        part="base"
        role="progressbar"
        aria-valuenow=${this.indeterminate ? undefined : percent}
        class="relative h-2 w-full overflow-hidden rounded-full bg-primary/20"
      >
        <div
          part="indicator"
          class=${cn(
            'h-full bg-primary transition-all',
            this.indeterminate && 'animate-pulse w-1/3'
          )}
          style=${this.indeterminate ? '' : `width: ${percent}%`}
        ></div>
      </div>
    `;
  }
}

@customElement('sl-tooltip')
export class SlTooltip extends UiElement {
  @property({ type: String }) content = '';
  @property({ type: String }) placement = 'top';
  @property({ type: Number }) distance = 8;
  @property({ type: Boolean }) disabled = false;

  render() {
    return html`
      <div part="base" class="group relative inline-flex">
        <slot></slot>
        ${!this.disabled && this.content
          ? html`
              <div
                part="body"
                role="tooltip"
                class="pointer-events-none absolute bottom-full left-1/2 z-50 mb-1 hidden -translate-x-1/2 rounded-md border bg-popover px-3 py-1.5 text-xs text-popover-foreground shadow-md group-hover:block"
              >
                ${this.content}
              </div>
            `
          : ''}
      </div>
    `;
  }
}

@customElement('sl-copy-button')
export class SlCopyButton extends UiElement {
  @property({ type: String }) value = '';
  @property({ type: String }) label = 'Copy';
  @property({ type: Boolean }) disabled = false;

  private async _copy() {
    if (this.disabled || !this.value) return;
    await navigator.clipboard.writeText(this.value);
    this.dispatchEvent(
      new CustomEvent('sl-copy', { bubbles: true, composed: true })
    );
  }

  render() {
    return html`
      <button
        part="button"
        type="button"
        class="inline-flex h-8 items-center gap-1 rounded-md border border-input bg-background px-2 text-xs shadow-sm hover:bg-accent"
        ?disabled=${this.disabled}
        @click=${this._copy}
        aria-label=${this.label}
      >
        <sl-icon name="copy"></sl-icon>
        <slot></slot>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-icon-button': SlIconButton;
    'sl-button-group': SlButtonGroup;
    'sl-spinner': SlSpinner;
    'sl-divider': SlDivider;
    'sl-details': SlDetails;
    'sl-progress-bar': SlProgressBar;
    'sl-tooltip': SlTooltip;
    'sl-copy-button': SlCopyButton;
  }
}
