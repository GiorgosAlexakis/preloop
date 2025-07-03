import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { listOrganizations, listProjects, Organization, Project } from '../api';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/tree/tree.js';
import '@shoelace-style/shoelace/dist/components/tree-item/tree-item.js';

@customElement('project-filter-modal')
export class ProjectFilterModal extends LitElement {
  @property({ type: Boolean, reflect: true }) open = false;
  @property({ type: Array }) initialSelectedProjectIds: string[] = [];

  @state() private organizations: Organization[] = [];
  @state() private projects: Project[] = [];
  @state() private selectedProjectIds: string[] = [];

  static styles = css`
    sl-dialog::part(body) {
      overflow-y: auto;
    }
  `;

  async willUpdate(changedProperties: Map<string | symbol, unknown>) {
    if (changedProperties.has('open') && this.open) {
      // When modal opens, sync internal state with initial state passed from parent
      this.selectedProjectIds = [...this.initialSelectedProjectIds];
      this.fetchData();
    }
  }

  async fetchData() {
    try {
      const [orgs, projs] = await Promise.all([
        listOrganizations(),
        listProjects(),
      ]);

      this.organizations = Array.isArray(orgs) ? orgs : [];
      this.projects = Array.isArray(projs) ? projs : [];
    } catch (error) {
      console.error('Failed to fetch data for project filter:', error);
      this.organizations = [];
      this.projects = [];
    }
  }

  handleSelect(event: CustomEvent) {
    const selection = event.detail.selection as HTMLElement[];
    this.selectedProjectIds = selection
      .map((item) => item.dataset.projectId)
      .filter(Boolean) as string[];
  }

  handleApply() {
    this.dispatchEvent(
      new CustomEvent('projects-selected', {
        detail: { projectIds: this.selectedProjectIds },
        bubbles: true,
        composed: true,
      })
    );
    // The parent will now be responsible for closing the modal.
  }

  render() {
    const projectsByOrg = this.projects.reduce(
      (acc, project) => {
        const orgId = project.organization_id;
        if (!acc.has(orgId)) {
          acc.set(orgId, []);
        }
        acc.get(orgId)!.push(project);
        return acc;
      },
      new Map<number, Project[]>()
    );

    return html`
      <sl-dialog
        label="Filter by Project"
        .open=${this.open}
        @sl-hide=${() => this.dispatchEvent(new CustomEvent('close-modal'))}
      >
        <sl-tree selection="multiple" @sl-selection-change=${this.handleSelect}>
          ${this.organizations.map((org) => {
            const projectsInOrg = projectsByOrg.get(org.id) || [];
            const selectedProjectsInOrg = projectsInOrg.filter((p) =>
              this.selectedProjectIds.includes(p.id.toString())
            );

            const allSelected =
              projectsInOrg.length > 0 &&
              selectedProjectsInOrg.length === projectsInOrg.length;
            const someSelected =
              selectedProjectsInOrg.length > 0 &&
              selectedProjectsInOrg.length < projectsInOrg.length;

            return html`
              <sl-tree-item ?selected=${allSelected} ?indeterminate=${someSelected}>
                ${org.name}
                ${projectsInOrg.map(
                  (proj) =>
                    html`<sl-tree-item
                      data-project-id="${proj.id}"
                      ?selected=${this.selectedProjectIds.includes(
                        proj.id.toString()
                      )}
                      >${proj.name}</sl-tree-item
                    >`
                )}
              </sl-tree-item>
            `;
          })}
        </sl-tree>
        <sl-button slot="footer" @click=${() => this.dispatchEvent(new CustomEvent('close-modal'))}>Cancel</sl-button>
        <sl-button slot="footer" variant="primary" @click=${this.handleApply}>Apply</sl-button>
      </sl-dialog>
    `;
  }
}
