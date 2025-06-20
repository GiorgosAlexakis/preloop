import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { router } from '../../router';
import { Router } from '@vaadin/router';
import '@vaadin/tabs';

@customElement('issues-view')
export class IssuesView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: var(--lumo-space-m);
    }
    a {
      text-decoration: none;
    }
  `;

  @state()
  private selectedTab = 0;

  private tabs = [
    { label: 'Duplicates', path: '/issues/duplicates' },
    { label: 'Suggested', path: '/issues/suggested' },
  ];

  connectedCallback() {
    super.connectedCallback();
    this.updateSelectedTab();
  }

  updateSelectedTab() {
    const currentPath = window.location.pathname;
    const activeTabIndex = this.tabs.findIndex((tab) =>
      currentPath.startsWith(tab.path)
    );
    if (activeTabIndex !== -1) {
      this.selectedTab = activeTabIndex;
    }
  }

  handleTabChange(e: CustomEvent) {
    const selectedIndex = e.detail.value;
    if (this.selectedTab !== selectedIndex) {
      this.selectedTab = selectedIndex;
      Router.go(this.tabs[selectedIndex].path);
    }
  }

  render() {
    return html`
      <vaadin-tabs
        .selected=${this.selectedTab}
        @selected-changed=${this.handleTabChange}
      >
        ${this.tabs.map((tab) => html`<vaadin-tab>${tab.label}</vaadin-tab>`)}
      </vaadin-tabs>
      <slot></slot>
    `;
  }
}
