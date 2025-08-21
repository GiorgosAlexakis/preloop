import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';

import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';

import { listProjects, searchIssues, detectIssueDependencies } from '../../api';
import type { Project, Issue, DependencyPair } from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';
import '../../components/pagination-controls.ts';
import { getStatusVariant } from '../../utils/verdict';

@customElement('issues-dependencies-view')
export class IssuesDependenciesView extends LitElement {
  @state()
  private _allProjects: Project[] = [];

  @state()
  private _selectedProjectId: string | null = null;

  @state()
  private _issues: Issue[] = [];

  @state()
  private _dependencies: DependencyPair[] = [];

  @state()
  private _dependencyMap: Map<
    string,
    { blocks: DependencyPair[]; blockedBy: DependencyPair[] }
  > = new Map();

  @state()
  private _loadingIssues = false;

  @state()
  private _loadingDependencies = false;

  @state()
  private _error: string | null = null;

  @state()
  private _currentPage = 1;

  @state()
  private _hasMorePages = false;

  private _pageSize = 10;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .container {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-medium);
      }
      .table-card {
        width: 100%;
        margin-bottom: var(--sl-spacing-medium);
      }
      .table-card {
        --padding: 0;
        border-spacing: 0;
      }
      .controls {
        display: flex;
        gap: var(--sl-spacing-medium);
        align-items: center;
      }
      sl-select {
        min-width: 250px;
      }
      .empty-state {
        text-align: center;
        padding: var(--sl-spacing-xx-large);
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-radius-medium);
      }
      .dependency-tags {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-2x-small);
        padding-top: var(--sl-spacing-3x-small);
      }
      .dependency-tags sl-badge::part(base) {
        cursor: pointer;
      }
    `,
  ];

  async connectedCallback() {
    super.connectedCallback();
  }

  async firstUpdated() {
    await this._fetchProjects();
    if (this._allProjects.length > 0) {
      this._selectedProjectId = this._allProjects[0].id;
      this.fetchIssues();
    }
  }

  private async _fetchProjects() {
    try {
      this._allProjects = await listProjects();
    } catch (error) {
      this._error = 'Failed to load projects.';
      console.error(error);
    }
  }

  async fetchIssues() {
    if (!this._selectedProjectId) return;

    this._loadingIssues = true;
    this._error = null;
    this._dependencies = []; // Clear old dependencies
    this._dependencyMap.clear();

    try {
      const skip = (this._currentPage - 1) * this._pageSize;
      const issues = await searchIssues({
        project_ids: [this._selectedProjectId],
        limit: this._pageSize,
        skip: skip,
      });
      this._issues = issues;
      this._hasMorePages = issues.length === this._pageSize;

      if (issues.length > 0) {
        this.fetchDependencies(issues.map((i) => i.id));
      }
    } catch (error) {
      this._error = 'Failed to load issues.';
      console.error(error);
    } finally {
      this._loadingIssues = false;
    }
  }

  async fetchDependencies(issueIds: string[]) {
    this._loadingDependencies = true;
    try {
      const result = await detectIssueDependencies(issueIds);
      this._dependencies = result.dependencies;
      this._processDependencies();
    } catch (error) {
      console.error('Failed to detect dependencies', error);
      // Silently fail for now, or show a non-blocking error
    } finally {
      this._loadingDependencies = false;
    }
  }

  private _handleProjectSelect(e: CustomEvent) {
    this._selectedProjectId = e.target.value;
    this._currentPage = 1;
    this._issues = [];
    this._dependencies = [];
    this._dependencyMap.clear();
    this.fetchIssues();
  }

  private _goToNextPage() {
    if (this._hasMorePages) {
      this._currentPage++;
      this.fetchIssues();
    }
  }

  private _goToPreviousPage() {
    if (this._currentPage > 1) {
      this._currentPage--;
      this.fetchIssues();
    }
  }

  private _processDependencies() {
    const newMap = new Map<
      string,
      { blocks: DependencyPair[]; blockedBy: DependencyPair[] }
    >();
    this._issues.forEach((issue) => {
      newMap.set(issue.id, { blocks: [], blockedBy: [] });
    });

    this._dependencies.forEach((dep) => {
      // Add to the 'blocks' list of the source issue
      if (newMap.has(dep.source_issue_id)) {
        newMap.get(dep.source_issue_id)!.blocks.push(dep);
      }
      // Add to the 'blockedBy' list of the dependent issue
      if (newMap.has(dep.dependent_issue_id)) {
        newMap.get(dep.dependent_issue_id)!.blockedBy.push(dep);
      }
    });

    this._dependencyMap = newMap;
  }

  private _renderIssueTable() {
    if (this._loadingIssues && this._issues.length === 0) {
      return html`<div class="loading-container"></div>`;
    }

    if (this._error) {
      return html`<div class="error">${this._error}</div>`;
    }

    if (this._issues.length === 0) {
      return html`
        <div class="empty-state">
          <sl-icon
            name="info-circle"
            style="font-size: 3rem; margin-bottom: 1rem;"
          ></sl-icon>
          <h2>No Issues Found</h2>
          <p>
            No issues were found for the selected project, or the project is
            empty.
          </p>
        </div>
      `;
    }

    return html`
      <sl-card class="table-card">
        <table class="styled-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Title</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${this._issues.map((issue) => {
              const deps = this._dependencyMap.get(issue.id);
              return html`
                <tr>
                  <td>
                    <a href="${issue.url}" target="_blank">${issue.key}</a>
                  </td>
                  <td>
                    ${issue.title}
                    <div class="dependency-tags">
                      ${when(
                        this._loadingDependencies,
                        () =>
                          html`<sl-spinner
                            style="font-size: 1em; vertical-align: middle;"
                          ></sl-spinner>`,
                        () => html`
                          ${deps?.blocks.map(
                            (d) => html`
                              <sl-tooltip content="Reason: ${d.reason}">
                                <sl-badge variant="danger" pill
                                  >Blocks: ${d.dependency_key}</sl-badge
                                >
                              </sl-tooltip>
                            `
                          )}
                          ${deps?.blockedBy.map(
                            (d) => html`
                              <sl-tooltip content="Reason: ${d.reason}">
                                <sl-badge variant="warning" pill
                                  >Blocked by: ${d.issue_key}</sl-badge
                                >
                              </sl-tooltip>
                            `
                          )}
                        `
                      )}
                    </div>
                  </td>
                  <td>
                    <sl-badge variant=${getStatusVariant(issue.status)}
                      >${issue.status}</sl-badge
                    >
                  </td>
                </tr>
              `;
            })}
          </tbody>
        </table>
      </sl-card>
      <pagination-controls
        .currentPage=${this._currentPage}
        .hasMorePages=${this._hasMorePages}
        .loading=${this._loadingIssues}
        @prev-page=${this._goToPreviousPage}
        @next-page=${this._goToNextPage}
      ></pagination-controls>
    `;
  }

  render() {
    return html`
      <view-header headerText="Issue Dependencies">
        <div slot="main-column">
          <sl-select
            placeholder="Select a project..."
            .value=${this._selectedProjectId}
            @sl-change=${this._handleProjectSelect}
            .disabled=${this._allProjects.length === 0}
          >
            ${this._allProjects.map(
              (proj) =>
                html`<sl-option value=${proj.id}>${proj.name}</sl-option>`
            )}
          </sl-select>
        </div>
      </view-header>

      <div class="column-layout">
        <div class="main-column">
          <div class="container">
            ${when(
              this._selectedProjectId,
              () => this._renderIssueTable(),
              () => html`
                <div class="empty-state">
                  <sl-icon
                    name="diagram-3"
                    style="font-size: 3rem; margin-bottom: 1rem;"
                  ></sl-icon>
                  <h2>Select a Project</h2>
                  <p>
                    Please select a project from the dropdown above to view its
                    issues and detect dependencies.
                  </p>
                </div>
              `
            )}
          </div>
        </div>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'issues-dependencies-view': IssuesDependenciesView;
  }
}
