import { LitElement, html, css, unsafeCSS, type TemplateResult } from 'lit';
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
  getApprovalPolicies,
  deleteApprovalPolicy,
  getFeatures,
  getAccountDetails,
  createAccessRule,
  updateAccessRule,
  deleteAccessRule,
  fetchWithAuth,
} from '../../api';
import '../../components/mcp-server-form';
import '../../components/mcp-server-card';
import '../../components/tool-list-item';
import '../../components/mcp-setup-dialog';
import '../../components/approval-policy-dialog';
import type { Tool, ApprovalPolicy } from '../../components/tool-card';
import type { MCPServer } from '../../components/mcp-server-card';
import type { AccessRuleSummary } from '../../components/tool-list-item';
import type { RuleFormData } from '../../components/tool-rule-editor';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/spinner/spinner.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '@shoelace-style/shoelace/dist/components/card/card.js';
import consoleStyles from '../../styles/console-styles.css?inline';

// Extended Tool type that includes access rules from the API
interface ToolWithRules extends Tool {
  access_rules: AccessRuleSummary[];
}

interface ToolGroup {
  id: string;
  name: string;
  type: 'builtin' | 'mcp' | 'http';
  server?: MCPServer;
  tools: ToolWithRules[];
  collapsed: boolean;
}

@customElement('tools-view')
export class ToolsView extends LitElement {
  @state() private tools: ToolWithRules[] = [];
  @state() private mcpServers: MCPServer[] = [];
  @state() private approvalPolicies: ApprovalPolicy[] = [];
  @state() private loading = false;
  @state() private error: string | null = null;
  @state() private isAddingMCPServer = false;
  @state() private editingMCPServer: MCPServer | null = null;
  @state() private currentUser: { id: string } | null = null;
  @state() private showSetupDialog = false;
  @state() private features: { [key: string]: boolean | string[] } = {};
  @state() private expandedTools: Set<string> = new Set();
  @state() private collapsedGroups: Set<string> = new Set();
  @state() private filterText = '';
  @state() private isExporting = false;

  // Single active filter — only one at a time (besides text/policy)
  @state() private activeFilter:
    | 'all'
    | 'available'
    | 'enabled'
    | 'disabled'
    | 'unavailable'
    | 'builtin'
    | 'mcp'
    | 'has_rules'
    | 'no_rules'
    | 'require_approval'
    | 'no_approval' = 'available';
  @state() private filterPolicyId: string | null = null;

  // Approval policy dialog
  @state() private showPolicyDialog = false;
  @state() private editingPolicy: ApprovalPolicy | null = null;

  static styles = [
    unsafeCSS(consoleStyles),
    css`
      mcp-setup-dialog {
        display: contents;
      }

      /* Top section: summary + MCP card side by side */
      .top-section {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: var(--sl-spacing-large);
      }

      @media (max-width: 900px) {
        .top-section {
          flex-direction: column;
          margin-bottom: var(--sl-spacing-small);
          gap: var(--sl-spacing-small);
        }
      }

      /* MCP Server card */
      .builtin-server-card {
        flex: 0 1 400px;
        max-width: 400px;
      }

      @media (max-width: 900px) {
        .builtin-server-card {
          max-width: none;
          width: 100%;
        }
      }

      .builtin-server-card::part(body) {
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
      }

      .builtin-server-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: var(--sl-spacing-2x-small);
      }

      .builtin-server-name {
        font-size: var(--sl-font-size-medium);
        font-weight: var(--sl-font-weight-semibold);
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .info-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.15rem 0;
        font-size: var(--sl-font-size-x-small);
      }

      .info-label {
        font-weight: 600;
        color: var(--sl-color-neutral-700);
      }

      .info-value-container {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
      }

      .info-value {
        color: var(--sl-color-neutral-900);
        font-family: monospace;
        background: var(--sl-color-neutral-50);
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: var(--sl-font-size-x-small);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        max-width: 220px;
      }

      .info-link {
        color: var(--sl-color-primary-600);
        text-decoration: none;
        font-size: var(--sl-font-size-x-small);
        white-space: nowrap;
      }

      .info-link:hover {
        text-decoration: underline;
      }

      sl-card::part(footer) {
        padding: var(--sl-spacing-x-small) var(--sl-spacing-medium);
        border-top: 1px solid var(--sl-color-neutral-200);
      }

      /* Summary table */
      .summary-table-wrapper {
        flex: 0 1 auto;
      }

      .summary-table {
        border-collapse: collapse;
        font-size: var(--sl-font-size-small);
      }

      .summary-table td {
        padding: 0;
        vertical-align: middle;
        white-space: nowrap;
      }

      .summary-stat {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: var(--sl-spacing-medium);
        color: var(--sl-color-neutral-700);
        cursor: pointer;
        padding: 4px 8px;
        border-radius: var(--sl-border-radius-small);
        transition: background 0.1s ease;
        white-space: nowrap;
      }

      .summary-stat:hover {
        background: var(--sl-color-neutral-100);
      }

      .summary-stat.active {
        background: var(--sl-color-primary-100);
        color: var(--sl-color-primary-700);
        font-weight: var(--sl-font-weight-semibold);
      }

      .summary-stat strong {
        font-variant-numeric: tabular-nums;
        color: var(--sl-color-neutral-900);
      }

      .summary-stat.active strong {
        color: var(--sl-color-primary-700);
      }

      .summary-stat.muted {
        opacity: 0.4;
        cursor: default;
      }

      .summary-stat.muted:hover {
        background: none;
      }

      /* Filter area: policy row + search row */
      .filter-area {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
        margin-bottom: var(--sl-spacing-large);
      }

      .policy-row {
        display: flex;
        justify-content: flex-end;
        margin-bottom: 0.6em;
      }

      .filter-bar {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        flex-wrap: wrap;
      }

      .filter-search {
        flex: 1;
        min-width: 200px;
      }

      .filter-buttons {
        display: flex;
        gap: var(--sl-spacing-2x-small);
        flex-shrink: 0;
        flex-wrap: wrap;
      }

      .filter-chip {
        font-size: var(--sl-font-size-x-small);
      }

      .filter-chip[variant='primary']::part(base) {
        font-weight: 600;
      }

      /* Section headers */
      .section-header {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-small);
        padding: var(--sl-spacing-small) 0;
        margin-top: var(--sl-spacing-medium);
        cursor: pointer;
        user-select: none;
      }

      .section-header:first-of-type {
        margin-top: 0;
      }

      .section-header:hover .section-title {
        color: var(--sl-color-neutral-900);
      }

      .section-icon {
        color: var(--sl-color-neutral-500);
        transition: transform 0.2s ease;
        flex-shrink: 0;
      }

      .section-icon.open {
        transform: rotate(90deg);
      }

      .section-title {
        font-size: var(--sl-font-size-small);
        font-weight: var(--sl-font-weight-bold);
        color: var(--sl-color-neutral-600);
        text-transform: uppercase;
        letter-spacing: 0.05em;
      }

      .section-meta {
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-500);
      }

      .section-actions {
        display: flex;
        gap: var(--sl-spacing-2x-small);
      }

      .section-line {
        flex: 1;
        height: 1px;
        background: var(--sl-color-neutral-200);
      }

      /* Tool list */
      .tool-list {
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-x-small);
        margin-bottom: var(--sl-spacing-medium);
      }

      .loading-indicator {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 200px;
      }

      .empty-state {
        text-align: center;
        padding: var(--sl-spacing-x-large);
        color: var(--sl-color-neutral-500);
      }

      /* Policy chip bar (above filter bar, right-aligned) */
      .policy-chip-bar {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-x-small);
        flex-wrap: wrap;
        font-size: var(--sl-font-size-small);
      }

      .policy-chip-bar-label {
        color: var(--sl-color-neutral-500);
        font-size: var(--sl-font-size-x-small);
        font-weight: var(--sl-font-weight-semibold);
        text-transform: uppercase;
        letter-spacing: 0.04em;
        white-space: nowrap;
        padding-right: var(--sl-spacing-2x-small);
      }

      .policy-chip {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 4px 2px 10px;
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-pill);
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-700);
        cursor: pointer;
        transition: all 0.15s ease;
        white-space: nowrap;
        background: var(--sl-color-neutral-0);
      }

      .policy-chip:hover {
        border-color: var(--sl-color-neutral-400);
        background: var(--sl-color-neutral-50);
      }

      .policy-chip.active {
        border-color: var(--sl-color-primary-400);
        background: var(--sl-color-primary-50);
        color: var(--sl-color-primary-700);
      }

      .policy-chip .policy-chip-name {
        max-width: 180px;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .policy-chip sl-icon-button {
        font-size: 0.65rem;
        color: var(--sl-color-neutral-500);
      }

      .policy-chip sl-icon-button:hover {
        color: var(--sl-color-neutral-900);
      }

      .policy-chip .policy-chip-type {
        font-size: 0.6rem;
        padding: 1px 5px;
        border-radius: var(--sl-border-radius-pill);
        background: var(--sl-color-neutral-100);
        color: var(--sl-color-neutral-500);
      }

      .policy-chip.active .policy-chip-type {
        background: var(--sl-color-primary-100);
        color: var(--sl-color-primary-600);
      }

      .policy-chip-add {
        display: inline-flex;
        align-items: center;
        gap: 3px;
        padding: 2px 10px;
        border: 1px dashed var(--sl-color-neutral-300);
        border-radius: var(--sl-border-radius-pill);
        font-size: var(--sl-font-size-x-small);
        color: var(--sl-color-neutral-500);
        cursor: pointer;
        transition: all 0.15s ease;
        background: none;
        white-space: nowrap;
      }

      .policy-chip-add:hover {
        border-color: var(--sl-color-primary-400);
        color: var(--sl-color-primary-600);
        background: var(--sl-color-primary-50);
      }

      .policy-chip-empty {
        color: var(--sl-color-neutral-400);
        font-size: var(--sl-font-size-x-small);
        font-style: italic;
      }

      /* Active filter tags */
      .active-filters {
        display: flex;
        align-items: center;
        gap: var(--sl-spacing-2x-small);
        flex-wrap: wrap;
      }

      .active-filter-tag {
        display: inline-flex;
        align-items: center;
        gap: var(--sl-spacing-2x-small);
        padding: 2px 8px;
        background: var(--sl-color-primary-100);
        color: var(--sl-color-primary-700);
        border-radius: var(--sl-border-radius-pill);
        font-size: var(--sl-font-size-x-small);
        font-weight: 500;
      }

      .active-filter-tag sl-icon-button {
        font-size: 0.7rem;
      }
    `,
  ];

  private static readonly _FILTER_STORAGE_KEY = 'preloop:tools-filter';

  connectedCallback() {
    super.connectedCallback();
    const saved = localStorage.getItem(ToolsView._FILTER_STORAGE_KEY);
    if (saved) {
      this.activeFilter = saved as typeof this.activeFilter;
    }
    this.loadData();
  }

  private _setFilter(filter: typeof this.activeFilter) {
    this.activeFilter = filter;
    localStorage.setItem(ToolsView._FILTER_STORAGE_KEY, filter);
  }

  private async loadData() {
    this.loading = true;
    this.error = null;

    try {
      const [tools, servers, policies, featuresResponse, currentUser] =
        await Promise.all([
          getTools(),
          getMCPServers(),
          getApprovalPolicies(),
          getFeatures(),
          getAccountDetails(),
        ]);

      this.currentUser = currentUser;
      this.features = featuresResponse.features || {};
      this.tools = tools as ToolWithRules[];
      this.mcpServers = servers;
      this.approvalPolicies = policies;
    } catch (err: any) {
      this.error = err.message || 'Failed to load data';
      console.error('Error loading tools data:', err);
    } finally {
      this.loading = false;
    }
  }

  // ─── Stats helpers ──────────────────────────────────

  private _getStats() {
    const all = this.tools;
    const available = all.filter((t) => t.is_supported !== false);
    const unavailable = all.filter((t) => t.is_supported === false);
    const enabled = available.filter((t) => t.is_enabled);
    const disabled = available.filter((t) => !t.is_enabled);
    const builtin = available.filter((t) => t.source === 'builtin');
    const proxied = available.filter((t) => t.source === 'mcp');
    const withRules = all.filter(
      (t) =>
        (t.access_rules && t.access_rules.length > 0) ||
        t.approval_policy_id ||
        t.has_approval_condition
    );
    const withoutRules = all.length - withRules.length;
    const requireApproval = all.filter(
      (t) =>
        t.access_rules?.some(
          (r) => r.action === 'require_approval' && r.is_enabled
        ) || t.approval_policy_id
    );
    const noApproval = all.length - requireApproval.length;

    return {
      total: all.length,
      available: available.length,
      unavailable: unavailable.length,
      enabled: enabled.length,
      disabled: disabled.length,
      builtin: builtin.length,
      proxied: proxied.length,
      withRules: withRules.length,
      withoutRules,
      requireApproval: requireApproval.length,
      noApproval,
      unavailableReasons: [
        ...new Set(
          unavailable
            .map((t) => t.unsupported_reason)
            .filter((r): r is string => !!r)
        ),
      ],
    };
  }

  // ─── Tool grouping & filtering ──────────────────────

  private _getToolGroups(): ToolGroup[] {
    const groups: ToolGroup[] = [];
    const filtered = this._getFilteredTools();

    // External MCP server groups first (more important to user)
    for (const server of this.mcpServers) {
      const serverTools = filtered.filter(
        (t) => t.source === 'mcp' && t.source_id === server.id
      );
      // Always show MCP group for server management access
      groups.push({
        id: server.id,
        name: server.name,
        type: 'mcp',
        server,
        tools: serverTools,
        collapsed: this.collapsedGroups.has(server.id),
      });
    }

    // HTTP tools group
    const httpTools = filtered.filter((t) => t.source === 'http');
    if (httpTools.length > 0) {
      groups.push({
        id: 'http',
        name: 'HTTP Tools',
        type: 'http',
        tools: httpTools,
        collapsed: this.collapsedGroups.has('http'),
      });
    }

    // Built-in tools last
    const builtinTools = filtered.filter((t) => t.source === 'builtin');
    if (builtinTools.length > 0) {
      groups.push({
        id: 'builtin',
        name: 'Built-in',
        type: 'builtin',
        tools: builtinTools,
        collapsed: this.collapsedGroups.has('builtin'),
      });
    }

    return groups;
  }

  private _getFilteredTools(): ToolWithRules[] {
    let tools = this.tools;

    // Single active filter
    switch (this.activeFilter) {
      case 'all':
        break;
      case 'available':
        tools = tools.filter((t) => t.is_supported !== false);
        break;
      case 'enabled':
        tools = tools.filter((t) => t.is_supported !== false && t.is_enabled);
        break;
      case 'disabled':
        tools = tools.filter((t) => t.is_supported !== false && !t.is_enabled);
        break;
      case 'unavailable':
        tools = tools.filter((t) => t.is_supported === false);
        break;
      case 'builtin':
        tools = tools.filter((t) => t.source === 'builtin');
        break;
      case 'mcp':
        tools = tools.filter((t) => t.source === 'mcp');
        break;
      case 'has_rules':
        tools = tools.filter(
          (t) =>
            (t.access_rules && t.access_rules.length > 0) ||
            t.approval_policy_id ||
            t.has_approval_condition
        );
        break;
      case 'no_rules':
        tools = tools.filter(
          (t) =>
            (!t.access_rules || t.access_rules.length === 0) &&
            !t.approval_policy_id &&
            !t.has_approval_condition
        );
        break;
      case 'require_approval':
        tools = tools.filter(
          (t) =>
            t.access_rules?.some(
              (r) => r.action === 'require_approval' && r.is_enabled
            ) || t.approval_policy_id
        );
        break;
      case 'no_approval':
        tools = tools.filter(
          (t) =>
            !t.access_rules?.some(
              (r) => r.action === 'require_approval' && r.is_enabled
            ) && !t.approval_policy_id
        );
        break;
    }

    // Text filter
    if (this.filterText) {
      const search = this.filterText.toLowerCase();
      tools = tools.filter(
        (t) =>
          t.name.toLowerCase().includes(search) ||
          t.description?.toLowerCase().includes(search) ||
          t.source_name?.toLowerCase().includes(search)
      );
    }

    // Policy filter
    if (this.filterPolicyId) {
      tools = tools.filter((t) => t.approval_policy_id === this.filterPolicyId);
    }

    return tools;
  }

  private _getToolKey(tool: Tool): string {
    return `${tool.name}-${tool.source}-${tool.source_id || 'none'}`;
  }

  // ─── Event handlers ──────────────────────────────────

  private _toggleGroup(groupId: string) {
    const updated = new Set(this.collapsedGroups);
    if (updated.has(groupId)) {
      updated.delete(groupId);
    } else {
      updated.add(groupId);
    }
    this.collapsedGroups = updated;
  }

  private _handleToggleExpand(e: CustomEvent) {
    const key = this._getToolKey(e.detail.tool);
    const updated = new Set(this.expandedTools);
    if (updated.has(key)) {
      updated.delete(key);
    } else {
      updated.add(key);
    }
    this.expandedTools = updated;
  }

  private async _handleToggleEnabled(e: CustomEvent) {
    const tool: ToolWithRules = e.detail.tool;

    try {
      this.tools = this.tools.map((t) => {
        if (this._getToolKey(t) === this._getToolKey(tool)) {
          return { ...t, is_enabled: !t.is_enabled };
        }
        return t;
      });

      if (tool.config_id) {
        await updateToolConfiguration(tool.config_id, {
          is_enabled: !tool.is_enabled,
        });
      } else {
        const config = await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          is_enabled: !tool.is_enabled,
          account_id: '',
        });
        this.tools = this.tools.map((t) => {
          if (this._getToolKey(t) === this._getToolKey(tool)) {
            return { ...t, config_id: config.id };
          }
          return t;
        });
      }
    } catch (err: any) {
      this.error = err.message || 'Failed to toggle tool';
      await this.loadData();
    }
  }

  private async _handleSaveRule(e: CustomEvent) {
    const { tool, existingRule, formData } = e.detail as {
      tool: ToolWithRules;
      existingRule: AccessRuleSummary | null;
      formData: RuleFormData;
    };

    try {
      let configId: string = tool.config_id || '';
      if (!configId) {
        const config = await createToolConfiguration({
          tool_name: tool.name,
          tool_source: tool.source,
          mcp_server_id: tool.source_id,
          account_id: '',
        });
        configId = config.id;
        this.tools = this.tools.map((t) => {
          if (this._getToolKey(t) === this._getToolKey(tool)) {
            return { ...t, config_id: configId };
          }
          return t;
        });
      }

      if (existingRule) {
        await updateAccessRule(existingRule.id, {
          action: formData.action,
          condition_expression: formData.condition_expression,
          condition_type: formData.condition_type,
          description: formData.description,
          is_enabled: formData.is_enabled,
          approval_policy_id: formData.approval_policy_id,
        });
      } else {
        const existingRules = tool.access_rules || [];
        const maxPriority = existingRules.reduce(
          (max, r) => Math.max(max, r.priority),
          -1
        );

        await createAccessRule(configId, {
          action: formData.action,
          condition_expression: formData.condition_expression,
          condition_type: formData.condition_type,
          priority: maxPriority + 1,
          description: formData.description,
          is_enabled: formData.is_enabled,
          approval_policy_id: formData.approval_policy_id,
        });
      }

      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to save rule';
    }
  }

  private async _handleDeleteRule(e: CustomEvent) {
    const { rule } = e.detail;
    if (!confirm('Delete this access rule? This cannot be undone.')) {
      return;
    }

    try {
      await deleteAccessRule(rule.id);
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to delete rule';
    }
  }

  private async _handleReorderRules(e: CustomEvent) {
    const { reorderedRules } = e.detail as {
      tool: any;
      reorderedRules: { id: string; priority: number }[];
    };

    try {
      // Update each rule's priority
      await Promise.all(
        reorderedRules.map((r) =>
          updateAccessRule(r.id, { priority: r.priority })
        )
      );
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to reorder rules';
    }
  }

  private async _handlePolicyCreated() {
    try {
      // Reload policies so the new policy appears in all dropdowns
      this.approvalPolicies = await getApprovalPolicies();
    } catch (err: any) {
      this.error = err.message || 'Failed to refresh approval policies';
    }
  }

  // ─── MCP Server handlers ────────────────────────────

  private async _handleServerAdded() {
    this.isAddingMCPServer = false;
    await this.loadData();
  }

  private async _handleServerUpdated() {
    this.editingMCPServer = null;
    await this.loadData();
  }

  private _closeServerForm() {
    this.isAddingMCPServer = false;
    this.editingMCPServer = null;
  }

  private _handleServerEdit(e: CustomEvent) {
    this.editingMCPServer = e.detail.server;
    this.isAddingMCPServer = false;
  }

  private async _handleScanMCPServer(serverId: string) {
    try {
      await scanMCPServer(serverId);
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to scan MCP server';
    }
  }

  private async _handleDeleteMCPServer(serverId: string) {
    try {
      await deleteMCPServer(serverId);
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to delete MCP server';
    }
  }

  private async _handleToggleMCPServer(e: CustomEvent) {
    const { id, enabled } = e.detail;
    try {
      await updateMCPServer(id, {
        status: enabled ? 'active' : 'disabled',
      });
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to update MCP server status';
    }
  }

  // ─── Import / Export ─────────────────────────────────

  private async _exportPolicies() {
    this.isExporting = true;
    try {
      const response = await fetchWithAuth(
        '/api/v1/policies/export?format=yaml'
      );
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to export');
      }
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'preloop-tools-config.yaml';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      this.error = err.message || 'Failed to export configuration';
    } finally {
      this.isExporting = false;
    }
  }

  private _triggerImport() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.yaml,.yml';
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      await this._importFile(file);
    };
    input.click();
  }

  private async _importFile(file: File) {
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetchWithAuth('/api/v1/policies/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(
          error.detail?.message || error.detail || 'Failed to import'
        );
      }

      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to import configuration';
    }
  }

  // ─── Approval Policy handlers ────────────────────────

  private _openPolicyDialog(policy: ApprovalPolicy | null = null) {
    this.editingPolicy = policy;
    this.showPolicyDialog = true;
  }

  private _closePolicyDialog() {
    this.showPolicyDialog = false;
    this.editingPolicy = null;
  }

  private async _handlePolicySaved() {
    this._closePolicyDialog();
    await this.loadData();
  }

  private async _handleDeletePolicy(policy: ApprovalPolicy) {
    if (
      !confirm(
        `Delete approval policy "${policy.name}"? This cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await deleteApprovalPolicy(policy.id);
      if (this.filterPolicyId === policy.id) {
        this.filterPolicyId = null;
      }
      await this.loadData();
    } catch (err: any) {
      this.error = err.message || 'Failed to delete policy';
    }
  }

  // ─── Render helpers ──────────────────────────────────

  private _clearFilters() {
    this._setFilter('available');
    this.filterPolicyId = null;
  }

  private _renderTopSection() {
    const apiUrl = window.location.origin;
    const mcpUrl = `${apiUrl}/mcp`;
    const stats = this._getStats();

    // Helper: renders a single table cell with label left, number right, full-cell hover
    const statCell = (
      label: string | TemplateResult,
      value: number,
      filterKey: typeof this.activeFilter | '__none__',
      opts?: { muted?: boolean; tooltip?: string }
    ) => {
      const isActive =
        filterKey !== '__none__' && this.activeFilter === filterKey;
      const isMuted = opts?.muted || false;
      const onClick =
        filterKey === '__none__' || isMuted
          ? undefined
          : () => {
              this._setFilter(
                this.activeFilter === filterKey ? 'available' : filterKey
              );
              this.filterPolicyId = null;
            };

      const inner = html`
        <span
          class="summary-stat ${isActive ? 'active' : ''} ${isMuted
            ? 'muted'
            : ''}"
          @click=${onClick}
        >
          <span>${label}</span>
          <strong>${value}</strong>
        </span>
      `;

      return html`<td>
        ${opts?.tooltip
          ? html`<sl-tooltip content=${opts.tooltip}>${inner}</sl-tooltip>`
          : inner}
      </td>`;
    };

    return html`
      <div class="top-section">
        <!-- Left: Summary table -->
        <div class="summary-table-wrapper">
          <table class="summary-table">
            <tr>
              ${statCell('Total tools', stats.total, 'all')}
              ${statCell('Available', stats.available, 'available')}
              ${statCell('Unavailable', stats.unavailable, 'unavailable', {
                muted: stats.unavailable === 0,
                tooltip:
                  stats.unavailableReasons.length > 0
                    ? stats.unavailableReasons.join('; ')
                    : 'Some tools require trackers to be configured',
              })}
            </tr>
            <tr>
              <td></td>
              ${statCell('Enabled', stats.enabled, 'enabled')}
              ${statCell('Disabled', stats.disabled, 'disabled')}
            </tr>
            <tr>
              <td></td>
              ${statCell('Built-in', stats.builtin, 'builtin')}
              ${statCell('Proxied', stats.proxied, 'mcp')}
            </tr>
            <tr>
              <td></td>
              ${statCell('With rules', stats.withRules, 'has_rules')}
              ${statCell('No rules', stats.withoutRules, 'no_rules')}
            </tr>
            <tr>
              <td></td>
              ${statCell(
                'Require approval',
                stats.requireApproval,
                'require_approval'
              )}
              ${statCell('No approval', stats.noApproval, 'no_approval')}
            </tr>
          </table>
        </div>

        <!-- Right: MCP Server card -->
        <sl-card class="builtin-server-card">
          <div class="card-content">
            <div class="builtin-server-header">
              <h3 class="builtin-server-name">Preloop MCP Server</h3>
              <sl-badge variant="primary" size="small">Built-in</sl-badge>
            </div>
            <div class="info-row">
              <span class="info-label">URL:</span>
              <code class="info-value" title=${mcpUrl}>${mcpUrl}</code>
              <sl-tooltip content="Copy URL">
                <sl-icon-button
                  name="clipboard"
                  style="font-size: 1rem;"
                  @click=${() => {
                    navigator.clipboard.writeText(mcpUrl);
                    this.dispatchEvent(
                      new CustomEvent('show-toast', {
                        bubbles: true,
                        composed: true,
                        detail: { message: 'MCP URL copied!' },
                      })
                    );
                  }}
                ></sl-icon-button>
              </sl-tooltip>
            </div>
            <div class="info-row">
              <span class="info-label">Auth:</span>
              <div class="info-value-container">
                <code class="info-value">Bearer Token</code>
                <a href="/console/settings/api-keys" class="info-link">
                  Keys &rarr;
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
      </div>
    `;
  }

  private _renderFilterBar() {
    const filteredPolicy = this.filterPolicyId
      ? this.approvalPolicies.find((p) => p.id === this.filterPolicyId)
      : null;

    // Labels for the active filter tag display
    const filterLabels: Record<string, string> = {
      all: 'All tools',
      available: 'Available',
      enabled: 'Enabled',
      disabled: 'Disabled',
      unavailable: 'Unavailable',
      builtin: 'Built-in',
      mcp: 'Proxied',
      has_rules: 'With rules',
      no_rules: 'No rules',
      require_approval: 'Require approval',
      no_approval: 'No approval',
    };

    return html`
      <div class="filter-area">
        <div class="policy-row">${this._renderPolicyChipBar()}</div>
        <div class="filter-bar">
          <sl-input
            class="filter-search"
            size="small"
            placeholder="Filter tools..."
            clearable
            @sl-input=${(e: Event) =>
              (this.filterText = (e.target as any).value)}
          >
            <sl-icon slot="prefix" name="search"></sl-icon>
          </sl-input>

          <div class="active-filters">
            ${this.activeFilter !== 'all'
              ? html`<span class="active-filter-tag">
                  ${filterLabels[this.activeFilter] || this.activeFilter}
                  <sl-icon-button
                    name="x-lg"
                    @click=${() => this._setFilter('available')}
                  ></sl-icon-button>
                </span>`
              : ''}
            ${this.filterPolicyId && filteredPolicy
              ? html`<span class="active-filter-tag">
                  Policy: ${filteredPolicy.name}
                  <sl-icon-button
                    name="x-lg"
                    @click=${() => (this.filterPolicyId = null)}
                  ></sl-icon-button>
                </span>`
              : ''}
          </div>
        </div>
      </div>
    `;
  }

  private _renderPolicyChipBar() {
    const policies = this.approvalPolicies;

    return html`
      <div class="policy-chip-bar">
        <span class="policy-chip-bar-label">Approval Policies</span>
        ${policies.length === 0
          ? html`<span class="policy-chip-empty">None defined</span>`
          : policies.map((policy) => {
              const isActive = this.filterPolicyId === policy.id;
              const isAi = policy.approval_type === 'ai_driven';
              return html`
                <span
                  class="policy-chip ${isActive ? 'active' : ''}"
                  @click=${() => {
                    this.filterPolicyId = isActive ? null : policy.id;
                  }}
                >
                  <span class="policy-chip-name">${policy.name}</span>
                  <span class="policy-chip-type">${isAi ? 'AI' : 'Human'}</span>
                  <sl-icon-button
                    name="pencil"
                    label="Edit policy"
                    @click=${(e: Event) => {
                      e.stopPropagation();
                      this._openPolicyDialog(policy);
                    }}
                  ></sl-icon-button>
                  <sl-icon-button
                    name="x-lg"
                    label="Delete policy"
                    @click=${(e: Event) => {
                      e.stopPropagation();
                      this._handleDeletePolicy(policy);
                    }}
                  ></sl-icon-button>
                </span>
              `;
            })}
        <span
          class="policy-chip-add"
          @click=${() => this._openPolicyDialog(null)}
        >
          <sl-icon name="plus-lg" style="font-size: 0.7rem;"></sl-icon>
          New
        </span>
      </div>
    `;
  }

  private _renderToolGroup(group: ToolGroup) {
    const enabledCount = group.tools.filter((t) => t.is_enabled).length;
    const totalCount = group.tools.length;

    return html`
      <div class="tool-group">
        <div class="section-header" @click=${() => this._toggleGroup(group.id)}>
          <sl-icon
            class="section-icon ${!group.collapsed ? 'open' : ''}"
            name="chevron-right"
          ></sl-icon>
          <span class="section-title">${group.name}</span>
          <span class="section-meta">
            ${enabledCount}/${totalCount} enabled
          </span>
          ${group.type === 'mcp' && group.server
            ? html`
                <div
                  class="section-actions"
                  @click=${(e: Event) => e.stopPropagation()}
                >
                  <sl-tooltip content="Scan for new tools">
                    <sl-icon-button
                      name="arrow-clockwise"
                      @click=${() =>
                        this._handleScanMCPServer(group.server!.id)}
                    ></sl-icon-button>
                  </sl-tooltip>
                  <sl-tooltip content="Edit server">
                    <sl-icon-button
                      name="pencil"
                      @click=${() => {
                        this.editingMCPServer = group.server!;
                      }}
                    ></sl-icon-button>
                  </sl-tooltip>
                  <sl-tooltip content="Delete server">
                    <sl-icon-button
                      name="trash"
                      @click=${() => {
                        if (
                          confirm(
                            `Delete MCP server "${group.name}" and all its tools?`
                          )
                        ) {
                          this._handleDeleteMCPServer(group.server!.id);
                        }
                      }}
                    ></sl-icon-button>
                  </sl-tooltip>
                </div>
              `
            : ''}
          <div class="section-line"></div>
        </div>

        ${!group.collapsed
          ? html`
              <div class="tool-list">
                ${group.tools.length === 0
                  ? html`<div
                      style="padding: var(--sl-spacing-small); color: var(--sl-color-neutral-400); font-size: var(--sl-font-size-small);"
                    >
                      No tools${this.filterText ? ' matching filter' : ''}.
                      ${group.type === 'mcp'
                        ? html`<sl-button
                            size="small"
                            variant="text"
                            @click=${() => this._handleScanMCPServer(group.id)}
                            >Scan for tools</sl-button
                          >`
                        : ''}
                    </div>`
                  : repeat(
                      group.tools,
                      (tool) => this._getToolKey(tool),
                      (tool) => html`
                        <tool-list-item
                          .tool=${tool}
                          .accessRules=${tool.access_rules || []}
                          .policies=${this.approvalPolicies}
                          .features=${this.features}
                          ?expanded=${this.expandedTools.has(
                            this._getToolKey(tool)
                          )}
                          @toggle-expand=${this._handleToggleExpand}
                          @toggle-enabled=${this._handleToggleEnabled}
                          @save-rule=${this._handleSaveRule}
                          @delete-rule=${this._handleDeleteRule}
                          @policy-created=${this._handlePolicyCreated}
                          @reorder-rules=${this._handleReorderRules}
                          @tool-updated=${() => this.loadData()}
                        ></tool-list-item>
                      `
                    )}
              </div>
            `
          : ''}
      </div>
    `;
  }

  render() {
    const groups = this._getToolGroups();

    return html`
      <view-header headerText="Tools" width="extra-wide">
        <div slot="main-column">
          <sl-dropdown>
            <sl-button slot="trigger" size="small" variant="primary" caret>
              <sl-icon slot="prefix" name="plus-lg"></sl-icon>
              Add Source
            </sl-button>
            <sl-menu>
              <sl-menu-item @click=${() => (this.isAddingMCPServer = true)}>
                <sl-icon slot="prefix" name="hdd-network"></sl-icon>
                MCP Server
              </sl-menu-item>
              <sl-menu-item disabled>
                <sl-icon slot="prefix" name="globe"></sl-icon>
                HTTP Tool (coming soon)
              </sl-menu-item>
            </sl-menu>
          </sl-dropdown>

          <sl-tooltip content="Import configuration from YAML">
            <sl-button size="small" @click=${this._triggerImport}>
              <sl-icon slot="prefix" name="upload"></sl-icon>
              Import
            </sl-button>
          </sl-tooltip>

          <sl-tooltip content="Export full tool configuration as YAML">
            <sl-button
              size="small"
              ?loading=${this.isExporting}
              @click=${this._exportPolicies}
            >
              <sl-icon slot="prefix" name="download"></sl-icon>
              Export
            </sl-button>
          </sl-tooltip>
        </div>
      </view-header>

      <div class="column-layout extra-wide">
        <div class="main-column">
          ${this.isAddingMCPServer
            ? html`<mcp-server-form
                @server-added=${this._handleServerAdded}
                @close-modal=${this._closeServerForm}
              ></mcp-server-form>`
            : ''}
          ${this.editingMCPServer
            ? html`<mcp-server-form
                .server=${this.editingMCPServer}
                @server-updated=${this._handleServerUpdated}
                @close-modal=${this._closeServerForm}
              ></mcp-server-form>`
            : ''}
          ${this.error
            ? html`<sl-alert
                variant="danger"
                open
                closable
                @sl-after-hide=${() => (this.error = null)}
              >
                <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
                <strong>Error:</strong> ${this.error}
              </sl-alert>`
            : ''}
          ${this.loading
            ? html`<div class="loading-indicator">
                <sl-spinner></sl-spinner>
              </div>`
            : html` ${this._renderTopSection()}
                <div class="tool-groups">
                  ${this._renderFilterBar()}
                  ${groups.length === 0
                    ? html`<div class="empty-state">
                        <sl-icon
                          name="tools"
                          style="font-size: 2rem; color: var(--sl-color-neutral-400);"
                        ></sl-icon>
                        <p>No tools found. Add an MCP server to get started.</p>
                      </div>`
                    : groups.map((group) => this._renderToolGroup(group))}
                </div>`}
        </div>
        <div class="side-column"></div>
      </div>

      <approval-policy-dialog
        ?open=${this.showPolicyDialog}
        .policy=${this.editingPolicy}
        .existingPolicies=${this.approvalPolicies}
        .features=${this.features}
        @close=${this._closePolicyDialog}
        @saved=${this._handlePolicySaved}
      ></approval-policy-dialog>
    `;
  }
}
