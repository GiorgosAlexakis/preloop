import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/switch/switch.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/tooltip/tooltip.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/dropdown/dropdown.js';
import '@shoelace-style/shoelace/dist/components/menu/menu.js';
import '@shoelace-style/shoelace/dist/components/menu-item/menu-item.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/radio-group/radio-group.js';
import '@shoelace-style/shoelace/dist/components/radio/radio.js';
import './tool-rule-editor';
import type { Tool, ApprovalPolicy } from './tool-card';
import type { AccessRule } from '../api';

export interface AccessRuleSummary {
  id: string;
  action: string;
  condition_expression: string | null;
  condition_type: string;
  priority: number;
  description: string | null;
  is_enabled: boolean;
  approval_policy_id: string | null;
}

@customElement('tool-list-item')
export class ToolListItem extends LitElement {
  @property({ type: Object }) tool!: Tool;
  @property({ type: Array }) accessRules: AccessRuleSummary[] = [];
  @property({ type: Array }) policies: ApprovalPolicy[] = [];
  @property({ type: Object }) features: { [key: string]: boolean | string[] } =
    {};
  @property({ type: Boolean }) expanded = false;

  @state() private _showRuleEditor = false;
  @state() private _editingRule: AccessRule | null = null;

  @state() private _showJustificationDialog = false;
  @state() private _justificationMode: string = 'disabled';

  @state() private _dragIndex: number | null = null;
  @state() private _dragOverIndex: number | null = null;

  static styles = css`
    :host {
      display: block;
    }

    .tool-row {
      border-radius: var(--sl-border-radius-medium);
      overflow: hidden;
      transition: background 0.15s ease;
    }

    .tool-row.expanded {
      background: var(--sl-color-neutral-50);
    }

    .tool-row.disabled {
      opacity: 0.65;
    }

    .tool-header {
      display: flex;
      align-items: center;
      padding: var(--sl-spacing-2x-small) var(--sl-spacing-medium);
      cursor: pointer;
      user-select: none;
      gap: var(--sl-spacing-small);
      min-height: 36px;
    }

    .tool-header:hover {
      background: var(--sl-color-neutral-50);
    }

    .expand-icon {
      color: var(--sl-color-neutral-500);
      transition: transform 0.2s ease;
      flex-shrink: 0;
    }

    .expand-icon.open {
      transform: rotate(90deg);
    }

    .tool-name {
      font-weight: var(--sl-font-weight-semibold);
      font-size: var(--sl-font-size-small);
      color: var(--sl-color-neutral-900);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .tool-description {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-500);
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .tool-badges {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-2x-small);
      flex-shrink: 0;
    }

    .rule-summary {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-2x-small);
      flex-shrink: 0;
      font-size: var(--sl-font-size-x-small);
    }

    .rule-summary .rule-count {
      display: inline-flex;
      align-items: center;
      gap: 3px;
      padding: 2px 8px;
      border-radius: var(--sl-border-radius-pill);
      font-weight: 500;
    }

    .rule-count.deny {
      background: var(--sl-color-danger-100);
      color: var(--sl-color-danger-700);
    }

    .rule-count.approval {
      background: var(--sl-color-primary-100);
      color: var(--sl-color-primary-700);
    }

    .rule-count.allow {
      background: var(--sl-color-success-100);
      color: var(--sl-color-success-700);
    }

    .no-rules {
      color: var(--sl-color-neutral-400);
      font-size: var(--sl-font-size-x-small);
    }

    .tool-toggle {
      flex-shrink: 0;
      margin-top: -3px;
    }

    /* Expanded content */
    .tool-content {
      padding: var(--sl-spacing-small) var(--sl-spacing-medium)
        var(--sl-spacing-medium);
    }

    .rules-list {
      display: flex;
      flex-direction: column;
      gap: 2px;
    }

    .rule-item {
      display: flex;
      align-items: flex-start;
      gap: var(--sl-spacing-small);
      padding: var(--sl-spacing-x-small) var(--sl-spacing-small);
      border-radius: var(--sl-border-radius-small);
      font-size: var(--sl-font-size-small);
      transition: background 0.1s ease;
    }

    .rule-item:hover {
      background: var(--sl-color-neutral-100);
    }

    .rule-item.disabled-rule {
      opacity: 0.5;
    }

    /* Drag-and-drop styles */
    .rule-item[draggable='true'] {
      cursor: grab;
    }

    .rule-item.dragging {
      opacity: 0.4;
      cursor: grabbing;
    }

    .rule-item.drag-over-top {
      border-top: 2px solid var(--sl-color-primary-500);
      padding-top: calc(var(--sl-spacing-x-small) - 2px);
    }

    .rule-item.drag-over-bottom {
      border-bottom: 2px solid var(--sl-color-primary-500);
      padding-bottom: calc(var(--sl-spacing-x-small) - 2px);
    }

    .drag-handle {
      color: var(--sl-color-neutral-400);
      cursor: grab;
      flex-shrink: 0;
      font-size: 0.85rem;
      padding-top: 2px;
    }

    .drag-handle:hover {
      color: var(--sl-color-neutral-600);
    }

    .rule-priority {
      font-size: var(--sl-font-size-x-small);
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-neutral-500);
      min-width: 20px;
      text-align: center;
      padding-top: 2px;
    }

    .rule-action-icon {
      flex-shrink: 0;
      font-size: 1rem;
      padding-top: 1px;
    }

    .rule-action-icon.deny {
      color: var(--sl-color-danger-600);
    }

    .rule-action-icon.approval {
      color: var(--sl-color-primary-600);
    }

    .rule-action-icon.allow {
      color: var(--sl-color-success-600);
    }

    .rule-details {
      flex: 1;
      min-width: 0;
    }

    .rule-action-label {
      font-weight: var(--sl-font-weight-semibold);
      font-size: var(--sl-font-size-small);
    }

    .rule-action-label.deny {
      color: var(--sl-color-danger-700);
    }

    .rule-action-label.approval {
      color: var(--sl-color-primary-700);
    }

    .rule-action-label.allow {
      color: var(--sl-color-success-700);
    }

    .rule-condition {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
      font-family: var(--sl-font-mono);
      margin-top: 2px;
      word-break: break-all;
    }

    .rule-description {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-500);
      font-style: italic;
      margin-top: 2px;
    }

    .rule-actions {
      display: flex;
      gap: var(--sl-spacing-2x-small);
      flex-shrink: 0;
    }

    .rules-footer {
      display: flex;
      justify-content: flex-start;
      gap: var(--sl-spacing-small);
      margin-top: var(--sl-spacing-small);
    }

    .empty-rules {
      text-align: center;
      padding: var(--sl-spacing-medium);
      color: var(--sl-color-neutral-500);
      font-size: var(--sl-font-size-small);
    }

    .unsupported-overlay {
      color: var(--sl-color-neutral-500);
      font-size: var(--sl-font-size-x-small);
      font-style: italic;
    }
  `;

  private _getRuleSummary() {
    const rules = this.accessRules.filter((r) => r.is_enabled);
    const deny = rules.filter((r) => r.action === 'deny').length;
    const approval = rules.filter(
      (r) => r.action === 'require_approval'
    ).length;
    const allow = rules.filter((r) => r.action === 'allow').length;
    return { deny, approval, allow, total: rules.length };
  }

  private _getActionIconName(action: string): string {
    switch (action) {
      case 'deny':
        return 'x-octagon-fill';
      case 'require_approval':
        return 'shield-lock-fill';
      case 'allow':
        return 'check-circle-fill';
      default:
        return 'question-circle';
    }
  }

  private _getActionColorClass(action: string): string {
    switch (action) {
      case 'deny':
        return 'deny';
      case 'require_approval':
        return 'approval';
      case 'allow':
        return 'allow';
      default:
        return '';
    }
  }

  private _getActionLabel(action: string): string {
    switch (action) {
      case 'deny':
        return 'DENY';
      case 'require_approval':
        return 'REQUIRE APPROVAL';
      case 'allow':
        return 'ALLOW';
      default:
        return action.toUpperCase();
    }
  }

  private _toggleExpanded() {
    this.dispatchEvent(
      new CustomEvent('toggle-expand', {
        detail: { tool: this.tool },
        bubbles: true,
        composed: true,
      })
    );
  }

  private _handleToggleEnabled(e: Event) {
    e.stopPropagation();
    this.dispatchEvent(
      new CustomEvent('toggle-enabled', {
        detail: { tool: this.tool },
        bubbles: true,
        composed: true,
      })
    );
  }

  private _openRuleEditor(rule: AccessRuleSummary | null = null) {
    this._editingRule = rule as AccessRule | null;
    this._showRuleEditor = true;
  }

  private _closeRuleEditor() {
    this._showRuleEditor = false;
    this._editingRule = null;
  }

  private _handleSaveRule(e: CustomEvent) {
    const { rule, formData } = e.detail;
    this.dispatchEvent(
      new CustomEvent('save-rule', {
        detail: {
          tool: this.tool,
          existingRule: rule,
          formData,
        },
        bubbles: true,
        composed: true,
      })
    );
    this._closeRuleEditor();
  }

  private _handlePolicyCreated() {
    // Bubble up to tools-view to refresh the policies list
    this.dispatchEvent(
      new CustomEvent('policy-created', {
        bubbles: true,
        composed: true,
      })
    );
  }

  private _handleDeleteRule(rule: AccessRuleSummary) {
    this.dispatchEvent(
      new CustomEvent('delete-rule', {
        detail: {
          tool: this.tool,
          rule,
        },
        bubbles: true,
        composed: true,
      })
    );
  }

  private _renderRuleSummaryBadges() {
    const summary = this._getRuleSummary();

    if (summary.total === 0) {
      if (this.tool.is_enabled) {
        return html`<span class="no-rules">No rules (allow all)</span>`;
      }
      return html`<span class="no-rules">No rules</span>`;
    }

    return html`
      ${summary.deny > 0
        ? html`<span class="rule-count deny"
            ><sl-icon name="x-octagon-fill" style="font-size: 0.8em;"></sl-icon>
            ${summary.deny} deny</span
          >`
        : ''}
      ${summary.approval > 0
        ? html`<span class="rule-count approval"
            ><sl-icon
              name="shield-lock-fill"
              style="font-size: 0.8em;"
            ></sl-icon>
            ${summary.approval} approval</span
          >`
        : ''}
      ${summary.allow > 0
        ? html`<span class="rule-count allow"
            ><sl-icon
              name="check-circle-fill"
              style="font-size: 0.8em;"
            ></sl-icon>
            ${summary.allow} allow</span
          >`
        : ''}
    `;
  }

  private _handleDragStart(index: number, e: DragEvent) {
    this._dragIndex = index;
    if (e.dataTransfer) {
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(index));
    }
  }

  private _handleDragOver(index: number, e: DragEvent) {
    e.preventDefault();
    if (e.dataTransfer) {
      e.dataTransfer.dropEffect = 'move';
    }
    this._dragOverIndex = index;
  }

  private _handleDragLeave() {
    this._dragOverIndex = null;
  }

  private _handleDrop(dropIndex: number, e: DragEvent) {
    e.preventDefault();
    const fromIndex = this._dragIndex;
    this._dragIndex = null;
    this._dragOverIndex = null;

    if (fromIndex === null || fromIndex === dropIndex) return;

    // Reorder the rules and dispatch event
    const sortedRules = [...this.accessRules].sort(
      (a, b) => a.priority - b.priority
    );
    const [moved] = sortedRules.splice(fromIndex, 1);
    sortedRules.splice(dropIndex, 0, moved);

    // Dispatch reorder event with new priorities
    this.dispatchEvent(
      new CustomEvent('reorder-rules', {
        detail: {
          tool: this.tool,
          reorderedRules: sortedRules.map((rule, i) => ({
            id: rule.id,
            priority: i,
          })),
        },
        bubbles: true,
        composed: true,
      })
    );
  }

  private _handleDragEnd() {
    this._dragIndex = null;
    this._dragOverIndex = null;
  }

  private _openJustificationDialog() {
    this._justificationMode = this.tool.justification_mode || 'disabled';
    this._showJustificationDialog = true;
  }

  private async _saveJustificationMode() {
    try {
      const { updateToolConfiguration, createToolConfiguration } =
        await import('../api');
      let configId = this.tool.config_id;
      if (!configId) {
        const config = await createToolConfiguration({
          tool_name: this.tool.name,
          tool_source: this.tool.source || 'builtin',
          is_enabled: this.tool.is_enabled !== false,
          justification_mode:
            this._justificationMode === 'disabled'
              ? null
              : this._justificationMode,
        });
        configId = config.id;
      } else {
        await updateToolConfiguration(configId, {
          justification_mode:
            this._justificationMode === 'disabled'
              ? null
              : this._justificationMode,
        });
      }
      this._showJustificationDialog = false;
      this.dispatchEvent(
        new CustomEvent('tool-updated', { bubbles: true, composed: true })
      );
    } catch (error) {
      console.error('Failed to save justification mode:', error);
    }
  }

  private _renderRuleItem(rule: AccessRuleSummary, index: number) {
    const policy = rule.approval_policy_id
      ? this.policies.find((p) => p.id === rule.approval_policy_id)
      : this.tool.approval_policy_id
        ? this.policies.find((p) => p.id === this.tool.approval_policy_id)
        : null;

    const colorClass = this._getActionColorClass(rule.action);
    const isDragging = this._dragIndex === index;
    const isDragOver = this._dragOverIndex === index;
    const dragPosition =
      isDragOver && this._dragIndex !== null
        ? index > this._dragIndex
          ? 'drag-over-bottom'
          : 'drag-over-top'
        : '';

    return html`
      <div
        class="rule-item ${!rule.is_enabled ? 'disabled-rule' : ''} ${isDragging
          ? 'dragging'
          : ''} ${dragPosition}"
        draggable="true"
        @dragstart=${(e: DragEvent) => this._handleDragStart(index, e)}
        @dragover=${(e: DragEvent) => this._handleDragOver(index, e)}
        @dragleave=${() => this._handleDragLeave()}
        @drop=${(e: DragEvent) => this._handleDrop(index, e)}
        @dragend=${() => this._handleDragEnd()}
      >
        <sl-icon class="drag-handle" name="grip-vertical"></sl-icon>
        <span class="rule-priority">${index + 1}.</span>
        <sl-icon
          class="rule-action-icon ${colorClass}"
          name=${this._getActionIconName(rule.action)}
        ></sl-icon>
        <div class="rule-details">
          <span class="rule-action-label ${colorClass}">
            ${this._getActionLabel(rule.action)}${rule.action ===
              'require_approval' && policy
              ? html` <span
                  style="font-weight: normal; font-size: var(--sl-font-size-x-small);"
                  >(${policy.name})</span
                >`
              : ''}
          </span>
          ${rule.condition_expression
            ? html`<div class="rule-condition">
                when ${rule.condition_expression}
              </div>`
            : html`<div class="rule-condition">(always)</div>`}
          ${rule.description
            ? html`<div class="rule-description">
                ${rule.action === 'deny' ? '\u2192 ' : ''}${rule.description}
              </div>`
            : ''}
        </div>
        <div class="rule-actions">
          <sl-tooltip content="Edit rule">
            <sl-icon-button
              name="pencil"
              @click=${() => this._openRuleEditor(rule)}
            ></sl-icon-button>
          </sl-tooltip>
          <sl-tooltip content="Delete rule">
            <sl-icon-button
              name="trash"
              @click=${() => this._handleDeleteRule(rule)}
            ></sl-icon-button>
          </sl-tooltip>
        </div>
      </div>
    `;
  }

  private _renderExpandedContent() {
    const sortedRules = [...this.accessRules].sort(
      (a, b) => a.priority - b.priority
    );

    return html`
      <div class="tool-content">
        ${this.tool.description
          ? html`<div
              style="font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-600); margin-bottom: var(--sl-spacing-small);"
            >
              ${this.tool.description}
            </div>`
          : ''}

        <div class="rules-list">
          ${sortedRules.length === 0
            ? html`<div class="empty-rules">
                No access rules configured. All calls to this tool are
                ${this.tool.is_enabled ? 'allowed' : 'blocked (tool disabled)'}.
              </div>`
            : sortedRules.map((rule, i) => this._renderRuleItem(rule, i))}
        </div>

        <div class="rules-footer">
          <sl-button
            size="small"
            variant="default"
            @click=${() => this._openRuleEditor(null)}
          >
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add Rule
          </sl-button>
        </div>
      </div>
    `;
  }

  render() {
    const isUnsupported = this.tool.is_supported === false;

    return html`
      <div
        class="tool-row ${this.expanded ? 'expanded' : ''} ${!this.tool
          .is_enabled
          ? 'disabled'
          : ''}"
      >
        <div class="tool-header" @click=${this._toggleExpanded}>
          <sl-icon
            class="expand-icon ${this.expanded ? 'open' : ''}"
            name="chevron-right"
          ></sl-icon>

          <span class="tool-name">${this.tool.name}</span>

          <div class="tool-badges">
            ${isUnsupported
              ? html`<sl-tooltip
                  content=${this.tool.unsupported_reason ||
                  'This tool is currently unavailable'}
                >
                  <sl-badge variant="neutral" pill>Unavailable</sl-badge>
                </sl-tooltip>`
              : ''}
          </div>

          <span class="tool-description">${this.tool.description}</span>

          <div class="rule-summary">${this._renderRuleSummaryBadges()}</div>

          <div class="tool-toggle" @click=${(e: Event) => e.stopPropagation()}>
            <sl-switch
              size="small"
              ?checked=${this.tool.is_enabled}
              ?disabled=${isUnsupported}
              @sl-change=${this._handleToggleEnabled}
            ></sl-switch>
          </div>

          <div @click=${(e: Event) => e.stopPropagation()}>
            <sl-dropdown>
              <sl-icon-button
                slot="trigger"
                name="three-dots-vertical"
                label="Tool settings"
                style="font-size: 1.2rem;"
              ></sl-icon-button>
              <sl-menu>
                <sl-menu-item @click=${() => this._openJustificationDialog()}>
                  <sl-icon slot="prefix" name="shield-shaded"></sl-icon>
                  Justification settings
                </sl-menu-item>
              </sl-menu>
            </sl-dropdown>
          </div>
        </div>

        ${this.expanded ? this._renderExpandedContent() : ''}
      </div>

      <!-- Dialog rendered outside .tool-row to avoid inheriting opacity from disabled state -->
      <tool-rule-editor
        ?open=${this._showRuleEditor}
        .rule=${this._editingRule}
        .toolName=${this.tool.name}
        .policies=${this.policies}
        .features=${this.features}
        .toolSchema=${this.tool.schema}
        @save-rule=${this._handleSaveRule}
        @policy-created=${this._handlePolicyCreated}
        @close=${this._closeRuleEditor}
      ></tool-rule-editor>

      <sl-dialog
        label="Justification Settings"
        ?open=${this._showJustificationDialog}
        @sl-after-hide=${() => {
          this._showJustificationDialog = false;
        }}
      >
        <p style="margin-top: 0; color: var(--sl-color-neutral-600);">
          Configure whether agents must provide justification when calling this
          tool. Justification is used for auditing and approval workflows.
        </p>
        <sl-radio-group
          label="Justification requirement"
          value=${this._justificationMode}
          @sl-change=${(e: Event) => {
            this._justificationMode = (e.target as any).value;
          }}
        >
          <sl-radio value="disabled">Disabled</sl-radio>
          <sl-radio value="optional">Optional</sl-radio>
          <sl-radio value="required">Required</sl-radio>
        </sl-radio-group>
        <div slot="footer">
          <sl-button
            variant="primary"
            @click=${() => this._saveJustificationMode()}
          >
            Save
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }
}
