import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import * as api from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import type SlInput from '@shoelace-style/shoelace/dist/components/input/input.js';
import type SlTreeItem from '@shoelace-style/shoelace/dist/components/tree-item/tree-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/tree/tree.js';
import '@shoelace-style/shoelace/dist/components/tree-item/tree-item.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';

@customElement('add-tracker-modal')
export class AddTrackerModal extends LitElement {
  @property({ type: Object })
  tracker: any = null;

  /**
   * @internal
   */
  _api = api;

  @property({ type: Boolean })
  opened = true;

  @state()
  private step = 1;

  @state()
  private trackerName = '';

  @state()
  private trackerType = 'github';

  @state()
  private trackerUrl = 'https://api.github.com';

  @state()
  private trackerToken = '';

  @state()
  private trackerUsername = '';

  @state()
  private orgs: any[] = [];

  @state()
  private projects: Record<string, any[]> = {};

  @state()
  private selectedOrgs: Record<string, boolean> = {};

  @state()
  private selectedProjects: Record<string, Record<string, boolean>> = {};

  @state()
  private areAllProjectsSelected = false;

  @state()
  private includeFutureProjects = true;

  @state()
  private isLoading = false;

  @state()
  private errorMessage = '';

  @state()
  private warningMessages: string[] = [];

  static styles = css`
    .error {
      color: var(--sl-color-danger-700);
    }
    sl-input,
    sl-select {
      margin-bottom: 1rem;
    }
    .select-all {
      margin-bottom: 1rem;
      margin-left: 0.5rem;
    }
    .include-future {
      margin-left: 0.5rem;
      margin-top: 1rem;
    }
  `;

  connectedCallback() {
    super.connectedCallback();
    if (this.tracker) {
      this.trackerName = this.tracker.name;
      this.trackerType = this.tracker.tracker_type;
      this.trackerUrl = this.tracker.url;
      this.trackerToken = 'unchanged';
      this.trackerUsername = this.tracker.connection_details?.username;
      this.selectedOrgs = this.tracker.scope_rules
        .filter(
          (x: any) => x.rule_type == 'INCLUDE' && x.scope_type == 'ORGANIZATION'
        )
        .reduce((acc: any, x: any) => {
          acc[x.identifier] = true;
          return acc;
        }, {});
      this.selectedProjects = {};
      // Object.keys(this.selectedOrgs).forEach((orgId: any) => {
      //   this.selectedProjects[orgId] = {};
      //   this.projects[orgId]?.forEach((project: any) => {
      //     if (this.tracker.scope_rules.filter((x: any) => x.scope_type == 'PROJECT' && x.rule_type == 'INCLUDE' && x.identifier == project.id).length ||
      //         !this.tracker.scope_rules.filter((x: any) => x.scope_type == 'PROJECT' && x.rule_type == 'EXCLUDE' && x.identifier == project.id).length) {
      //       this.selectedProjects[orgId][project.id] = true;
      //     }
      //   });
      // });
      this.includeFutureProjects = !this.tracker.scope_rules.filter(
        (x: any) => x.rule_type == 'INCLUDE' && x.scope_type == 'PROJECT'
      ).length;
      // Token is not pre-filled for security reasons
      if (this.tracker) {
        this.trackerToken = 'unchanged';
      }
    }
  }
  firstUpdated() {
    this.shadowRoot?.querySelector('sl-dialog')?.show();
    setTimeout(() => {
      const input = this.shadowRoot?.querySelector<SlInput>('sl-input');
      input?.focus();
    }, 100);
  }
  render() {
    return html`
      <sl-dialog
        label="${this.tracker ? 'Edit' : 'Add'} Tracker"
        @sl-request-close=${() => this.closeModal()}
      >
        ${this.step === 1 ? this.renderStep1() : this.renderStep2()}
        ${this.warningMessages.length > 0
          ? html`
              <sl-alert variant="warning" open style="margin-top: 1rem;">
                <sl-icon slot="icon" name="exclamation-triangle"></sl-icon>
                <strong>Warnings:</strong>
                <ul style="margin: 0.5rem 0 0 0; padding-left: 1.5rem;">
                  ${this.warningMessages.map((w) => html`<li>${w}</li>`)}
                </ul>
              </sl-alert>
            `
          : ''}
        ${this.errorMessage
          ? html`<p class="error">${this.errorMessage}</p>`
          : ''}
        <div slot="footer">${this.renderFooterButtons()}</div>
      </sl-dialog>
    `;
  }

  renderFooterButtons() {
    // Show "Done" button after successful save with warnings
    if (this.warningMessages.length > 0) {
      return html`
        <sl-button variant="primary" @click=${() => this.closeModal(true)}>
          Done
        </sl-button>
      `;
    }
    if (this.step === 1) {
      return html`
        <sl-button @click=${() => this.closeModal()}>Cancel</sl-button>
        <sl-button
          variant="primary"
          @click=${this.testConnection}
          .loading=${this.isLoading}
          >Next</sl-button
        >
      `;
    }
    return html`
      <sl-button @click=${() => (this.step = 1)}>Back</sl-button>
      <sl-button
        variant="primary"
        @click=${this.handleSave}
        .loading=${this.isLoading}
      >
        ${this.tracker ? 'Save' : 'Add'}
      </sl-button>
    `;
  }

  renderStep1() {
    return html`
      <sl-input
        label="Name"
        name="name"
        .value=${this.trackerName}
        @sl-input=${(e: any) => (this.trackerName = e.target.value)}
        required
        tabindex="0"
        autofocus
      ></sl-input>
      <sl-select
        label="Type"
        name="type"
        .value=${this.trackerType}
        @sl-change=${(e: any) => {
          this.trackerType = e.target.value;
          const urlInput = this.shadowRoot?.querySelector(
            'sl-input[name="url"]'
          ) as HTMLInputElement;
          if (this.trackerType === 'gitlab') {
            this.trackerUrl = 'https://gitlab.com';
            if (urlInput) {
              urlInput.placeholder = 'e.g., https://gitlab.example.com';
            }
          } else if (this.trackerType === 'github') {
            this.trackerUrl = 'https://github.com';
            if (urlInput) {
              urlInput.placeholder = 'e.g., https://github.example.com';
            }
          } else {
            this.trackerUrl = '';
            if (urlInput) {
              urlInput.placeholder = 'e.g., https://your-team.atlassian.net';
            }
          }
        }}
      >
        <sl-option value="github">GitHub</sl-option>
        <sl-option value="gitlab">GitLab</sl-option>
        <sl-option value="jira">Jira</sl-option>
      </sl-select>
      <sl-input
        label="URL"
        name="url"
        .value=${this.trackerUrl}
        @sl-input=${(e: any) => (this.trackerUrl = e.target.value)}
        placeholder="e.g., https://github.example.com"
      ></sl-input>
      ${this.trackerType === 'jira'
        ? html`
            <sl-input
              label="Jira Username"
              name="username"
              .value=${this.trackerUsername}
              @sl-input=${(e: any) => (this.trackerUsername = e.target.value)}
              required
            ></sl-input>
          `
        : ''}
      <sl-input
        type="password"
        label="API Key"
        name="api_key"
        .value=${this.trackerToken}
        @sl-input=${(e: any) => (this.trackerToken = e.target.value)}
        required
      ></sl-input>
    `;
  }

  renderStep2() {
    return html`
      <h2>Configure Project Scope</h2>
      <div>
        <sl-checkbox
          .checked=${this.areAllProjectsSelected}
          @sl-change=${this.toggleSelectAll}
          class="select-all"
        >
          Select All
        </sl-checkbox>
      </div>
      ${this.renderOrgTree()}
      <div>
        <sl-checkbox
          .checked=${this.includeFutureProjects}
          @sl-change=${(e: any) =>
            (this.includeFutureProjects = e.target.checked)}
          class="include-future"
        >
          Include future projects
        </sl-checkbox>
      </div>
    `;
  }

  renderOrgTree() {
    setTimeout(() => {
      this.shadowRoot
        ?.querySelectorAll('sl-tree-item')
        ?.forEach((item: any) => {
          if (item.selected) {
            item.dispatchEvent(
              new CustomEvent('sl-lazy-load', { bubbles: true })
            );
          }
        });
    }, 300);
    return html`
      <sl-tree
        selection="multiple"
        @sl-selection-change=${this.handleSelectionChange}
      >
        ${this.orgs.map(
          (org: any) => html`
            <sl-tree-item
              value="${org.id}"
              ?selected=${this.selectedOrgs[org.id]}
              ?lazy=${!this.projects[org.id]}
              ?loading=${this.isLoading}
              ?expanded=${this.selectedOrgs[org.id]}
              @sl-lazy-load=${(e: { target: SlTreeItem }) =>
                this.loadProjects(org.id, e.target)}
            >
              ${org.name}
              ${this.projects[org.id]?.map(
                (proj: any) => html`
                  <sl-tree-item
                    value="${proj.id}"
                    ?selected=${this.selectedProjects[org.id]?.[proj.id]}
                  >
                    ${proj.name}
                  </sl-tree-item>
                `
              )}
            </sl-tree-item>
          `
        )}
      </sl-tree>
    `;
  }

  async testConnection() {
    this.isLoading = true;
    this.errorMessage = '';
    try {
      const response = await this._api.validateTrackerToken(
        this.trackerType,
        this.trackerToken,
        this.trackerUrl,
        this.trackerUsername,
        this.tracker?.id
      );
      if (!response.success) {
        this.errorMessage = response.message.split('\n')[0];
        return;
      }
      this.orgs = response.orgs;
      this.step = 2;
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }

  async loadProjects(orgId: string, item?: SlTreeItem) {
    if (this.projects[orgId]) {
      // Projects already loaded
      return;
    }
    this.isLoading = true;
    if (item) {
      item.loading = true;
    }
    try {
      const projects = await this._api.listProjectsForOrg(
        this.trackerType,
        this.trackerToken,
        orgId,
        this.trackerUrl,
        this.trackerUsername,
        this.tracker?.id
      );
      this.projects = { ...this.projects, [orgId]: projects };
      if (this.selectedOrgs[orgId]) {
        if (!this.includeFutureProjects) {
          this.selectedProjects[orgId] = projects.reduce(
            (acc: Record<string, boolean>, proj: any) => {
              acc[proj.id] =
                this.tracker?.scope_rules.filter(
                  (x: any) =>
                    x.rule_type == 'INCLUDE' &&
                    x.scope_type == 'PROJECT' &&
                    x.identifier == proj.id
                ).length > 0;
              return acc;
            },
            {} as Record<string, boolean>
          );
        } else {
          this.selectedProjects[orgId] = projects.reduce(
            (acc: Record<string, boolean>, proj: any) => {
              acc[proj.id] =
                this.tracker?.scope_rules.filter(
                  (x: any) =>
                    x.rule_type == 'EXCLUDE' &&
                    x.scope_type == 'PROJECT' &&
                    x.identifier == proj.id
                ).length == 0;
              return acc;
            },
            {} as Record<string, boolean>
          );
        }
      }
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
      if (item) {
        item.loading = false;
        item.lazy = false;
      }
      this.requestUpdate();
    }
  }

  handleSelectionChange(event: CustomEvent) {
    const selectedItems = event.detail.selection as SlTreeItem[];
    const newSelectedOrgs: Record<string, boolean> = {};
    const newSelectedProjects: Record<string, Record<string, boolean>> = {};
    // Initialize projects map
    this.orgs.forEach((org) => {
      newSelectedProjects[org.id] = {};
    });

    selectedItems.forEach((item) => {
      const project = item.getAttribute('value');
      const org = item.parentElement?.getAttribute('value');
      if (!org || !project) return;
      newSelectedOrgs[org] = true;
      newSelectedProjects[org][project] = true;
    });

    this.selectedOrgs = newSelectedOrgs;
    this.selectedProjects = newSelectedProjects;
    this.updateSelectAllState();
  }

  async toggleSelectAll() {
    this.areAllProjectsSelected = !this.areAllProjectsSelected;

    if (this.areAllProjectsSelected) {
      this.isLoading = true;
      const promises = this.orgs
        .filter((org) => !this.projects[org.id])
        .map((org) => this.loadProjects(org.id));
      await Promise.all(promises);
      this.isLoading = false;
    }

    const newSelectedOrgs: Record<string, boolean> = {};
    const newSelectedProjects: Record<string, Record<string, boolean>> = {};

    this.orgs.forEach((org) => {
      newSelectedOrgs[org.id] = this.areAllProjectsSelected;
      newSelectedProjects[org.id] = {};
      if (this.projects[org.id]) {
        this.projects[org.id].forEach((proj) => {
          newSelectedProjects[org.id][proj.id] = this.areAllProjectsSelected;
        });
      }
    });

    this.selectedOrgs = newSelectedOrgs;
    this.selectedProjects = newSelectedProjects;
    this.requestUpdate();
  }

  updateSelectAllState() {
    // Only consider loaded projects for the "Select All" state
    const loadedProjects = this.orgs
      .filter((org) => this.projects[org.id])
      .flatMap((org) => this.projects[org.id]);

    if (loadedProjects.length === 0) {
      this.areAllProjectsSelected = false;
      return;
    }

    let allSelected = true;
    for (const org of this.orgs) {
      if (this.projects[org.id]) {
        for (const proj of this.projects[org.id]) {
          if (!this.selectedProjects[org.id]?.[proj.id]) {
            allSelected = false;
            break;
          }
        }
      }
      if (!allSelected) break;
    }
    this.areAllProjectsSelected = allSelected;
  }

  async handleSave() {
    this.isLoading = true;
    this.errorMessage = '';
    const scopeRules = [];
    for (const org of this.orgs) {
      if (this.selectedOrgs[org.id]) {
        scopeRules.push({
          rule_type: 'INCLUDE',
          scope_type: 'ORGANIZATION',
          identifier: org.id,
        });
        if (this.includeFutureProjects) {
          for (const proj of this.projects[org.id] || []) {
            if (!this.selectedProjects[org.id]?.[proj.id]) {
              scopeRules.push({
                rule_type: 'EXCLUDE',
                scope_type: 'PROJECT',
                identifier: proj.id,
              });
            }
          }
        } else {
          for (const proj of this.projects[org.id] || []) {
            if (this.selectedProjects[org.id]?.[proj.id]) {
              scopeRules.push({
                rule_type: 'INCLUDE',
                scope_type: 'PROJECT',
                identifier: proj.id,
              });
            }
          }
        }
      }
    }

    const trackerData = {
      name: this.trackerName,
      type: this.trackerType,
      url: this.trackerUrl,
      api_key: this.trackerToken,
      scope_rules: scopeRules,
      config: {
        username: this.trackerUsername,
      },
    };

    try {
      let response;
      if (this.tracker) {
        response = await this._api.updateTracker(this.tracker.id, trackerData);
        this.dispatchEvent(
          new CustomEvent('tracker-updated', {
            detail: { tracker: response },
          })
        );
      } else {
        response = await this._api.addTracker(trackerData);
        this.dispatchEvent(
          new CustomEvent('tracker-added', {
            detail: { tracker: response },
          })
        );
      }

      // Check for warnings in response and display them before closing
      if (response?.warnings && response.warnings.length > 0) {
        this.warningMessages = response.warnings;
        this.isLoading = false;
        // Don't close modal yet - let user see the warnings
        return;
      }

      this.closeModal(true);
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }

  closeModal(success = false) {
    if (typeof success !== 'boolean') {
      success = false;
    }
    const event = new CustomEvent('close-modal', {
      bubbles: true,
      composed: true,
      detail: { success },
    });
    this.dispatchEvent(event);
    this.opened = false;
  }
}
