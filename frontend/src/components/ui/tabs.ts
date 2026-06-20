import { html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-tab-group')
export class SlTabGroup extends UiElement {
  @property({ type: String }) placement = 'top';

  @state() private _activeTab = '';

  private _onTabClick(e: CustomEvent) {
    this._activeTab = e.detail.name;
    this.dispatchEvent(
      new CustomEvent('sl-tab-show', {
        bubbles: true,
        composed: true,
        detail: { name: this._activeTab },
      })
    );
  }

  firstUpdated() {
    const tabs = this.querySelectorAll('sl-tab');
    if (tabs.length > 0 && !this._activeTab) {
      const active = Array.from(tabs).find((t) => t.hasAttribute('active'));
      this._activeTab =
        active?.getAttribute('panel') ||
        tabs[0].getAttribute('panel') ||
        'tab-0';
    }
  }

  render() {
    return html`
      <div part="base" class="w-full">
        <div
          part="nav"
          class="inline-flex h-9 items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground"
          @sl-tab-activate=${this._onTabClick}
        >
          <slot name="nav" @slotchange=${() => this.requestUpdate()}></slot>
          <slot name="tabs" @slotchange=${() => this.requestUpdate()}></slot>
        </div>
        <div part="body" class="mt-4">
          <slot @slotchange=${() => this.requestUpdate()}></slot>
        </div>
      </div>
    `;
  }
}

@customElement('sl-tab')
export class SlTab extends UiElement {
  @property({ type: String }) panel = '';
  @property({ type: Boolean, reflect: true }) active = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) slot = 'nav';

  private _activate() {
    if (this.disabled) return;
    this.active = true;
    this.dispatchEvent(
      new CustomEvent('sl-tab-activate', {
        bubbles: true,
        composed: true,
        detail: { name: this.panel },
      })
    );
  }

  render() {
    return html`
      <button
        part="base"
        type="button"
        role="tab"
        ?disabled=${this.disabled}
        class=${cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
          this.active
            ? 'bg-background text-foreground shadow'
            : 'hover:bg-background/50 hover:text-foreground'
        )}
        @click=${this._activate}
      >
        <slot></slot>
      </button>
    `;
  }
}

@customElement('sl-tab-panel')
export class SlTabPanel extends UiElement {
  @property({ type: String }) name = '';
  @property({ type: Boolean, reflect: true }) active = false;

  render() {
    if (!this.active) return nothing;
    return html`
      <div part="base" role="tabpanel" class="mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">
        <slot></slot>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-tab-group': SlTabGroup;
    'sl-tab': SlTab;
    'sl-tab-panel': SlTabPanel;
  }
}
