import { html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-dropdown')
export class SlDropdown extends UiElement {
  @property({ type: Boolean }) open = false;
  @property({ type: Boolean }) hoist = false;
  @property({ type: String }) placement = 'bottom-start';
  @property({ type: Number }) distance = 4;
  @property({ type: Number }) skidding = 0;

  @state() private _isOpen = false;

  show() {
    this._isOpen = true;
    this.open = true;
  }

  hide() {
    this._isOpen = false;
    this.open = false;
    this.dispatchEvent(
      new CustomEvent('sl-hide', { bubbles: true, composed: true })
    );
  }

  private _toggle() {
    this._isOpen ? this.hide() : this.show();
  }

  render() {
    return html`
      <div part="base" class="relative inline-block">
        <div part="trigger" @click=${this._toggle}>
          <slot name="trigger"></slot>
        </div>
        ${this._isOpen || this.open
          ? html`
              <div
                part="panel"
                class="absolute z-50 mt-1 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
                @click=${(e: Event) => e.stopPropagation()}
              >
                <slot></slot>
              </div>
            `
          : nothing}
      </div>
    `;
  }
}

@customElement('sl-menu')
export class SlMenu extends UiElement {
  render() {
    return html`
      <div part="base" class="flex flex-col gap-0.5 p-1" role="menu">
        <slot></slot>
      </div>
    `;
  }
}

@customElement('sl-menu-item')
export class SlMenuItem extends UiElement {
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) value = '';
  @property({ type: String }) type = 'normal';

  private _onClick() {
    if (this.disabled) return;
    this.dispatchEvent(
      new CustomEvent('sl-select', {
        bubbles: true,
        composed: true,
        detail: { item: this },
      })
    );
  }

  render() {
    return html`
      <button
        part="base"
        type="button"
        role="menuitem"
        ?disabled=${this.disabled}
        class=${cn(
          'relative flex w-full cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors hover:bg-accent hover:text-accent-foreground focus:bg-accent focus:text-accent-foreground disabled:pointer-events-none disabled:opacity-50',
          this.type === 'checkbox' && 'pl-8'
        )}
        @click=${this._onClick}
      >
        <slot name="prefix"></slot>
        <slot></slot>
        <slot name="suffix"></slot>
      </button>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-dropdown': SlDropdown;
    'sl-menu': SlMenu;
    'sl-menu-item': SlMenuItem;
  }
}
