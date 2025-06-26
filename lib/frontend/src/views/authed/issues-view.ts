import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';

@customElement('issues-view')
export class IssuesView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: var(--lumo-space-m);
    }
    sl-tab-group::part(tabs) {
      border-bottom: none;
    }
  `;

  private tabs = [
    { panel: 'duplicates', label: 'Duplicates', path: '/issues/duplicates' },
    { panel: 'assignments', label: 'Assignments', path: '/issues/assignments' },
  ];

  connectedCallback() {
    super.connectedCallback();
    this.updateActiveTab();
    window.addEventListener(
      'vaadin-router-location-changed',
      this.handleLocationChanged
    );
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener(
      'vaadin-router-location-changed',
      this.handleLocationChanged
    );
  }

  handleLocationChanged = () => {
    this.updateActiveTab();
  };

  async updateActiveTab() {
    await this.updateComplete;
    const tabGroup = this.shadowRoot?.querySelector('sl-tab-group');
    if (!tabGroup) return;

    const currentPath = window.location.pathname;
    const activeTab = this.tabs.find((tab) =>
      currentPath.startsWith(tab.path)
    );

    if (activeTab) {
      tabGroup.show(activeTab.panel);
    }
  }

  handleTabChange(e: CustomEvent) {
    const tab = this.tabs.find((t) => t.panel === e.detail.name);
    if (tab && !window.location.pathname.startsWith(tab.path)) {
      Router.go(tab.path);
    }
  }

  render() {
    return html`
      <slot></slot>
    `;
  }
}
