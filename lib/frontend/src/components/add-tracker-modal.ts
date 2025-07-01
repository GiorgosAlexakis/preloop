import { LitElement, html, css, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import {
  addTracker,
  updateTracker,
  validateTrackerToken,
  listProjectsForOrg,
} from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import type SlInput from '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';

@customElement('add-tracker-modal')
export class AddTrackerModal extends LitElement {
  @property({ type: Object })
  tracker: any = null;

  @property({ type: Boolean })
  opened = true;

  @state()
  private step = 1;

  @state()
  private trackerName = '';

  @state()
  private trackerType = 'github';

  @state()
  private trackerUrl = '';

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
  private singleOrgWithProjects = false;

  @state()
  private areAllProjectsSelected = false;

  @state()
  private includeFutureProjects = true;

  @state()
  private isLoading = false;

  @state()
  private errorMessage = '';

  static styles = css`
    .error {
      color: var(--sl-color-danger-700);
    }
    sl-input,
    sl-select {
      margin-bottom: 1rem;
    }
    .projects {
      padding-left: 2rem;
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
      this.orgs = this.tracker.scope_rules.organizations;
      this.projects = this.tracker.scope_rules.projects;
      this.selectedOrgs = this.tracker.scope_rules
        .filter(
          (x: any) => x.rule_type == 'INCLUDE' && x.scope_type == 'ORGANIZATION'
        )
        .reduce((acc: any, x: any) => {
          acc[x.identifier] = true;
          return acc;
        }, {});
      this.selectedProjects = this.tracker.scope_rules
        .filter(
          (x: any) => x.rule_type == 'EXCLUDE' && x.scope_type == 'PROJECT'
        )
        .reduce((acc: any, x: any) => {
          acc[x.identifier] = false;
          return acc;
        }, {});
      this.includeFutureProjects =
        this.tracker.scope_rules.filter(
          (x: any) => x.rule_type == 'INCLUDE' && x.scope_type == 'PROJECT'
        ).length > 0;
      // Token is not pre-filled for security reasons
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
        ${this.errorMessage
          ? html`<p class="error">${this.errorMessage}</p>`
          : ''}
        <div slot="footer">${this.renderFooterButtons()}</div>
      </sl-dialog>
    `;
  }

  renderFooterButtons() {
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
        @sl-change=${(e: any) => (this.trackerType = e.target.value)}
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
        placeholder="e.g., https://gitlab.com"
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
        label="Access Token"
        name="token"
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
        >
          Select All
        </sl-checkbox>
      </div>
      ${this.singleOrgWithProjects
        ? this.renderProjectsForSingleOrg()
        : this.renderOrgTree()}
      <div>
        <sl-checkbox
          .checked=${this.includeFutureProjects}
          @sl-change=${(e: any) =>
            (this.includeFutureProjects = e.target.checked)}
        >
          Include future projects
        </sl-checkbox>
      </div>
    `;
  }

  renderProjectsForSingleOrg() {
    const orgId = this.orgs[0].id;
    return html`
      <div class="projects">
        ${this.projects[orgId]?.map(
          (proj: any) => html`
            <div>
              <sl-checkbox
                .checked=${this.selectedProjects[orgId]?.[proj.id]}
                @sl-change=${() => this.toggleProject(orgId, proj.id)}
              >
                ${proj.name}
              </sl-checkbox>
            </div>
          `
        )}
      </div>
    `;
  }

  renderOrgTree() {
    return html`
      ${this.orgs.map(
        (org: any) => html`
          <div>
            <sl-icon-button
              .name=${this.projects[org.id] ? 'chevron-down' : 'chevron-right'}
              @click=${() => this.loadProjects(org.id)}
            ></sl-icon-button>
            <sl-checkbox
              .checked=${this.selectedOrgs[org.id]}
              @sl-change=${() => this.toggleOrg(org.id)}
            >
              ${org.name}
            </sl-checkbox>

            ${this.projects[org.id]
              ? html`
                  <div class="projects">
                    ${this.projects[org.id].map(
                      (proj: any) => html`
                        <div>
                          <sl-checkbox
                            .checked=${this.selectedProjects[org.id]?.[proj.id]}
                            @sl-change=${() =>
                              this.toggleProject(org.id, proj.id)}
                          >
                            ${proj.name}
                          </sl-checkbox>
                        </div>
                      `
                    )}
                  </div>
                `
              : ''}
          </div>
        `
      )}
    `;
  }

  async testConnection() {
    this.isLoading = true;
    this.errorMessage = '';
    try {
      const response = await validateTrackerToken(
        this.tracker?.id,
        this.trackerType,
        this.trackerToken,
        this.trackerUrl,
        this.trackerUsername
      );
      this.orgs = response.orgs;
      if (response.orgs.length === 1 && response.orgs[0].children?.length > 0) {
        this.singleOrgWithProjects = true;
        const orgId = response.orgs[0].id;
        this.projects = { [orgId]: response.orgs[0].children };
        this.selectedOrgs = { [orgId]: true };
      } else {
        this.singleOrgWithProjects = false;
      }
      this.step = 2;
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }

  async loadProjects(orgId: string) {
    if (this.projects[orgId]) {
      // Projects already loaded
      return;
    }
    this.isLoading = true;
    try {
      const projects = await listProjectsForOrg(
        this.trackerType,
        this.trackerToken,
        orgId,
        this.trackerUrl,
        this.trackerUsername
      );
      this.projects = { ...this.projects, [orgId]: projects };
    } catch (error: any) {
      this.errorMessage = error.message;
    } finally {
      this.isLoading = false;
    }
  }

  toggleOrg(orgId: string) {
    const isSelected = !this.selectedOrgs[orgId];
    this.selectedOrgs = {
      ...this.selectedOrgs,
      [orgId]: isSelected,
    };
    if (isSelected && !this.projects[orgId]) {
      this.loadProjects(orgId);
    }
    // When an org is toggled, we might need to update the "Select All" status
    this.updateSelectAllState();
  }

  toggleProject(orgId: string, projectId: string) {
    const orgProjects = this.selectedProjects[orgId] || {};
    const newOrgProjects = {
      ...orgProjects,
      [projectId]: !orgProjects[projectId],
    };
    this.selectedProjects = {
      ...this.selectedProjects,
      [orgId]: newOrgProjects,
    };
    this.updateSelectAllState();
  }

  toggleSelectAll() {
    this.areAllProjectsSelected = !this.areAllProjectsSelected;
    const newSelectedProjects: Record<string, Record<string, boolean>> = {};

    for (const org of this.orgs) {
      if (this.projects[org.id]) {
        newSelectedProjects[org.id] = {};
        for (const proj of this.projects[org.id]) {
          newSelectedProjects[org.id][proj.id] = this.areAllProjectsSelected;
        }
      }
    }
    this.selectedProjects = newSelectedProjects;
  }

  updateSelectAllState() {
    let allSelected = true;
    let hasProjects = false;
    for (const org of this.orgs) {
      if (this.projects[org.id]) {
        hasProjects = true;
        for (const proj of this.projects[org.id]) {
          if (!this.selectedProjects[org.id]?.[proj.id]) {
            allSelected = false;
            break;
          }
        }
      }
      if (!allSelected) break;
    }
    this.areAllProjectsSelected = hasProjects && allSelected;
  }

  async handleSave() {
    this.isLoading = true;
    this.errorMessage = '';

    const scopeRules = [];
    debugger;
    for (const org of this.orgs) {
      if (this.selectedOrgs[org.id]) {
        scopeRules.push({
          rule_type: 'INCLUDE',
          scope_type: 'ORGANIZATION',
          identifier: org.id,
        });
      }
      if (this.includeFutureProjects) {
        for (const proj of this.selectedOrgs[org.id]?.children || []) {
          if (!this.selectedProjects[org.id]?.[proj.id]) {
            scopeRules.push({
              rule_type: 'EXCLUDE',
              scope_type: 'PROJECT',
              identifier: proj.id,
            });
          }
        }
      } else {
        for (const proj of this.selectedOrgs[org.id]?.children || []) {
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

    const trackerData = {
      name: this.trackerName,
      type: this.trackerType,
      url: this.trackerUrl,
      token: this.trackerToken,
      scope_rules: scopeRules,
      config: {
        username: this.trackerUsername,
      },
    };

    try {
      if (this.tracker) {
        await updateTracker(this.tracker.id, trackerData);
      } else {
        await addTracker(trackerData);
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
  }
}
