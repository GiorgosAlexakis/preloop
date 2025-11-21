import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import './theme-switcher.ts';
import * as api from '../api.ts';
import { Router } from '@vaadin/router';
import { unifiedWebSocketManager } from '../services/unified-websocket-manager';

interface UserDetails {
  username: string;
  email: string;
  full_name: string;
}

interface FlowExecution {
  id: string;
  flow_id: string;
  flow_name?: string;
  status: string;
  start_time: string;
  end_time: string | null;
}

@customElement('console-header')
export class ConsoleHeader extends LitElement {
  @state()
  private _user: UserDetails | null = null;

  @state()
  private _runningExecutions: FlowExecution[] = [];

  private unsubscribe?: () => void;

  static styles = css`
    :host {
      display: block;
    }
    .header-container {
      display: flex;
      justify-content: flex-end;
      align-items: center;
      padding: 0.4rem;
      border-bottom: 1px solid var(--sl-color-neutral-200);
    }
    .user-menu {
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .user-menu sl-icon-button {
      font-size: 1.8rem;
    }
    .theme-switcher-container {
      padding: 0.5rem 1rem;
    }
    .user-info {
      padding: 0.5rem 1rem;
      line-height: 1.4;
    }
    .user-name {
      font-weight: bold;
    }
    .user-email {
      color: var(--sl-color-neutral-500);
    }
    .notification-button {
      position: relative;
    }
    .execution-list {
      max-width: 400px;
      max-height: 300px;
      overflow-y: auto;
    }
    .execution-item {
      padding: 0.75rem;
      cursor: pointer;
      border-bottom: 1px solid var(--sl-color-neutral-100);
    }
    .execution-item:hover {
      background-color: var(--sl-color-neutral-50);
    }
    .execution-name {
      font-weight: 500;
      margin-bottom: 0.25rem;
    }
    .execution-time {
      font-size: 0.875rem;
      color: var(--sl-color-neutral-500);
    }
    .no-executions {
      padding: 1rem;
      text-align: center;
      color: var(--sl-color-neutral-500);
    }
  `;

  async connectedCallback() {
    super.connectedCallback();
    this.fetchUserDetails();
    this.connectToFlowUpdates();
    this.loadRunningExecutions();
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.unsubscribe?.();
  }

  private async loadRunningExecutions() {
    try {
      const executions = await api.getFlowExecutions();
      // Filter for running/pending executions
      this._runningExecutions = executions.filter(
        (exec: FlowExecution) =>
          exec.status === 'RUNNING' || exec.status === 'PENDING'
      );
    } catch (error) {
      console.error('Failed to load running executions:', error);
    }
  }

  private connectToFlowUpdates() {
    this.unsubscribe = unifiedWebSocketManager.subscribe(
      'flow_executions',
      (message) => {
        console.log('Console header received flow update:', message);

        // Handle new execution
        if (message.type === 'execution_started') {
          const newExecution: FlowExecution = {
            id: message.execution_id,
            flow_id: message.flow_id,
            status: message.payload.status || 'PENDING',
            start_time: message.timestamp,
            end_time: null,
            flow_name: message.payload.flow_name,
          };

          // Add to running executions if not already there
          const exists = this._runningExecutions.some(
            (exec) => exec.id === newExecution.id
          );
          if (!exists) {
            this._runningExecutions = [
              newExecution,
              ...this._runningExecutions,
            ];
          }
        }

        // Handle status updates
        if (message.type === 'status_update' && message.execution_id) {
          const status = message.payload.status;
          const executionIndex = this._runningExecutions.findIndex(
            (exec) => exec.id === message.execution_id
          );

          if (executionIndex !== -1) {
            // If status is no longer running/pending, remove from list
            if (
              status !== 'RUNNING' &&
              status !== 'PENDING' &&
              status !== 'STARTING' &&
              status !== 'INITIALIZING'
            ) {
              this._runningExecutions = [
                ...this._runningExecutions.slice(0, executionIndex),
                ...this._runningExecutions.slice(executionIndex + 1),
              ];
            } else {
              // Update the execution
              const updatedExecution = {
                ...this._runningExecutions[executionIndex],
                status: status,
                end_time: message.payload.end_time || null,
              };
              this._runningExecutions = [
                ...this._runningExecutions.slice(0, executionIndex),
                updatedExecution,
                ...this._runningExecutions.slice(executionIndex + 1),
              ];
            }
          }
        }
      }
    );

    // Track connection state
    unifiedWebSocketManager.onStateChange((state) => {
      console.log(`Console header WebSocket state: ${state}`);
    });
  }

  async fetchUserDetails() {
    try {
      this._user = await api.getAccountDetails();
    } catch (error) {
      console.error('Failed to fetch user details', error);
    }
  }

  async signOut() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    window.dispatchEvent(
      new CustomEvent('auth-change', { bubbles: true, composed: true })
    );
    window.location.href = '/';
    fetch('/logout', { method: 'GET' }).catch((error) => {
      console.error('Logout request to server failed:', error);
    });
  }

  private formatRelativeTime(dateString: string): string {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);

    if (diffMinutes < 1) return 'just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;

    const diffHours = Math.floor(diffMinutes / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  }

  private navigateToExecution(executionId: string) {
    Router.go(`/console/flow-executions/${executionId}`);
  }

  render() {
    return html`
      <div class="header-container">
        <div class="user-menu">
          <!-- Flow Execution Notifications -->
          ${this._runningExecutions.length > 0
            ? html`
                <sl-dropdown distance="8">
                  <div slot="trigger" class="notification-button">
                    <sl-icon-button
                      name="activity"
                      label="Running Flow Executions"
                    >
                      <sl-badge
                        variant="primary"
                        pill
                        style="position: absolute; top: -4px; right: -4px;"
                      >
                        ${this._runningExecutions.length}
                      </sl-badge>
                    </sl-icon-button>
                  </div>
                  <div class="execution-list">
                    ${this._runningExecutions.map(
                      (exec) => html`
                        <div
                          class="execution-item"
                          @click=${() => this.navigateToExecution(exec.id)}
                        >
                          <div class="execution-name">
                            ${exec.flow_name || 'Flow Execution'}
                          </div>
                          <div class="execution-time">
                            <sl-badge variant="warning"
                              >${exec.status}</sl-badge
                            >
                            • ${this.formatRelativeTime(exec.start_time)}
                          </div>
                        </div>
                      `
                    )}
                  </div>
                </sl-dropdown>
              `
            : ''}

          <!-- User Menu -->
          <sl-dropdown distance="8">
            <sl-icon-button
              name="person-circle"
              slot="trigger"
              label="User Menu"
            ></sl-icon-button>
            <sl-menu>
              <div class="user-info">
                <div class="user-name">
                  ${this._user?.full_name || this._user?.username}
                </div>
                <div class="user-email">${this._user?.email}</div>
              </div>
              <sl-divider></sl-divider>
              <sl-menu-item
                @click=${() => Router.go('/console/settings/profile')}
              >
                <sl-icon name="person-circle" slot="prefix"></sl-icon>
                Profile
              </sl-menu-item>
              <sl-menu-item
                @click=${() => Router.go('/console/settings/security')}
              >
                <sl-icon name="lock" slot="prefix"></sl-icon>
                Security
              </sl-menu-item>
              <sl-menu-item
                @click=${() =>
                  Router.go('/console/settings/notification-preferences')}
              >
                <sl-icon name="bell" slot="prefix"></sl-icon>
                Notification Preferences
              </sl-menu-item>
              <sl-divider></sl-divider>
              <sl-menu-item @click=${this.signOut}>
                <sl-icon name="box-arrow-right" slot="prefix"></sl-icon>
                Sign Out
              </sl-menu-item>
            </sl-menu>
          </sl-dropdown>
        </div>
      </div>
    `;
  }
}
