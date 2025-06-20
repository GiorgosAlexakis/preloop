import {
  addTracker,
  validateTrackerToken,
  listProjectsForOrg,
} from '../api';
import { LitElement, html, css, render as litRender, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@vaadin/dialog';
import '@vaadin/form-layout';
import '@vaadin/text-field';
import '@vaadin/password-field';
import '@vaadin/select';
import '@vaadin/button';
import '@vaadin/checkbox';
import '@vaadin/progress-bar';
import '@vaadin/details';

interface Project {
  id: string;
  name: string;
  identifier: string;
}

interface Organization {
  id: string;
  name: string;
  children: Project[];
  loading?: boolean;
  projectsLoaded?: boolean;
}

@customElement('add-tracker-modal')
export class AddTrackerModal extends LitElement {
  @property({ type: Boolean })
  opened = false;

  @state()
  private step = 1;

  @state()
  private trackerName = '';

  @state()
  private trackerType = '';

  @state()
  private trackerUrl = '';

  @state()
  private trackerToken = '';

  @state()
  private jiraUsername = '';

  @state()
  private orgs: Organization[] = [];

  @state()
  private selectedProjects: Set<string> = new Set();

  @state()
  private includeFutureProjects = true;

  @state()
  private isConnecting = false;

  @state()
  private isSaving = false;

  @state()
  private errorMessage = '';

  static styles = css`
    .form-container {
      display: flex;
      flex-direction: column;
      gap: 1rem;
      width: 500px;
    }
    .project-tree {
      max-height: 300px;
      overflow-y: auto;
    }
    .project-item {
      margin-left: 1rem;
    }
    .org-header {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .error-message {
      color: var(--lumo-error-text-color);
    }
    vaadin-details {
      margin-bottom: 0.5rem;
    }
  `;

  private get isStep1Invalid() {
    if (!this.trackerName || !this.trackerType || !this.trackerUrl || !this.trackerToken) {
      return true;
    }
    if (this.trackerType === 'jira' && !this.jiraUsername) {
      return true;
    }
    return false;
  }

  render() {
    return html`
      <vaadin-dialog
        header-title="${this.step === 1
          ? 'Add New Tracker: Credentials'
          : 'Add New Tracker: Project Scope'}"
        .opened="${this.opened}"
        @opened-changed="${(e: CustomEvent) => {
          if (!e.detail.value) this.reset();
          this.opened = e.detail.value;
        }}"
        .renderer="${this.renderForm}"
      ></vaadin-dialog>
    `;
  }

  private renderForm = (root: HTMLElement) => {
    litRender(
      html`
        <div class="form-container">
          ${this.isConnecting || this.isSaving
            ? html`<vaadin-progress-bar indeterminate></vaadin-progress-bar>`
            : ''}
          ${this.step === 1 ? this.renderStep1() : this.renderStep2()}
          ${this.errorMessage ? html`<div class="error-message">${this.errorMessage}</div>` : ''}
          <div style="display: flex; justify-content: flex-end; gap: 1rem; margin-top: 1rem;">
            <vaadin-button @click="${() => (this.opened = false)}">Cancel</vaadin-button>
            ${this.step > 1
              ? html`<vaadin-button @click="${() => (this.step = 1)}">Previous</vaadin-button>`
              : ''}
            <vaadin-button
              theme="primary"
              @click="${this.handleNextOrSave}"
              .disabled="${this.step === 1
                ? this.isStep1Invalid || this.isConnecting
                : this.isSaving}"
            >
              ${this.isConnecting
                ? 'Connecting...'
                : this.step === 1
                ? 'Next'
                : 'Save'}
            </vaadin-button>
          </div>
        </div>
      `,
      root
    );
  };

  private renderStep1(): TemplateResult {
    return html`
      <vaadin-text-field
        label="Tracker Name"
        .value="${this.trackerName}"
        @value-changed="${(e: CustomEvent) => (this.trackerName = e.detail.value)}"
        required
      ></vaadin-text-field>
      <vaadin-select
        label="Tracker Type"
        .items="${[
          { label: 'GitHub', value: 'github' },
          { label: 'GitLab', value: 'gitlab' },
          { label: 'Jira', value: 'jira' },
        ]}"
        .value="${this.trackerType}"
        @value-changed="${(e: CustomEvent) => (this.trackerType = e.detail.value)}"
        required
      ></vaadin-select>
      <vaadin-text-field
        label="Tracker URL"
        .value="${this.trackerUrl}"
        @value-changed="${(e: CustomEvent) => (this.trackerUrl = e.detail.value)}"
        required
      ></vaadin-text-field>
      <vaadin-password-field
        label="Access Token"
        .value="${this.trackerToken}"
        @value-changed="${(e: CustomEvent) => (this.trackerToken = e.detail.value)}"
        required
      ></vaadin-password-field>
      ${this.trackerType === 'jira'
        ? html`
            <vaadin-text-field
              label="Jira Username"
              .value="${this.jiraUsername}"
              @value-changed="${(e: CustomEvent) => (this.jiraUsername = e.detail.value)}"
              required
            ></vaadin-text-field>
          `
        : ''}
    `;
  }

  private renderStep2(): TemplateResult {
    return html`
      <div class="project-tree">
        ${this.orgs.map(
          (org, index) => html`
            <vaadin-details
              @opened-changed="${(e: CustomEvent) => {
                if (e.detail.value) this.loadProjectsForOrg(index);
              }}"
            >
              <div slot="summary" class="org-header">
                <vaadin-checkbox
                  .checked="${this.isOrgSelected(org)}"
                  .indeterminate="${this.isOrgIndeterminate(org)}"
                  @click="${(e: Event) => e.stopPropagation()}"
                  @change="${(e: Event) => {
                    this.toggleOrg(org, (e.target as HTMLInputElement).checked);
                  }}"
                ></vaadin-checkbox>
                <span>${org.name}</span>
              </div>
              ${org.loading
                ? html`<vaadin-progress-bar indeterminate></vaadin-progress-bar>`
                : html`
                    <div class="project-list">
                      ${org.children.map(
                        proj => html`
                          <div class="project-item">
                            <vaadin-checkbox
                              .checked="${this.selectedProjects.has(
                                proj.identifier
                              )}"
                              @change="${() => this.toggleProject(proj)}"
                              .label="${proj.name}"
                            ></vaadin-checkbox>
                          </div>
                        `
                      )}
                    </div>
                  `}
            </vaadin-details>
          `
        )}
      </div>
      <vaadin-checkbox
        .checked="${this.includeFutureProjects}"
        @change="${(e: Event) =>
          (this.includeFutureProjects = (e.target as HTMLInputElement).checked)}"
        label="Automatically include new projects created in the future"
      ></vaadin-checkbox>
    `;
  }

  private handleNextOrSave = async () => {
    this.errorMessage = '';
    if (this.step === 1) {
      await this.testConnection();
    } else {
      await this.handleSave();
    }
  };

  private async testConnection() {
    if (!this.trackerName || !this.trackerType || !this.trackerUrl || !this.trackerToken) {
      this.errorMessage = 'Please fill in all required fields.';
      return;
    }

    this.isConnecting = true;
    try {
      const response = await validateTrackerToken(
        this.trackerType,
        this.trackerToken,
        this.trackerUrl,
        this.jiraUsername
      );
      this.orgs =
        response.orgs?.map((org: any) => ({
          id: org.id,
          name: org.name,
          children: [],
          loading: false,
          projectsLoaded: false,
        })) || [];
      this.step = 2;
    } catch (error: any) {
      this.errorMessage = error.message || 'Failed to connect to the tracker.';
    } finally {
      this.isConnecting = false;
    }
  }

  private async handleSave() {
    this.isSaving = true;
    const allProjectIdentifiers = this.orgs.flatMap(org => org.children.map(p => p.identifier));
    const includedProjectIdentifiers = this.includeFutureProjects ? null : Array.from(this.selectedProjects);
    const excludedProjectIdentifiers = this.includeFutureProjects ? allProjectIdentifiers.filter(id => !this.selectedProjects.has(id)) : null;

    const trackerData = {
      name: this.trackerName,
      type: this.trackerType,
      url: this.trackerUrl,
      token: this.trackerToken,
      config: this.trackerType === 'jira' ? { username: this.jiraUsername } : undefined,
      include_future_projects: this.includeFutureProjects,
      included_project_identifiers: includedProjectIdentifiers,
      excluded_project_identifiers: excludedProjectIdentifiers,
    };

    try {
      await addTracker(trackerData);
      this.dispatchEvent(new CustomEvent('save'));
      this.opened = false;
    } catch (error: any) {
      this.errorMessage = error.message || 'Failed to save tracker.';
    } finally {
      this.isSaving = false;
    }
  }

  private async loadProjectsForOrg(index: number) {
    const org = this.orgs[index];
    if (!org || org.projectsLoaded) return;

    org.loading = true;
    this.requestUpdate();

    try {
      const response = await listProjectsForOrg(
        this.trackerType,
        this.trackerToken,
        org.id,
        this.trackerUrl,
        this.jiraUsername
      );
      org.children = response.projects || [];
      org.projectsLoaded = true;
      // Add all newly fetched projects to the selection by default
      org.children.forEach(p => this.selectedProjects.add(p.identifier));
    } catch (error: any) {
      this.errorMessage = error.message || `Failed to fetch projects for ${org.name}.`;
    } finally {
      org.loading = false;
      this.requestUpdate();
    }
  }

  private isOrgSelected(org: Organization): boolean {
    if (!org.projectsLoaded || org.children.length === 0) return false;
    return org.children.every(p => this.selectedProjects.has(p.identifier));
  }

  private isOrgIndeterminate(org: Organization): boolean {
    if (!org.projectsLoaded) return false;
    const selectedCount = org.children.filter(p => this.selectedProjects.has(p.identifier)).length;
    return selectedCount > 0 && selectedCount < org.children.length;
  }

  private toggleOrg(org: Organization, checked: boolean) {
    // Ensure projects are loaded before toggling
    if (!org.projectsLoaded) {
      // You might want to load them here if they aren't already
      return;
    }
    org.children.forEach(p => {
      if (checked) {
        this.selectedProjects.add(p.identifier);
      } else {
        this.selectedProjects.delete(p.identifier);
      }
    });
    this.requestUpdate();
  }

  private toggleProject(project: Project) {
    if (this.selectedProjects.has(project.identifier)) {
      this.selectedProjects.delete(project.identifier);
    } else {
      this.selectedProjects.add(project.identifier);
    }
    this.requestUpdate();
  }

  private reset() {
    this.step = 1;
    this.trackerName = '';
    this.trackerType = '';
    this.trackerUrl = '';
    this.trackerToken = '';
    this.jiraUsername = '';
    this.orgs = [];
    this.selectedProjects = new Set();
    this.includeFutureProjects = true;
    this.isConnecting = false;
    this.isSaving = false;
    this.errorMessage = '';
  }
}