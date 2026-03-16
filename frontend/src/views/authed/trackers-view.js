var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, unsafeCSS } from 'lit';
import { customElement, state, query } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import '../../components/tracker-list.ts';
import '../../components/add-tracker-modal.ts';
import consoleStyles from '../../styles/console-styles.css?inline';
let TrackersView = class TrackersView extends LitElement {
    constructor() {
        super(...arguments);
        this.isAddingTracker = false;
        this.editingTracker = null;
        this.githubInstallationId = null;
        this.githubTargetLogin = null;
        this.githubError = null;
    }
    connectedCallback() {
        super.connectedCallback();
        this._handleUrlAction();
        this._handleGitHubCallback();
    }
    _handleUrlAction() {
        const params = new URLSearchParams(window.location.search);
        if (params.get('action') === 'add') {
            this.isAddingTracker = true;
            // Clean up the URL subtly
            const newUrl = new URL(window.location.href);
            newUrl.searchParams.delete('action');
            window.history.replaceState({}, '', newUrl.toString());
        }
    }
    _handleGitHubCallback() {
        const params = new URLSearchParams(window.location.search);
        // Handle GitHub OAuth callback
        const installationId = params.get('github_installation_id');
        const targetLogin = params.get('target_login');
        const returnedState = params.get('state');
        const error = params.get('github_error');
        const errorDescription = params.get('error_description');
        if (error) {
            this.githubError = errorDescription || error;
            // Clear stored state and URL params
            sessionStorage.removeItem('github_oauth_state');
            window.history.replaceState({}, '', window.location.pathname);
            return;
        }
        if (installationId) {
            // Validate CSRF state token
            const storedState = sessionStorage.getItem('github_oauth_state');
            sessionStorage.removeItem('github_oauth_state');
            if (!storedState || storedState !== returnedState) {
                this.githubError =
                    'OAuth state mismatch. This may be a CSRF attack or the session expired. Please try again.';
                window.history.replaceState({}, '', window.location.pathname);
                return;
            }
            this.githubInstallationId = installationId;
            this.githubTargetLogin = targetLogin;
            // Auto-open the add tracker modal
            this.isAddingTracker = true;
            // Clear URL params
            window.history.replaceState({}, '', window.location.pathname);
        }
    }
    _openAddTrackerForm() {
        this.isAddingTracker = true;
        this.editingTracker = null;
    }
    _closeAddTrackerForm() {
        this.isAddingTracker = false;
        this.editingTracker = null;
        const fromWelcome = sessionStorage.getItem('github_oauth_from_welcome');
        if (fromWelcome) {
            sessionStorage.removeItem('github_oauth_from_welcome');
            Router.go('/console');
        }
    }
    async _handleTrackerAdded(event) {
        // Don't close modal if there are warnings to display
        if (!event.detail?.hasWarnings) {
            this.isAddingTracker = false;
        }
        await this.trackerListElement?.fetchTrackers();
    }
    async _handleTrackerUpdated(event) {
        // Don't close modal if there are warnings to display
        if (!event.detail?.hasWarnings) {
            this.editingTracker = null;
        }
        await this.trackerListElement?.fetchTrackers();
    }
    _handleTrackerEdit(event) {
        this.editingTracker = event.detail.tracker;
        this.isAddingTracker = false;
    }
    _dismissGitHubError() {
        this.githubError = null;
    }
    render() {
        return html `
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
            ? html `
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
            ? html `<add-tracker-modal
                .githubInstallationId=${this.githubInstallationId}
                .githubTargetLogin=${this.githubTargetLogin}
                @tracker-added=${this._handleTrackerAdded}
                @close-modal=${this._closeAddTrackerForm}
              ></add-tracker-modal>`
            : ''}
          ${this.editingTracker
            ? html `<add-tracker-modal
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
};
TrackersView.styles = [unsafeCSS(consoleStyles)];
__decorate([
    state()
], TrackersView.prototype, "isAddingTracker", void 0);
__decorate([
    state()
], TrackersView.prototype, "editingTracker", void 0);
__decorate([
    state()
], TrackersView.prototype, "githubInstallationId", void 0);
__decorate([
    state()
], TrackersView.prototype, "githubTargetLogin", void 0);
__decorate([
    state()
], TrackersView.prototype, "githubError", void 0);
__decorate([
    query('tracker-list')
], TrackersView.prototype, "trackerListElement", void 0);
TrackersView = __decorate([
    customElement('trackers-view')
], TrackersView);
export { TrackersView };
