import {
  addTracker,
  validateTrackerToken,
  listProjectsForOrg,
} from '../api';
import { LitElement, html, css, TemplateResult } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/progress-bar/progress-bar.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import { SlDialog } from '@shoelace-style/shoelace';

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
    sl-details {
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
      <sl-dialog
        label="${this.step === 1
          ? 'Add New Tracker: Credentials'
          : 'Add New Tracker: Project Scope'}"
        .open="${this.opened}"
        @sl-hide="${() => (this.opened = false)}"
        @sl-after-hide="${() => this.reset()}"
      >
        <div class="form-container">
          ${this.isConnecting || this.isSaving
            ? html`<sl-progress-bar indeterminate></sl-progress-bar>`
            : ''}
          ${this.step === 1 ? this.renderStep1() : this.renderStep2()}
          ${this.errorMessage ? html`<div class="error-message">${this.errorMessage}</div>` : ''}
        </div>
        <sl-button slot="footer" @click="${() => (this.opened = false)}">Cancel</sl-button>
        ${this.step > 1
          ? html`<sl-button slot="footer" @click="${() => (this.step = 1)}">Previous</sl-button>`
          : ''}
        <sl-button
          slot="footer"
          variant="primary"
          @click="${this.handleNextOrSave}"
          .disabled="${this.step === 1
            ? this.isStep1Invalid || this.isConnecting
            : this.isSaving}"
          .loading="${this.isConnecting || this.isSaving}"
        >
          ${this.step === 1 ? 'Next' : 'Save'}
        </sl-button>
      </sl-dialog>
    `;
  }

  private renderStep1(): TemplateResult {
    return html`
      <sl-input
        label="Tracker Name"
        .value="${this.trackerName}"
        @sl-input="${(e: Event) => (this.trackerName = (e.target as HTMLInputElement).value)}"
        required
      ></sl-input>
      <sl-select
        label="Tracker Type"
        .value="${this.trackerType}"
        @sl-change="${(e: CustomEvent) => (this.trackerType = e.detail.item.value)}"
        required
      >
        <sl-menu-item value="github">GitHub</sl-menu-item>
        <sl-menu-item value="gitlab">GitLab</sl-menu-item>
        <sl-menu-item value="jira">Jira</sl-menu-item>
      </sl-select>
      <sl-input
        label="Tracker URL"
        .value="${this.trackerUrl}"
        @sl-input="${(e: Event) => (this.trackerUrl = (e.target as HTMLInputElement).value)}"
        required
      ></sl-input>
      <sl-input
        type="password"
        label="Access Token"
        .value="${this.trackerToken}"
        @sl-input="${(e: Event) => (this.trackerToken = (e.target as HTMLInputElement).value)}"
        required
        password-toggle
      ></sl-input>
      ${this.trackerType === 'jira'
        ? html`
            <sl-input
              label="Jira Username"
              .value="${this.jiraUsername}"
              @sl-input="${(e: Event) =>
                (this.jiraUsername = (e.target as HTMLInputElement).value)}"
              required
            ></sl-input>
          `
        : ''}
    `;
  }

  private renderStep2(): TemplateResult {
    return html`
      <div class="project-tree">
        ${this.orgs.map(
          (org, index) => html`
            <sl-details
              summary="${org.name}"
              @sl-show="${() => this.loadProjectsForOrg(index)}"
            >
              <div slot="summary" class="org-header">
                <sl-checkbox
                  .checked="${this.isOrgSelected(org)}"
                  .indeterminate="${this.isOrgIndeterminate(org)}"
                  @click="${(e: Event) => e.stopPropagation()}"
                  @sl-change="${(e: Event) => {
                    this.toggleOrg(org, (e.target as HTMLInputElement).checked);
                  }}"
                ></sl-checkbox>
                <span>${org.name}</span>
              </div>
              ${org.loading
                ? html`<sl-progress-bar indeterminate></sl-progress-bar>`
                : html`
                    <div class="project-list">
                      ${org.children.map(
                        proj => html`
                          <div class="project-item">
                            <sl-checkbox
                              .checked="${this.selectedProjects.has(
                                proj.identifier
                              )}"
                              @sl-change="${() => this.toggleProject(proj)}"
                            >
                              ${proj.name}
                            </sl-checkbox>
                          </div>
                        `
                      )}
                    </div>
                  `}
            </sl-details>
          `
        )}
      </div>
      <sl-checkbox
        .checked="${this.includeFutureProjects}"
        @sl-change="${(e: Event) =>
          (this.includeFutureProjects = (e.target as HTMLInputElement).checked)}"
      >
        Automatically include new projects created in the future
      </sl-checkbox>
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