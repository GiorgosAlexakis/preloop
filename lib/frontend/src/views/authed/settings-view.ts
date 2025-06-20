import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { router } from '../../router';

@customElement('settings-view')
export class SettingsView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: var(--lumo-space-l);
    }
    vaadin-tabs {
      margin-bottom: var(--lumo-space-l);
    }
  `;

  @state()
  private location = router.location;

  private tabs = [
    { path: '/settings/account', label: 'Account' },
    { path: '/settings/api-keys', label: 'API Keys' },
    { path: '/settings/llm-models', label: 'LLM Models' },
  ];

  private get selectedTab() {
    return this.tabs.findIndex((tab) =>
      this.location.pathname.startsWith(tab.path)
    );
  }

  private onTabSelected(e: CustomEvent) {
    const tab = this.tabs[e.detail.value];
    if (tab) {
      Router.go(tab.path);
    }
  }

  render() {
    return html`
      <vaadin-tabs
        .selected=${this.selectedTab}
        @selected-changed=${this.onTabSelected}
      >
        ${this.tabs.map((tab) => html`<vaadin-tab>${tab.label}</vaadin-tab>`)}
      </vaadin-tabs>
      <slot></slot>
    `;
  }
}
