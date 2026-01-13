import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import '../../components/tracker-list.ts';
import '../../components/add-tracker-modal.ts';
import type { Tracker } from '../../components/tracker-item.ts';
import type { TrackerList } from '../../components/tracker-list.ts';
import consoleStyles from '../../styles/console-styles.css?inline';

@customElement('trackers-view')
export class TrackersView extends LitElement {
  @state()
  private isAddingTracker = false;

  @state()
  private editingTracker: Tracker | null = null;

  @state()
  private githubInstallationId: string | null = null;

  @state()
  private githubTargetLogin: string | null = null;

  @state()
  private githubError: string | null = null;

  @query('tracker-list')
  private trackerListElement: TrackerList | undefined;

  static styles = [unsafeCSS(consoleStyles)];

  connectedCallback() {
    super.connectedCallback();
    this._handleGitHubCallback();
  }

  private _handleGitHubCallback() {
    const params = new URLSearchParams(window.location.search);

    // Handle GitHub OAuth callback
    const installationId = params.get('github_installation_id');
    const targetLogin = params.get('target_login');
    const error = params.get('github_error');
    const errorDescription = params.get('error_description');

    if (error) {
      this.githubError = errorDescription || error;
      // Clear URL params
      window.history.replaceState({}, '', window.location.pathname);
      return;
    }

    if (installationId) {
      this.githubInstallationId = installationId;
      this.githubTargetLogin = targetLogin;
      // Auto-open the add tracker modal
      this.isAddingTracker = true;
      // Clear URL params
      window.history.replaceState({}, '', window.location.pathname);
    }
  }

  private _openAddTrackerForm() {
    this.isAddingTracker = true;
    this.editingTracker = null;
  }

  private _closeAddTrackerForm() {
    this.isAddingTracker = false;
    this.editingTracker = null;
  }

  private async _handleTrackerAdded(event: CustomEvent) {
    // Don't close modal if there are warnings to display
    if (!event.detail?.hasWarnings) {
      this.isAddingTracker = false;
    }
    await this.trackerListElement?.fetchTrackers();
  }

  private async _handleTrackerUpdated(event: CustomEvent) {
    // Don't close modal if there are warnings to display
    if (!event.detail?.hasWarnings) {
      this.editingTracker = null;
    }
    await this.trackerListElement?.fetchTrackers();
  }

  private _handleTrackerEdit(event: CustomEvent) {
    this.editingTracker = event.detail.tracker;
    this.isAddingTracker = false;
  }

  private _dismissGitHubError() {
    this.githubError = null;
  }

  render() {
    return html`
      <view-header headerText="Trackers" width="narrow">
        <div slot="main-column">
          <sl-button variant="primary" @click=${this._openAddTrackerForm}>
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add New Tracker
          </sl-button>
        </div>
      </view-header>
      <div class="column-layout narrow">
        <div class="main-column">
          ${this.githubError
            ? html`
                <sl-alert
                  variant="danger"
                  open
                  closable
                  @sl-after-hide=${this._dismissGitHubError}
                >
                  <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                  <strong>GitHub Connection Failed</strong><br />
                  ${this.githubError}
                </sl-alert>
              `
            : ''}
          ${this.isAddingTracker
            ? html`<add-tracker-modal
                .githubInstallationId=${this.githubInstallationId}
                .githubTargetLogin=${this.githubTargetLogin}
                @tracker-added=${this._handleTrackerAdded}
                @close-modal=${this._closeAddTrackerForm}
              ></add-tracker-modal>`
            : ''}
          ${this.editingTracker
            ? html`<add-tracker-modal
                .tracker=${this.editingTracker}
                @tracker-updated=${this._handleTrackerUpdated}
                @close-modal=${this._closeAddTrackerForm}
              ></add-tracker-modal>`
            : ''}
          <tracker-list @tracker-edit=${this._handleTrackerEdit}></tracker-list>
        </div>
      </div>
    `;
  }
}
