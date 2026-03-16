var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/tree/tree.js';
import '@shoelace-style/shoelace/dist/components/tree-item/tree-item.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio-button/radio-button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
let ProjectFilterModal = class ProjectFilterModal extends LitElement {
    constructor() {
        super(...arguments);
        this.isOpen = false;
        this.organizations = [];
        this.projects = [];
        this.selectedProjectIds = [];
        this.showProjects = true;
        this.showResolution = true;
        this.selectedStatus = 'opened';
        this.selectedResolution = 'all';
        this.draftSelectedProjectIds = [];
        this.draftSelectedStatus = 'opened';
        this.draftSelectedResolution = 'all';
    }
    willUpdate(changedProperties) {
        // When the dialog is opened, reset the draft state from the properties
        if (changedProperties.has('isOpen') && this.isOpen) {
            this.draftSelectedProjectIds = [...this.selectedProjectIds];
            this.draftSelectedStatus = this.selectedStatus;
            this.draftSelectedResolution = this.selectedResolution;
        }
    }
    handleSelect(event) {
        const selectedItems = event.detail.selection;
        const projectIds = selectedItems
            .map((item) => item.dataset.projectId)
            .filter((id) => id); // Filter out undefined from parent items
        this.draftSelectedProjectIds = [...new Set(projectIds)];
    }
    handleStatusChange(event) {
        const radioGroup = event.target;
        this.draftSelectedStatus = radioGroup.value;
    }
    handleResolutionChange(event) {
        const radioGroup = event.target;
        this.draftSelectedResolution = radioGroup.value;
    }
    handleApply() {
        this.dispatchEvent(new CustomEvent('on-apply', {
            bubbles: true,
            composed: true,
            detail: {
                projectIds: this.draftSelectedProjectIds,
                status: this.draftSelectedStatus,
                resolution: this.draftSelectedResolution,
            },
        }));
    }
    handleClose() {
        this.dispatchEvent(new CustomEvent('on-close', { bubbles: true, composed: true }));
    }
    render() {
        const projectsByOrg = this.projects.reduce((acc, p) => {
            // Assuming project has an organization_id. This is based on typical data structures.
            const orgId = p.organization_id;
            if (!acc.has(orgId)) {
                acc.set(orgId, []);
            }
            acc.get(orgId).push(p);
            return acc;
        }, new Map());
        return html `
      <sl-dialog
        label="Filters"
        .open=${this.isOpen}
        @sl-hide=${this.handleClose}
      >
        ${when(this.showProjects, () => html `
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
            const selectedProjectsInOrg = projectsInOrg.filter((p) => this.draftSelectedProjectIds.includes(p.id.toString()));
            const allSelected = projectsInOrg.length > 0 &&
                selectedProjectsInOrg.length === projectsInOrg.length;
            const someSelected = selectedProjectsInOrg.length > 0 &&
                selectedProjectsInOrg.length < projectsInOrg.length;
            return html `
                    <sl-tree-item
                      ?selected=${allSelected}
                      ?indeterminate=${someSelected}
                    >
                      ${org.name}
                      ${projectsInOrg.map((proj) => html `<sl-tree-item
                            data-project-id="${proj.id}"
                            ?selected=${this.draftSelectedProjectIds.includes(proj.id.toString())}
                            >${proj.name}</sl-tree-item
                          >`)}
                    </sl-tree-item>
                  `;
        })}
              </sl-tree>
            </div>
            <sl-divider></sl-divider>
          `)}

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

        ${when(this.showResolution, () => html `
            <sl-divider></sl-divider>
            <div class="filter-section">
              <label class="filter-label">Resolution Status</label>
              <sl-radio-group
                value=${this.draftSelectedResolution}
                @sl-change=${this.handleResolutionChange}
              >
                <sl-radio-button value="all">All</sl-radio-button>
                <sl-radio-button value="resolved">Resolved</sl-radio-button>
                <sl-radio-button value="unresolved">Unresolved</sl-radio-button>
              </sl-radio-group>
            </div>
          `)}

        <sl-button slot="footer" @click=${this.handleClose}>Cancel</sl-button>
        <sl-button slot="footer" variant="primary" @click=${this.handleApply}
          >Apply</sl-button
        >
      </sl-dialog>
    `;
    }
};
ProjectFilterModal.styles = css `
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
__decorate([
    property({ type: Boolean })
], ProjectFilterModal.prototype, "isOpen", void 0);
__decorate([
    property({ type: Array })
], ProjectFilterModal.prototype, "organizations", void 0);
__decorate([
    property({ type: Array })
], ProjectFilterModal.prototype, "projects", void 0);
__decorate([
    property({ type: Array })
], ProjectFilterModal.prototype, "selectedProjectIds", void 0);
__decorate([
    property({ type: Boolean })
], ProjectFilterModal.prototype, "showProjects", void 0);
__decorate([
    property({ type: Boolean })
], ProjectFilterModal.prototype, "showResolution", void 0);
__decorate([
    property({ type: String })
], ProjectFilterModal.prototype, "selectedStatus", void 0);
__decorate([
    property({ type: String })
], ProjectFilterModal.prototype, "selectedResolution", void 0);
__decorate([
    state()
], ProjectFilterModal.prototype, "draftSelectedProjectIds", void 0);
__decorate([
    state()
], ProjectFilterModal.prototype, "draftSelectedStatus", void 0);
__decorate([
    state()
], ProjectFilterModal.prototype, "draftSelectedResolution", void 0);
ProjectFilterModal = __decorate([
    customElement('project-filter-modal')
], ProjectFilterModal);
export { ProjectFilterModal };
