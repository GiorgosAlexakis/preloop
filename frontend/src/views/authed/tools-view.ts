import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import {
  getTools,
  getMCPServers,
  deleteMCPServer,
  scanMCPServer,
  updateMCPServer,
  createToolConfiguration,
  updateToolConfiguration,
  updateToolApprovalCondition,
  getApprovalPolicies,
  createApprovalPolicy,
  updateApprovalPolicy,
} from '../../api';
import '../../components/mcp-server-form';
import '../../components/mcp-server-card';
import '../../components/tool-card';
import '../../components/mcp-setup-dialog';
import type { Tool, ApprovalPolicy } from '../../components/tool-card';
import type { MCPServer } from '../../components/mcp-server-card';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import '@shoelace-style/shoelace/dist/components/details/details.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import consoleStyles from '../../styles/console-styles.css?inline';

@customElement('tools-view')
export class ToolsView extends LitElement {
  @state()
  private tools: Tool[] = [];

  @state()
  private mcpServers: MCPServer[] = [];

  @state()
  private approvalPolicies: ApprovalPolicy[] = [];

  @state()
  private loading = false;

  @state()
  private error: string | null = null;

  @state()
  private isAddingMCPServer = false;

  @state()
  private editingMCPServer: MCPServer | null = null;

  @state()
  private activeTab: 'all' | 'builtin' | string = 'all';

  @state()
  private showSetupDialog = false;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      .tabs {
        display: flex;
        gap: 0.5rem;
        margin-bottom: 2rem;
        border-bottom: 1px solid var(--sl-color-neutral-200);
        flex-wrap: wrap;
      }

      .tab {
        padding: 0.75rem 1rem;
        background: none;
        border: none;
        border-bottom: 2px solid transparent;
        cursor: pointer;
        font-size: 0.9rem;
        color: var(--sl-color-neutral-600);
        transition: all 0.2s;
        white-space: nowrap;
      }

      .tab:hover {
        color: var(--sl-color-neutral-900);
      }

      .tab.active {
        color: var(--sl-color-primary-600);
        border-bottom-color: var(--sl-color-primary-600);
      }

      .tools-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: var(--sl-spacing-large);
        padding-top: var(--sl-spacing-medium);
      }

      .servers-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
        gap: var(--sl-spacing-medium);
        margin-bottom: 2rem;
      }

      .loading-indicator {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
      }

      .empty-state {
        text-align: center;
        padding: 3rem;
        color: var(--sl-color-neutral-600);
      }

      .proxy-notice {
        background: var(--sl-color-primary-50);
        border-left: 3px solid var(--sl-color-primary-600);
        padding: 1rem;
        margin-bottom: 1.5rem;
        border-radius: 4px;
      }

      .proxy-notice-title {
        font-weight: 600;
        color: var(--sl-color-primary-900);
        margin-bottom: 0.5rem;
      }

      .proxy-notice-text {
        color: var(--sl-color-primary-800);
        font-size: 0.9rem;
        line-height: 1.5;
      }

      .builtin-server-card {
        display: flex;
        flex-direction: column;
        height: 100%;
      }

      .builtin-card-content {
        flex-grow: 1;
        display: flex;
        flex-direction: column;
      }

      .builtin-server-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--sl-spacing-small);
      }

      .builtin-server-name {
        font-size: var(--sl-font-size-medium);
        font-weight: var(--sl-font-weight-semibold);
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .builtin-server-url {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-600);
        margin: 0 0 var(--sl-spacing-x-small) 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        font-family: monospace;
      }

      .server-meta {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-700);
        margin-bottom: var(--sl-spacing-x-small);
      }

      .info-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        padding: 0.25rem 0;
        border-bottom: 1px solid var(--sl-color-neutral-100);
        font-size: var(--sl-font-size-x-small);
      }

      .info-row:first-child {
        padding-top: 0.25rem;
      }

      .info-row:last-child {
        border-bottom: none;
      }

      .info-label {
        font-weight: 600;
        color: var(--sl-color-neutral-700);
        padding-top: 0.2rem;
      }

      .info-value-container {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        gap: 0.25rem;
      }

      .info-value {
        color: var(--sl-color-neutral-900);
        font-family: monospace;
        background: var(--sl-color-neutral-50);
        padding: 0.2rem 0.4rem;
        border-radius: 4px;
        font-size: var(--sl-font-size-x-small);
      }

      .info-link {
        color: var(--sl-color-primary-600);
        text-decoration: none;
        font-size: var(--sl-font-size-x-small);
      }

      .info-link:hover {
        text-decoration: underline;
      }

      .help-text {
        color: var(--sl-color-neutral-600);
        font-size: 0.85rem;
        line-height: 1.5;
        margin-top: 0.5rem;
      }

      sl-card::part(footer) {
        padding: var(--sl-spacing-medium);
        border-top: 1px solid var(--sl-color-neutral-200);
      }
    `,
  ];

  connectedCallback() {
    super.connectedCallback();
    this.loadData();
  }

  private async loadData() {
    this.loading = true;
    this.error = null;

    try {
      const [tools, servers, policies] = await Promise.all([
        getTools(),
        getMCPServers(),
        getApprovalPolicies(),
      ]);

      // Count enabled tools per server
      const toolCounts = new Map<string, number>();
      tools.forEach((tool: Tool) => {
        if (tool.source === 'mcp' && tool.source_id && tool.is_enabled) {
          toolCounts.set(
            tool.source_id,
            (toolCounts.get(tool.source_id) || 0) + 1
          );
        }
      });

      this.tools = tools;
      this.mcpServers = servers.map((server: MCPServer) => ({
        ...server,
        tool_count: toolCounts.get(server.id) || 0,
      }));
      this.approvalPolicies = policies;
    } catch (err: any) {
      this.error = err.message || 'Failed to load data';
      console.error('Error loading tools and MCP servers:', err);
    } finally {
      this.loading = false;
    }
  }

  private async handleServerAdded() {
    this.isAddingMCPServer = false;
    await this.loadData();
  }

  private async handleServerUpdated() {
    this.editingMCPServer = null;
    await this.loadData();
  }

  private closeServerForm() {
    this.isAddingMCPServer = false;
    this.editingMCPServer = null;
  }

  private handleServerEdit(event: CustomEvent) {
    this.editingMCPServer = event.detail.server;
    this.isAddingMCPServer = false;
  }

  private async handleToggleEnabled(event: CustomEvent) {
    const tool: Tool = event.detail.tool;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Update local state immediately for instant feedback
      const updatedTools = this.tools.map((t) => {
        if (
          t.name === tool.name &&
          t.source === tool.source &&
          t.source_id === tool.source_id
        ) {
          return { ...t, is_enabled: !t.is_enabled };
        }
        return t;
      });
      this.tools = updatedTools;

      // Update on server in background
      if (tool.config_id) {
        await updateToolConfiguration(tool.config_id, {
          is_enabled: !tool.is_enabled,
        });
      } else {
        await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          is_enabled: !tool.is_enabled,
          account_id: '',
        });
      }

      // Restore scroll position
      window.scrollTo(0, scrollY);
    } catch (err: any) {
      this.error = err.message || 'Failed to update tool configuration';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handleToggleApproval(event: CustomEvent) {
    const { tool, enable } = event.detail;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Update local state immediately for instant feedback
      const updatedTools = this.tools.map((t) => {
        if (
          t.name === tool.name &&
          t.source === tool.source &&
          t.source_id === tool.source_id
        ) {
          // When disabling, clear the approval_policy_id
          return {
            ...t,
            approval_policy_id: enable ? t.approval_policy_id : null,
          };
        }
        return t;
      });
      this.tools = updatedTools;

      // Update on server - when disabling, remove approval_policy_id
      if (tool.config_id) {
        await updateToolConfiguration(tool.config_id, {
          approval_policy_id: enable ? tool.approval_policy_id : null,
        });
      } else if (!enable) {
        // If disabling and no config exists, no need to create one
        // The tool will just use default (no approval)
      }

      // Restore scroll position
      window.scrollTo(0, scrollY);
    } catch (err: any) {
      this.error = err.message || 'Failed to update tool configuration';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handlePolicySelected(event: CustomEvent) {
    const { tool, policyId } = event.detail;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Update local state immediately for instant feedback
      const updatedTools = this.tools.map((t) => {
        if (
          t.name === tool.name &&
          t.source === tool.source &&
          t.source_id === tool.source_id
        ) {
          return {
            ...t,
            approval_policy_id: policyId,
          };
        }
        return t;
      });
      this.tools = updatedTools;

      // Assign policy on server
      if (tool.config_id) {
        await updateToolConfiguration(tool.config_id, {
          approval_policy_id: policyId,
        });
      } else {
        await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          approval_policy_id: policyId,
          account_id: '',
        });
      }

      // Restore scroll position
      window.scrollTo(0, scrollY);

      console.log('Policy assigned for tool:', tool.name, 'Policy:', policyId);
    } catch (err: any) {
      this.error = err.message || 'Failed to assign policy';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handleCreatePolicy(event: CustomEvent) {
    const { tool, policy } = event.detail;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Create the new policy
      const newPolicy = await createApprovalPolicy(policy);

      // Update local policy list
      this.approvalPolicies = [...this.approvalPolicies, newPolicy];

      // Update local state immediately for instant feedback
      const updatedTools = this.tools.map((t) => {
        if (
          t.name === tool.name &&
          t.source === tool.source &&
          t.source_id === tool.source_id
        ) {
          return {
            ...t,
            approval_policy_id: newPolicy.id,
          };
        }
        return t;
      });
      this.tools = updatedTools;

      // Assign the new policy on server
      if (tool.config_id) {
        await updateToolConfiguration(tool.config_id, {
          approval_policy_id: newPolicy.id,
        });
      } else {
        await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          approval_policy_id: newPolicy.id,
          account_id: '',
        });
      }

      // Restore scroll position
      window.scrollTo(0, scrollY);

      console.log(
        'Created and applied policy:',
        newPolicy.name,
        'for tool:',
        tool.name
      );
    } catch (err: any) {
      this.error = err.message || 'Failed to create policy';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handleUpdatePolicy(event: CustomEvent) {
    const { policyId, policy } = event.detail;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Update the policy on the server
      const updatedPolicy = await updateApprovalPolicy(policyId, policy);

      // Update local policy list
      this.approvalPolicies = this.approvalPolicies.map((p) =>
        p.id === policyId ? updatedPolicy : p
      );

      // Restore scroll position
      window.scrollTo(0, scrollY);

      console.log('Updated policy:', updatedPolicy.name);
    } catch (err: any) {
      this.error = err.message || 'Failed to update policy';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handleSaveCondition(event: CustomEvent) {
    const { tool, condition } = event.detail;

    // Save scroll position
    const scrollY = window.scrollY;

    try {
      // Ensure tool configuration exists first
      let configId = tool.config_id;

      if (!configId) {
        // Create tool configuration if it doesn't exist
        const newConfig = await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          account_id: '',
        });
        configId = newConfig.id;

        // Update local tool with new config_id
        const updatedTools = this.tools.map((t) => {
          if (
            t.name === tool.name &&
            t.source === tool.source &&
            t.source_id === tool.source_id
          ) {
            return { ...t, config_id: configId };
          }
          return t;
        });
        this.tools = updatedTools;
      }

      // Update local state immediately for instant feedback
      const updatedTools = this.tools.map((t) => {
        if (
          t.name === tool.name &&
          t.source === tool.source &&
          t.source_id === tool.source_id
        ) {
          return {
            ...t,
            has_approval_condition: !!condition,
          };
        }
        return t;
      });
      this.tools = updatedTools;

      // Save condition using dedicated endpoint
      await updateToolApprovalCondition(configId, condition);

      // Restore scroll position
      window.scrollTo(0, scrollY);

      console.log(
        'Saved condition for tool:',
        tool.name,
        'Condition:',
        condition
      );
    } catch (err: any) {
      this.error = err.message || 'Failed to save condition';
      // Reload on error to revert optimistic update
      await this.loadData();
    }
  }

  private async handleScanMCPServer(event: CustomEvent) {
    const serverId = event.detail.id;
    try {
      await scanMCPServer(serverId);
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to scan MCP server';
    }
  }

  private async handleDeleteMCPServer(event: CustomEvent) {
    const serverId = event.detail.id;
    try {
      await deleteMCPServer(serverId);
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to delete MCP server';
    }
  }

  private async handleToggleMCPServer(event: CustomEvent) {
    const { id, enabled } = event.detail;
    try {
      await updateMCPServer(id, {
        status: enabled ? 'active' : 'disabled',
      });
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to update MCP server status';
    }
  }

  private getFilteredTools(): Tool[] {
    if (this.activeTab === 'all') {
      return this.tools;
    } else if (this.activeTab === 'builtin') {
      return this.tools.filter((t) => t.source === 'builtin');
    } else {
      // activeTab is a server ID
      return this.tools.filter(
        (t) => t.source === 'mcp' && t.source_id === this.activeTab
      );
    }
  }

  private renderBuiltinMCPCard() {
    const apiUrl = window.location.origin;
    const mcpUrl = `${apiUrl}/mcp/v1`;
    const builtinToolCount = this.tools.filter(
      (t) => t.source === 'builtin' && t.is_enabled
    ).length;
    const proxiedToolCount = this.tools.filter(
      (t) => t.source === 'mcp' && t.is_enabled
    ).length;
    const totalToolCount = builtinToolCount + proxiedToolCount;

    return html`
      <sl-card class="builtin-server-card">
        <div class="builtin-card-content">
          <div class="builtin-server-header">
            <h3 class="builtin-server-name">Preloop AI MCP Server</h3>
            <sl-badge variant="success" size="small">Built-in</sl-badge>
          </div>
          <p class="builtin-server-url" title=${mcpUrl}>${mcpUrl}</p>
          <div class="server-meta">
            ${totalToolCount} tool${totalToolCount !== 1 ? 's' : ''}:
            ${builtinToolCount} built-in, ${proxiedToolCount} proxied
          </div>

          <div class="info-row">
            <span class="info-label">Authentication:</span>
            <div class="info-value-container">
              <code class="info-value">Bearer Token</code>
              <a href="/console/settings/api-keys" class="info-link">
                Manage Keys →
              </a>
            </div>
          </div>
        </div>

        <div slot="footer">
          <sl-button
            size="small"
            style="width: 100%;"
            @click=${() => (this.showSetupDialog = true)}
          >
            <sl-icon slot="prefix" name="info-circle"></sl-icon>
            Setup Instructions
          </sl-button>
        </div>
      </sl-card>

      <mcp-setup-dialog
        ?open=${this.showSetupDialog}
        @close=${() => (this.showSetupDialog = false)}
      ></mcp-setup-dialog>
    `;
  }

  render() {
    const filteredTools = this.getFilteredTools();
    const builtinTools = this.tools.filter((t) => t.source === 'builtin');

    return html`
      <view-header headerText="Tools">
        <div slot="main-column">
          <sl-button
            variant="primary"
            @click=${() => (this.isAddingMCPServer = true)}
          >
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add MCP Server
          </sl-button>
        </div>
      </view-header>

      <div class="column-layout">
        <div class="main-column">
          ${this.isAddingMCPServer
        ? html`<mcp-server-form
                @server-added=${this.handleServerAdded}
                @close-modal=${this.closeServerForm}
              ></mcp-server-form>`
        : ''}
          ${this.editingMCPServer
        ? html`<mcp-server-form
                .server=${this.editingMCPServer}
                @server-updated=${this.handleServerUpdated}
                @close-modal=${this.closeServerForm}
              ></mcp-server-form>`
        : ''}
          ${this.error
        ? html`<sl-alert variant="danger" open>
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                <strong>Error:</strong> ${this.error}
              </sl-alert>`
        : ''}
          <div class="proxy-notice">
            <div class="proxy-notice-text">
              Tools from external MCP servers are proxied through the
              Preloop AI MCP server. Any tool (built-in or external) can be
              "prelooped" with a human approval policy, requiring review and
              approval by the appropriate users before allowing tool executions
              to run.
            </div>
          </div>
          ${this.loading
        ? html`<div class="loading-indicator">
                <sl-spinner></sl-spinner>
              </div>`
        : html`
                <div class="servers-grid">
                  ${this.renderBuiltinMCPCard()}
                  ${repeat(
          this.mcpServers,
          (server) => server.id,
          (server) =>
            html`<mcp-server-card
                        .server=${server}
                        @server-edit=${this.handleServerEdit}
                        @server-scan=${this.handleScanMCPServer}
                        @server-deleted=${this.handleDeleteMCPServer}
                        @server-toggle-enabled=${this.handleToggleMCPServer}
                      ></mcp-server-card>`
        )}
                </div>

                <div class="tabs">
                  <button
                    class="tab ${this.activeTab === 'all' ? 'active' : ''}"
                    @click=${() => (this.activeTab = 'all')}
                  >
                    All Tools (${this.tools.length})
                  </button>
                  <button
                    class="tab ${this.activeTab === 'builtin' ? 'active' : ''}"
                    @click=${() => (this.activeTab = 'builtin')}
                  >
                    Built-in (${builtinTools.length})
                  </button>
                  ${this.mcpServers.map(
          (server) => html`
                      <button
                        class="tab ${this.activeTab === server.id
              ? 'active'
              : ''}"
                        @click=${() => (this.activeTab = server.id)}
                      >
                        ${server.name} (${server.tool_count || 0})
                      </button>
                    `
        )}
                </div>

                ${filteredTools.length === 0
            ? html`<div class="empty-state">
                      <p>No tools available in this category.</p>
                    </div>`
            : html`
                      <div class="tools-grid">
                        ${repeat(
              filteredTools,
              (tool) =>
                `${tool.name}-${tool.source}-${tool.source_id}`,
              (tool) =>
                html`<tool-card
                              .tool=${tool}
                              .policies=${this.approvalPolicies}
                              @toggle-enabled=${this.handleToggleEnabled}
                              @toggle-approval=${this.handleToggleApproval}
                              @policy-selected=${this.handlePolicySelected}
                              @create-policy=${this.handleCreatePolicy}
                              @update-policy=${this.handleUpdatePolicy}
                              @save-condition=${this.handleSaveCondition}
                            ></tool-card>`
            )}
                      </div>
                    `}
              `}
        </div>
        <div class="side-column"></div>
      </div>
    `;
  }
}
