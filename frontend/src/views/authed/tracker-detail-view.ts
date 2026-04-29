import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '../../components/view-header.ts';
import {
  fetchWithAuth,
  getFeatures,
  deleteTracker,
  type FeaturesResponse,
} from '../../api';
import type { Project } from '../../types';
import consoleStyles from '../../styles/console-styles.css?inline';

interface TrackerDetail {
  id: string;
  name: string;
  tracker_type: string;
  created: string;
  last_updated: string;
  is_valid: boolean;
  validation_message?: string;
  url?: string;
  scope_rules?: Array<{
    scope_type: string;
    rule_type: string;
    identifier: string;
  }>;
}

@customElement('tracker-detail-view')
export class TrackerDetailView extends LitElement {
  @state()
  private _tracker: TrackerDetail | null = null;

  @state()
  private _projects: Project[] = [];

  @state()
  private _loading = true;

  @state()
  private _error: string | null = null;

  @state()
  private _editingTracker: TrackerDetail | null = null;

  @state()
  private _features: FeaturesResponse['features'] = {};

  @state()
  private _featuresLoaded = false;

  private _trackerId = '';

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .tracker-header {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-medium);
        margin-bottom: var(--sl-spacing-small);
      }

      .tracker-icon {
        font-size: 2.5rem;
        color: var(--sl-color-primary-600);
      }

      .tracker-title {
        margin: 0;
        font-size: var(--sl-font-size-2x-large);
      }

      .tracker-meta {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-medium);
        margin-bottom: var(--sl-spacing-large);
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .tracker-meta span {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
      }

      .section-title {
        font-size: var(--sl-font-size-large);
        font-weight: var(--sl-font-weight-semibold);
        margin: var(--sl-spacing-large) 0 var(--sl-spacing-medium) 0;
      }

      .analytics-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: var(--sl-spacing-medium);
      }

      .analytics-card {
        cursor: pointer;
        transition: box-shadow 0.2s ease;
      }

      .analytics-card:hover {
        box-shadow: var(--sl-shadow-medium);
      }

      .analytics-card .card-header {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        margin-bottom: var(--sl-spacing-small);
      }

      .analytics-card .card-header sl-icon {
        font-size: 1.25rem;
        color: var(--sl-color-primary-600);
      }

      .analytics-card .card-header h3 {
        margin: 0;
        font-size: var(--sl-font-size-medium);
      }

      .analytics-card p {
        margin: 0;
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .projects-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
      }

      .project-row {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
        font-size: var(--sl-font-size-small);
      }

      .project-name {
        font-weight: var(--sl-font-weight-semibold);
      }

      .project-key {
        color: var(--sl-color-neutral-500);
      }

      .scope-rules {
        display: flex;
        flex-wrap: wrap;
        gap: var(--sl-spacing-x-small);
      }

      .back-link {
        display: inline-flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
        margin-bottom: var(--sl-spacing-medium);
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
        text-decoration: none;
      }

      .back-link:hover {
        color: var(--sl-color-primary-600);
        text-decoration: none;
      }

      .no-analytics {
        padding: var(--sl-spacing-large);
        text-align: center;
        color: var(--sl-color-neutral-500);
        background: var(--sl-color-neutral-50);
        border-radius: var(--sl-border-radius-medium);
      }

      .no-projects {
        padding: var(--sl-spacing-medium);
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-small);
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();
    this._trackerId = (this as any).location?.params?.trackerId || '';
    this._loadData();
  }

  private async _loadData() {
    this._loading = true;
    this._error = null;

    try {
      const [trackerRes, projectsRes, featuresRes] = await Promise.all([
        fetchWithAuth(`/api/v1/trackers/${this._trackerId}`),
        fetchWithAuth('/api/v1/projects'),
        getFeatures(),
      ]);

      if (!trackerRes.ok) {
        throw new Error('Tracker not found');
      }

      this._tracker = await trackerRes.json();
      this._features = featuresRes.features;
      this._featuresLoaded = true;

      if (projectsRes.ok) {
        const allProjects: Project[] = await projectsRes.json();
        this._projects = allProjects.filter(
          (p) => p.tracker_id === this._trackerId
        );
      }
    } catch (error) {
      this._error =
        error instanceof Error ? error.message : 'Failed to load tracker';
    } finally {
      this._loading = false;
    }
  }

  private _hasAnyAnalyticsFeature(): boolean {
    return !!(
      this._features.issue_compliance ||
      this._features.issue_duplicates ||
      this._features.issue_dependencies
    );
  }

  private _getTrackerIcon(): string {
    const type = this._tracker?.tracker_type?.toLowerCase() || '';
    if (type.includes('jira')) return 'git';
    if (type.includes('github')) return 'github';
    if (type.includes('gitlab')) return 'gitlab';
    return 'box-seam';
  }

  private _getProjectIds(): string {
    return this._projects.map((p) => p.id.split('-')[0]).join(',');
  }

  private handleEdit() {
    if (this._tracker) {
      this._editingTracker = this._tracker;
    }
  }

  private async handleDelete() {
    if (!this._tracker) return;
    if (
      !confirm(
        `Are you sure you want to delete the tracker "${this._tracker.name}"?`
      )
    ) {
      return;
    }

    this._loading = true;
    try {
      await deleteTracker(this._trackerId);
      Router.go('/console/trackers');
    } catch (error) {
      this._error =
        error instanceof Error ? error.message : 'Failed to delete tracker';
      this._loading = false;
    }
  }

  private handleSync() {
    console.log('Sync tracker functionality not yet implemented in backend.');
  }

  private _handleTrackerUpdated() {
    this._editingTracker = null;
    this._loadData();
  }

  private _closeAddTrackerForm() {
    this._editingTracker = null;
  }

  private _buildIssuesUrl(subpath: string): string {
    const projectIds = this._getProjectIds();
    const base = `/console/issues${subpath}`;
    return projectIds ? `${base}?projects=${projectIds}` : base;
  }

  render() {
    if (this._loading) {
      return html`
        <div
          style="display: flex; justify-content: center; padding: var(--sl-spacing-2x-large);"
        >
          <sl-spinner style="font-size: 2rem;"></sl-spinner>
        </div>
      `;
    }

    if (this._error || !this._tracker) {
      return html`
        <view-header headerText="Tracker Details" width="narrow">
          <div slot="top" style="margin-bottom: var(--sl-spacing-small);">
            <sl-button
              variant="text"
              size="small"
              href="/console/trackers"
              style="margin-left: -12px;"
            >
              <sl-icon slot="prefix" name="arrow-left"></sl-icon> Back to
              Trackers
            </sl-button>
          </div>
        </view-header>
        <div class="column-layout narrow" style="padding-top: 0;">
          <div class="main-column">
            <sl-alert variant="danger" open>
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              ${this._error || 'Tracker not found'}
            </sl-alert>
          </div>
        </div>
      `;
    }

    const tracker = this._tracker;
    const createdDate = new Date(tracker.created).toLocaleDateString();
    const updatedDate = new Date(tracker.last_updated).toLocaleDateString();
    const icon = this._getTrackerIcon();
    const hasAnalytics = this._hasAnyAnalyticsFeature();
    const hasProjects = this._projects.length > 0;

    return html`
      ${this._editingTracker
        ? html`<add-tracker-modal
            .tracker=${this._editingTracker}
            @tracker-updated=${this._handleTrackerUpdated}
            @close-modal=${this._closeAddTrackerForm}
          ></add-tracker-modal>`
        : ''}
      <view-header headerText=${tracker.name} width="narrow">
        <div slot="top" style="margin-bottom: var(--sl-spacing-small);">
          <sl-button
            variant="text"
            size="small"
            href="/console/trackers"
            style="margin-left: -12px;"
          >
            <sl-icon slot="prefix" name="arrow-left"></sl-icon> Back to Trackers
          </sl-button>
        </div>
        <div slot="main-column" class="header-actions">
          <resource-actions
            .actions=${[
              {
                id: 'edit',
                label: 'Edit',
                icon: 'pencil',
                onClick: () => this.handleEdit(),
              },
              {
                id: 'sync',
                label: 'Sync Now',
                icon: 'arrow-repeat',
                onClick: () => this.handleSync(),
              },
              {
                id: 'delete',
                label: 'Delete',
                icon: 'trash',
                variant: 'danger',
                onClick: () => this.handleDelete(),
              },
            ]}
          ></resource-actions>
        </div>
      </view-header>
      <div class="column-layout narrow" style="padding-top: 0;">
        <div class="main-column">
          <div class="tracker-header">
            <sl-icon class="tracker-icon" name=${icon}></sl-icon>
            <sl-badge variant=${tracker.is_valid ? 'success' : 'warning'} pill>
              ${tracker.is_valid ? 'Connected' : 'Not validated'}
            </sl-badge>
          </div>

          <div class="tracker-meta">
            <span>
              <sl-icon name="tag"></sl-icon>
              ${tracker.tracker_type}
            </span>
            <span>
              <sl-icon name="calendar3"></sl-icon>
              Created ${createdDate}
            </span>
            <span>
              <sl-icon name="clock-history"></sl-icon>
              Updated ${updatedDate}
            </span>
            ${tracker.url
              ? html`<span>
                  <sl-icon name="link-45deg"></sl-icon>
                  ${tracker.url}
                </span>`
              : ''}
          </div>

          ${tracker.scope_rules && tracker.scope_rules.length > 0
            ? html`
                <div class="scope-rules">
                  ${tracker.scope_rules.map(
                    (rule) => html`
                      <sl-badge variant="neutral" pill>
                        ${rule.rule_type === 'INCLUDE' ? '+' : '-'}
                        ${rule.scope_type}: ${rule.identifier}
                      </sl-badge>
                    `
                  )}
                </div>
              `
            : ''}

          <sl-divider></sl-divider>

          <h2 class="section-title">Issue Analytics</h2>

          ${hasAnalytics && hasProjects
            ? html`
                <div class="analytics-grid">
                  ${this._features.issue_duplicates
                    ? html`
                        <a
                          href=${this._buildIssuesUrl('')}
                          style="text-decoration: none; color: inherit;"
                        >
                          <sl-card class="analytics-card">
                            <div class="card-header">
                              <sl-icon name="intersect"></sl-icon>
                              <h3>Similarity</h3>
                            </div>
                            <p>
                              Find duplicate and overlapping issues using vector
                              similarity search.
                            </p>
                          </sl-card>
                        </a>
                      `
                    : ''}
                  ${this._features.issue_compliance
                    ? html`
                        <a
                          href=${this._buildIssuesUrl('/compliance')}
                          style="text-decoration: none; color: inherit;"
                        >
                          <sl-card class="analytics-card">
                            <div class="card-header">
                              <sl-icon name="clipboard-check"></sl-icon>
                              <h3>Compliance</h3>
                            </div>
                            <p>
                              Evaluate issue quality against compliance metrics
                              and get improvement suggestions.
                            </p>
                          </sl-card>
                        </a>
                      `
                    : ''}
                  ${this._features.issue_dependencies
                    ? html`
                        <a
                          href=${this._buildIssuesUrl('/dependencies')}
                          style="text-decoration: none; color: inherit;"
                        >
                          <sl-card class="analytics-card">
                            <div class="card-header">
                              <sl-icon name="diagram-3"></sl-icon>
                              <h3>Dependencies</h3>
                            </div>
                            <p>
                              Detect unmapped dependencies between issues and
                              visualize relationships.
                            </p>
                          </sl-card>
                        </a>
                      `
                    : ''}
                </div>
              `
            : html`
                <div class="no-analytics">
                  ${!hasProjects
                    ? 'No projects synced yet. Issues will appear after the first sync completes.'
                    : 'Issue analytics features are not enabled for this instance.'}
                </div>
              `}

          <sl-divider></sl-divider>

          <h2 class="section-title">
            Projects
            ${hasProjects
              ? html`<sl-badge variant="neutral" pill
                  >${this._projects.length}</sl-badge
                >`
              : ''}
          </h2>

          ${hasProjects
            ? html`
                <div class="projects-list">
                  ${this._projects.map(
                    (project) => html`
                      <div class="project-row">
                        <sl-icon
                          name="folder"
                          style="color: var(--sl-color-primary-500);"
                        ></sl-icon>
                        <span class="project-name">${project.name}</span>
                        ${project.key
                          ? html`<span class="project-key"
                              >(${project.key})</span
                            >`
                          : ''}
                      </div>
                    `
                  )}
                </div>
              `
            : html`<div class="no-projects">
                No projects synced yet. Projects will appear after the tracker
                completes its first sync.
              </div>`}
        </div>
      </div>
    `;
  }
}
