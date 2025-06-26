import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { getDuplicateIssues } from '../../api';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';

@customElement('issues-view')
export class IssuesView extends LitElement {
  static styles = css`
    :host {
      display: block;
      padding: var(--lumo-space-m);
    }

    .header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: var(--sl-spacing-large);
    }

    .container {
      max-width: var(--console-container-max-width);
      padding: var(--sl-spacing-x-large);
    }
  `;

  @state()
  private issues: any[] = [];

  private tabs = [
    { panel: 'duplicates', label: 'Duplicates', path: '/issues/duplicates' },
    { panel: 'assignments', label: 'Assignments', path: '/issues/assignments' },
  ];

  async connectedCallback() {
    super.connectedCallback();
    this.updateActiveTab();
    this.issues = await getDuplicateIssues();
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
    const activeTab = this.tabs.find((tab) => currentPath.startsWith(tab.path));

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
      <div class="container">
        <div class="header">
          <h1 class="title">Issues Dashboard</h1>
        </div>
        ${this.issues.length > 0
          ? html`
              <sl-menu>
                ${this.issues.map(
                  (issue) => html`<sl-menu-item>${issue.title}</sl-menu-item>`
                )}
              </sl-menu>
            `
          : html`
              <sl-alert variant="primary" open>
                <sl-icon slot="icon" name="info-circle"></sl-icon>
                No duplicate issues found.
              </sl-alert>
            `}
      </div>
    `;
  }
}
