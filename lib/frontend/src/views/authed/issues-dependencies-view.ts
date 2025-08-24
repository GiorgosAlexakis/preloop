import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { when } from 'lit/directives/when.js';

import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/button-group/button-group.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';

import '../../components/single-issue-detail-view.ts';
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

  @state()
  private _expandedRowKey: string | null = null;

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
      .blocks-badge::part(base) {
        background-color: #d9d9e9;
        color: var(--sl-color-neutral-800);
        border: none;
      }
      .blocked-by-badge::part(base) {
        background-color: #e3e3e0;
        color: var(--sl-color-neutral-800);
        border: none;
      }
      .dependency-badge-content {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-3x-small);
      }
      .clickable-row {
        cursor: pointer;
      }
      .row-expanded {
        background-color: var(--sl-color-primary-50);
      }
      .side-column {
        display: none;
      }

      .placeholder-content {
        text-align: center;
      }

      .dependency-details {
        font-size: var(--sl-font-size-small);
      }
      .dependency-details h5 {
        margin-top: var(--sl-spacing-medium);
        margin-bottom: var(--sl-spacing-x-small);
      }
      .dependency-details ul {
        list-style-type: none;
        padding-left: var(--sl-spacing-medium);
        margin: 0;
      }
      .dependency-details li {
        padding: var(--sl-spacing-2x-small) 0;
        border-bottom: 1px solid var(--sl-color-neutral-200);
      }
      .dependency-details li:last-child {
        border-bottom: none;
      }
      .dependency-reason {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-500);
      }

      @media (min-width: 1720px) {
        .side-column {
          display: flex;
        }
        .inline-detail-row {
          display: none;
        }
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

  private async _expandScanForRow(issueId: string) {
    this._loadingDependencies = true;
    this._error = null;
    try {
      // We only need to fetch dependencies for the new issue
      const newDependencies = await detectIssueDependencies([issueId]);

      // Merge new dependencies with existing ones
      const newDependencyPairs = [...this._dependencies];
      const existingPairs = new Set(
        newDependencyPairs.map(
          (p) => `${p.source_issue_id}-${p.target_issue_id}`
        )
      );

      for (const dep of newDependencies) {
        const pairKey = `${dep.source_issue_id}-${dep.target_issue_id}`;
        if (!existingPairs.has(pairKey)) {
          newDependencyPairs.push(dep);
          existingPairs.add(pairKey);
        }
      }

      this._dependencies = newDependencyPairs;
      this._processDependencies(); // This will rebuild the map and trigger a re-render
    } catch (error) {
      this._error = 'Failed to expand scan for issue.';
      console.error(error);
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

  private _toggleRow(issueId: string) {
    if (this._expandedRowKey === issueId) {
      this._expandedRowKey = null;
    } else {
      this._expandedRowKey = issueId;
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

  private _renderDependencyDetails(
    deps: { blocks: DependencyPair[]; blockedBy: DependencyPair[] } | undefined
  ) {
    if (!deps || (deps.blocks.length === 0 && deps.blockedBy.length === 0)) {
      return html`
        <div class="detail-section">
          <h4>Dependencies</h4>
          <sl-alert variant="primary" open>
            <sl-icon slot="icon" name="info-circle"></sl-icon>
            No dependencies detected for this issue.
          </sl-alert>
        </div>
      `;
    }

    const renderList = (
      items: DependencyPair[],
      type: 'blocks' | 'blockedBy'
    ) => {
      return html`
        <ul>
          ${items.map((d) => {
            const issueId =
              type === 'blocks' ? d.dependent_issue_id : d.source_issue_id;
            const issue = this._issues.find((i) => i.id === issueId);

            return html`
              <li>
                <strong
                  >${type === 'blocks' ? d.dependency_key : d.issue_key}</strong
                >: ${issue?.title || 'Unknown Issue'}
                <div class="dependency-reason">
                  ${d.reason} &bull; Confidence:
                  ${(d.confidence_score * 100).toFixed(0)}%
                </div>
              </li>
            `;
          })}
        </ul>
      `;
    };

    return html`
      <div class="detail-section dependency-details">
        <h4>Dependencies</h4>
        ${when(
          deps.blocks.length > 0,
          () => html`
            <h5>Blocks</h5>
            ${renderList(deps.blocks, 'blocks')}
          `
        )}
        ${when(
          deps.blockedBy.length > 0,
          () => html`
            <h5>Blocked By</h5>
            ${renderList(deps.blockedBy, 'blockedBy')}
          `
        )}
      </div>
    `;
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
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            ${this._issues.map((issue) => {
              const deps = this._dependencyMap.get(issue.id);
              const isExpanded = this._expandedRowKey === issue.id;
              return html`
                <tr
                  class="clickable-row ${isExpanded ? 'row-expanded' : ''}"
                  @click=${() => this._toggleRow(issue.id)}
                >
                  <td>
                    <a
                      href="${issue.url}"
                      target="_blank"
                      @click=${(e: Event) => e.stopPropagation()}
                      >${issue.key}</a
                    >
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
                          ${when(
                            deps && deps.blocks.length > 0,
                            () => html`
                              <sl-badge pill class="blocks-badge">
                                <div class="dependency-badge-content">
                                  <sl-tooltip content="Blocks">
                                    <sl-icon name="arrow-right-circle"></sl-icon
                                    >Blocks:
                                  </sl-tooltip>
                                  <span
                                    >${deps?.blocks.map(
                                      (d, i) => html`
                                        <sl-tooltip
                                          content="Reason: ${d.reason} | Confidence: ${(
                                            d.confidence_score * 100
                                          ).toFixed(0)}%"
                                        >
                                          <span
                                            >#${d.dependency_key.match(
                                              /\d+$/
                                            )?.[0]}</span
                                          > </sl-tooltip
                                        >${i < deps.blocks.length - 1
                                          ? ', '
                                          : ''}
                                      `
                                    )}</span
                                  >
                                </div>
                              </sl-badge>
                            `
                          )}
                          ${when(
                            deps && deps.blockedBy.length > 0,
                            () => html`
                              <sl-badge pill class="blocked-by-badge">
                                <div class="dependency-badge-content">
                                  <sl-tooltip content="Blocked by">
                                    <sl-icon name="arrow-left-circle"></sl-icon
                                    >Blocked by:
                                  </sl-tooltip>
                                  <span
                                    >${deps?.blockedBy.map(
                                      (d, i) => html`
                                        <sl-tooltip
                                          content="Reason: ${d.reason} | Confidence: ${(
                                            d.confidence_score * 100
                                          ).toFixed(0)}%"
                                        >
                                          <span
                                            >#${d.issue_key.match(
                                              /\d+$/
                                            )?.[0]}</span
                                          > </sl-tooltip
                                        >${i < deps.blockedBy.length - 1
                                          ? ', '
                                          : ''}
                                      `
                                    )}</span
                                  >
                                </div>
                              </sl-badge>
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
                  <td>
                    <sl-button
                      size="small"
                      @click=${() => this._expandScanForRow(issue.id)}
                      .loading=${this._loadingDependencies}
                      >Expand Scan</sl-button
                    >
                  </td>
                </tr>
                ${isExpanded
                  ? html`
                      <tr class="inline-detail-row">
                        <td colspan="4">
                          <div class="detail-view-card">
                            <single-issue-detail-view .issue=${issue}>
                              <div slot="additional-info">
                                ${this._renderDependencyDetails(deps)}
                              </div>
                            </single-issue-detail-view>
                          </div>
                        </td>
                      </tr>
                    `
                  : ''}
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
        <div class="side-column">
          <sl-card class="detail-view-card">
            <div slot="header">Issue Details</div>
            ${when(
              this._expandedRowKey,
              () => {
                const issue = this._issues.find(
                  (i) => i.id === this._expandedRowKey
                );
                if (issue) {
                  return html`<single-issue-detail-view .issue=${issue}>
                    <div slot="additional-info">
                      ${this._renderDependencyDetails(
                        this._dependencyMap.get(issue.id)
                      )}
                    </div>
                  </single-issue-detail-view>`;
                } else {
                  return html`<div class="placeholder-content">
                    <sl-icon name="info-circle"></sl-icon>
                    <p>Select an issue to see details.</p>
                  </div>`;
                }
              },
              () =>
                html`<div class="placeholder-content">
                  <sl-icon name="info-circle"></sl-icon>
                  <p>Select an issue to see details.</p>
                </div>`
            )}
          </sl-card>
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
