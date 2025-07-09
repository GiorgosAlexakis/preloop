import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { Organization, Project } from '../api';
import type { SlTree } from '@shoelace-style/shoelace';

import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/tree/tree.js';
import '@shoelace-style/shoelace/dist/components/tree-item/tree-item.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio-button/radio-button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';

@customElement('project-filter-modal')
export class ProjectFilterModal extends LitElement {
  static styles = css`
    sl-tree {
      max-height: 300px;
      overflow-y: auto;
    }
    .filter-section {
      margin-bottom: var(--sl-spacing-medium);
    }
    .filter-label {
      font-weight: var(--sl-font-weight-semibold);
      margin-bottom: var(--sl-spacing-x-small);
      display: block;
    }
  `;

  @property({ type: Boolean }) open = false;
  @property({ type: Array }) organizations: Organization[] = [];
  @property({ type: Array }) projects: Project[] = [];
  @property({ type: Array }) selectedProjectIds: string[] = [];
  @property({ type: String }) selectedStatus: 'opened' | 'closed' | 'all' =
    'opened';

  @state() private draftSelectedProjectIds: string[] = [];
  @state() private draftSelectedStatus: 'opened' | 'closed' | 'all' = 'opened';

  willUpdate(changedProperties: Map<string, any>) {
    // When the dialog is opened, reset the draft state from the properties
    if (changedProperties.has('open') && this.open) {
      this.draftSelectedProjectIds = [...this.selectedProjectIds];
      this.draftSelectedStatus = this.selectedStatus;
    }
  }

  handleSelect(event: CustomEvent) {
    const selectedItems = event.detail.selection as HTMLElement[];
    const projectIds = selectedItems
      .map((item) => item.dataset.projectId)
      .filter((id) => id); // Filter out undefined from parent items

    this.draftSelectedProjectIds = [...new Set(projectIds)] as string[];
  }

  handleStatusChange(event: CustomEvent) {
    const radioGroup = event.target as any;
    this.draftSelectedStatus = radioGroup.value;
  }

  handleApply() {
    this.dispatchEvent(
      new CustomEvent('apply-filters', {
        detail: {
          selectedProjectIds: this.draftSelectedProjectIds,
          selectedStatus: this.draftSelectedStatus,
        },
      })
    );
    this.dispatchEvent(new CustomEvent('close-modal'));
  }

  render() {
    const projectsByOrg = this.projects.reduce((acc, p) => {
      // Assuming project has an organization_id. This is based on typical data structures.
      const orgId = p.organization_id;
      if (!acc.has(orgId)) {
        acc.set(orgId, []);
      }
      acc.get(orgId)!.push(p);
      return acc;
    }, new Map<number, Project[]>());

    return html`
      <sl-dialog
        label="Filters"
        .open=${this.open}
        @sl-hide=${() => this.dispatchEvent(new CustomEvent('close-modal'))}
      >
        <div
          class="filter-section"
          style="margin-top: var(--sl-spacing-medium);"
        >
          <label class="filter-label">Projects</label>
          <sl-tree
            selection="multiple"
            @sl-selection-change=${this.handleSelect}
          >
            ${this.organizations.map((org) => {
              const projectsInOrg = projectsByOrg.get(org.id) || [];
              const selectedProjectsInOrg = projectsInOrg.filter((p) =>
                this.draftSelectedProjectIds.includes(p.id.toString())
              );

              const allSelected =
                projectsInOrg.length > 0 &&
                selectedProjectsInOrg.length === projectsInOrg.length;
              const someSelected =
                selectedProjectsInOrg.length > 0 &&
                selectedProjectsInOrg.length < projectsInOrg.length;

              return html`
                <sl-tree-item
                  ?selected=${allSelected}
                  ?indeterminate=${someSelected}
                >
                  ${org.name}
                  ${projectsInOrg.map(
                    (proj) =>
                      html`<sl-tree-item
                        data-project-id="${proj.id}"
                        ?selected=${this.draftSelectedProjectIds.includes(
                          proj.id.toString()
                        )}
                        >${proj.name}</sl-tree-item
                      >`
                  )}
                </sl-tree-item>
              `;
            })}
          </sl-tree>
        </div>

        <sl-divider></sl-divider>

        <div class="filter-section">
          <label class="filter-label">Issue Status</label>
          <sl-radio-group
            value=${this.draftSelectedStatus}
            @sl-change=${this.handleStatusChange}
          >
            <sl-radio-button value="opened">Opened</sl-radio-button>
            <sl-radio-button value="closed">Closed</sl-radio-button>
            <sl-radio-button value="all">All</sl-radio-button>
          </sl-radio-group>
        </div>

        <sl-button
          slot="footer"
          @click=${() => this.dispatchEvent(new CustomEvent('close-modal'))}
          >Cancel</sl-button
        >
        <sl-button slot="footer" variant="primary" @click=${this.handleApply}
          >Apply</sl-button
        >
      </sl-dialog>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'project-filter-modal': ProjectFilterModal;
  }
}
