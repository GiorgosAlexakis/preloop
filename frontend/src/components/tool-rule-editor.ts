import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/icon-button/icon-button.js';
import '@shoelace-style/shoelace/dist/components/divider/divider.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/badge/badge.js';
import '@shoelace-style/shoelace/dist/components/switch/switch.js';
import type { ApprovalPolicy } from './tool-card';
import type { AccessRule } from '../api';

export interface RuleFormData {
  action: 'allow' | 'deny' | 'require_approval';
  condition_expression: string | null;
  condition_type: 'simple' | 'cel';
  description: string | null;
  is_enabled: boolean;
  approval_policy_id: string | null;
}

interface SimpleCondition {
  field: string;
  operator: string;
  value: string;
}

@customElement('tool-rule-editor')
export class ToolRuleEditor extends LitElement {
  @property({ type: Boolean }) open = false;
  @property({ type: Object }) rule: AccessRule | null = null;
  @property({ type: String }) toolName = '';
  @property({ type: Array }) policies: ApprovalPolicy[] = [];
  @property({ type: Object }) features: { [key: string]: boolean } = {};
  @property({ type: Object }) toolSchema: any = null;

  @state() private _action: 'allow' | 'deny' | 'require_approval' = 'deny';
  @state() private _conditionExpression = '';
  @state() private _conditionType: 'simple' | 'cel' = 'cel';
  @state() private _description = '';
  @state() private _isEnabled = true;
  @state() private _saving = false;
  @state() private _error: string | null = null;

  // Simple condition builder state (OSS: single condition)
  @state() private _simpleField = '';
  @state() private _simpleOperator = '==';
  @state() private _simpleValue = '';

  // Advanced simple conditions (EE: multiple conditions with AND/OR)
  @state() private _conditions: SimpleCondition[] = [
    { field: '', operator: '==', value: '' },
  ];
  @state() private _conditionOperator: 'AND' | 'OR' = 'AND';
  @state() private _useCelEditor = false;

  // Approval policy state
  @state() private _approvalPolicyId: string | null = null;
  @state() private _approvalMode: 'human' | 'ai' = 'human';
  @state() private _showNewPolicy = false;
  // Inline AI policy fields
  @state() private _aiModel = '';
  @state() private _aiGuidelines = '';
  @state() private _aiConfidenceThreshold = 0.8;
  @state() private _aiFallbackBehavior: 'approve' | 'deny' | 'escalate' =
    'escalate';
  @state() private _aiEscalationPolicyId: string | null = null;

  private get _isEditing(): boolean {
    return this.rule !== null;
  }

  private get _hasAdvancedConditions(): boolean {
    return this.features['advanced_approvals'] === true;
  }

  static styles = css`
    :host {
      display: block;
    }

    /* Ensure dialog panel is fully opaque */
    sl-dialog {
      --sl-panel-background-color: var(--sl-color-neutral-0);
      --sl-overlay-background-color: hsl(240 3.8% 46.1% / 33%);
    }

    sl-dialog::part(panel) {
      background-color: var(--sl-color-neutral-0, #fff);
      opacity: 1;
    }

    sl-dialog::part(overlay) {
      background-color: hsl(240 3.8% 46.1% / 33%);
    }

    sl-dialog::part(body) {
      background-color: var(--sl-color-neutral-0, #fff);
    }

    .form-group {
      margin-bottom: var(--sl-spacing-medium);
    }

    .form-group label {
      display: block;
      font-size: var(--sl-font-size-small);
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-neutral-700);
      margin-bottom: var(--sl-spacing-x-small);
    }

    .form-group .hint {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-500);
      margin-top: var(--sl-spacing-2x-small);
    }

    .action-cards {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: var(--sl-spacing-small);
    }

    .action-card {
      border: 2px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
      background: var(--sl-color-neutral-0);
    }

    .action-card:hover {
      border-color: var(--sl-color-neutral-400);
    }

    .action-card.selected {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
    }

    .action-card.deny.selected {
      border-color: var(--sl-color-danger-600);
      background: var(--sl-color-danger-50);
    }

    .action-card.approval.selected {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
    }

    .action-card .action-icon {
      font-size: 1.5rem;
      margin-bottom: var(--sl-spacing-x-small);
    }

    .action-card .action-label {
      font-weight: var(--sl-font-weight-semibold);
      font-size: var(--sl-font-size-small);
    }

    .action-card .action-desc {
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-500);
      margin-top: var(--sl-spacing-2x-small);
    }

    .condition-section {
      background: var(--sl-color-neutral-50);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
    }

    .simple-condition {
      display: grid;
      grid-template-columns: minmax(140px, 3fr) minmax(100px, 2fr) minmax(
          80px,
          2fr
        );
      gap: var(--sl-spacing-small);
      align-items: end;
    }

    /* Make parameter select dropdown wider than the trigger */
    .param-select::part(listbox) {
      min-width: 220px;
    }

    /* Multi-condition row with delete button */
    .condition-row {
      display: flex;
      align-items: end;
      gap: var(--sl-spacing-x-small);
    }

    .condition-row .simple-condition {
      flex: 1;
    }

    .condition-row sl-icon-button {
      margin-bottom: 4px;
    }

    .condition-join {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-small);
      margin: var(--sl-spacing-x-small) 0;
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
    }

    .condition-join .join-line {
      flex: 1;
      height: 1px;
      background: var(--sl-color-neutral-300);
    }

    .join-toggle {
      cursor: pointer;
      padding: 2px 8px;
      border-radius: var(--sl-border-radius-pill);
      background: var(--sl-color-neutral-200);
      font-weight: var(--sl-font-weight-semibold);
      user-select: none;
      transition: background 0.1s ease;
    }

    .join-toggle:hover {
      background: var(--sl-color-neutral-300);
    }

    .condition-actions {
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-small);
      margin-top: var(--sl-spacing-small);
    }

    .cel-toggle {
      margin-left: auto;
      display: flex;
      align-items: center;
      gap: var(--sl-spacing-x-small);
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
    }

    .dialog-footer {
      display: flex;
      justify-content: flex-end;
      gap: var(--sl-spacing-small);
      margin-top: var(--sl-spacing-medium);
    }

    .cel-help {
      margin-top: var(--sl-spacing-small);
      font-size: var(--sl-font-size-x-small);
      color: var(--sl-color-neutral-600);
    }

    .cel-help code {
      background: var(--sl-color-neutral-100);
      padding: 0.1em 0.3em;
      border-radius: 3px;
      font-size: 0.9em;
    }

    .args-list {
      margin-top: var(--sl-spacing-x-small);
      display: flex;
      flex-wrap: wrap;
      gap: var(--sl-spacing-2x-small);
    }

    /* Approval policy section */
    .approval-section {
      background: var(--sl-color-neutral-50);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-medium);
    }

    .approval-mode-cards {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--sl-spacing-small);
      margin-bottom: var(--sl-spacing-medium);
    }

    .approval-mode-card {
      border: 2px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      padding: var(--sl-spacing-small) var(--sl-spacing-medium);
      cursor: pointer;
      text-align: center;
      transition: all 0.15s ease;
      background: var(--sl-color-neutral-0);
    }

    .approval-mode-card:hover {
      border-color: var(--sl-color-neutral-400);
    }

    .approval-mode-card.selected {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
    }

    .approval-mode-card .mode-icon {
      font-size: 1.2rem;
      margin-bottom: 2px;
    }

    .approval-mode-card .mode-label {
      font-weight: var(--sl-font-weight-semibold);
      font-size: var(--sl-font-size-small);
    }

    .ai-config {
      margin-top: var(--sl-spacing-medium);
      padding: var(--sl-spacing-medium);
      background: var(--sl-color-neutral-0);
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
    }

    .ai-config-title {
      font-size: var(--sl-font-size-small);
      font-weight: var(--sl-font-weight-semibold);
      color: var(--sl-color-neutral-700);
      margin-bottom: var(--sl-spacing-small);
    }

    .ai-config-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: var(--sl-spacing-small);
    }

    .ai-config-full {
      grid-column: 1 / -1;
    }

    .policy-select-row {
      display: flex;
      align-items: end;
      gap: var(--sl-spacing-small);
    }

    .policy-select-row sl-select {
      flex: 1;
    }
  `;

  updated(changedProperties: Map<string, any>) {
    if (changedProperties.has('open') && this.open) {
      this._initForm();
    }
  }

  private _initForm() {
    if (this.rule) {
      this._action = this.rule.action as 'allow' | 'deny' | 'require_approval';
      this._conditionExpression = this.rule.condition_expression || '';
      this._conditionType = this.rule.condition_type as 'simple' | 'cel';
      this._description = this.rule.description || '';
      this._isEnabled = this.rule.is_enabled;

      // Approval policy
      this._approvalPolicyId = this.rule.approval_policy_id || null;
      if (this._approvalPolicyId) {
        const policy = this.policies.find(
          (p) => p.id === this._approvalPolicyId
        );
        this._approvalMode =
          policy?.approval_type === 'ai_driven' ? 'ai' : 'human';
      } else {
        this._approvalMode = 'human';
      }

      // Try to parse existing CEL expression into simple conditions
      if (this._hasAdvancedConditions && this._conditionExpression) {
        const parsed = this._parseCelExpression(this._conditionExpression);
        if (parsed) {
          this._conditions = parsed.conditions;
          this._conditionOperator = parsed.operator;
          this._useCelEditor = false;
        } else {
          // Expression is too complex for simple editor, fall back to CEL
          this._conditions = [{ field: '', operator: '==', value: '' }];
          this._conditionOperator = 'AND';
          this._useCelEditor = true;
        }
      } else if (!this._hasAdvancedConditions && this._conditionExpression) {
        // OSS mode: try to parse single condition
        const parsed = this._parseSingleCondition(this._conditionExpression);
        if (parsed) {
          this._simpleField = parsed.field;
          this._simpleOperator = parsed.operator;
          this._simpleValue = parsed.value;
        }
        this._useCelEditor = false;
      } else {
        this._conditions = [{ field: '', operator: '==', value: '' }];
        this._conditionOperator = 'AND';
        this._useCelEditor = false;
      }
    } else {
      this._action = 'deny';
      this._conditionExpression = '';
      this._conditionType = this._hasAdvancedConditions ? 'cel' : 'simple';
      this._description = '';
      this._isEnabled = true;
      this._simpleField = '';
      this._simpleOperator = '==';
      this._simpleValue = '';
      this._conditions = [{ field: '', operator: '==', value: '' }];
      this._conditionOperator = 'AND';
      this._useCelEditor = false;
      this._approvalPolicyId = null;
      this._approvalMode = 'human';
    }
    this._showNewPolicy = false;
    this._aiModel = '';
    this._aiGuidelines = '';
    this._aiConfidenceThreshold = 0.8;
    this._aiFallbackBehavior = 'escalate';
    this._aiEscalationPolicyId = null;
    this._error = null;
    this._saving = false;
  }

  /**
   * Parse a single CEL condition like `args.field == "value"` or `args.field > 100`
   */
  private _parseSingleCondition(expr: string): SimpleCondition | null {
    // Match: args.FIELD OP VALUE
    const match = expr
      .trim()
      .match(
        /^args\.(\w+)\s*(==|!=|>=|<=|>|<)\s*(?:"([^"]*)"|(\d+(?:\.\d+)?))$/
      );
    if (match) {
      return {
        field: match[1],
        operator: match[2],
        value: match[3] ?? match[4],
      };
    }

    // Match: args.FIELD.contains("value")
    const containsMatch = expr
      .trim()
      .match(/^args\.(\w+)\.contains\("([^"]*)"\)$/);
    if (containsMatch) {
      return {
        field: containsMatch[1],
        operator: 'contains',
        value: containsMatch[2],
      };
    }

    // Match: args.FIELD.startsWith("value")
    const startsMatch = expr
      .trim()
      .match(/^args\.(\w+)\.startsWith\("([^"]*)"\)$/);
    if (startsMatch) {
      return {
        field: startsMatch[1],
        operator: 'starts_with',
        value: startsMatch[2],
      };
    }

    // Match: args.FIELD.endsWith("value")
    const endsMatch = expr.trim().match(/^args\.(\w+)\.endsWith\("([^"]*)"\)$/);
    if (endsMatch) {
      return {
        field: endsMatch[1],
        operator: 'ends_with',
        value: endsMatch[2],
      };
    }

    return null;
  }

  /**
   * Parse a CEL expression into multiple simple conditions joined by && or ||
   */
  private _parseCelExpression(
    expr: string
  ): { conditions: SimpleCondition[]; operator: 'AND' | 'OR' } | null {
    // Try splitting by && first, then ||
    for (const [separator, op] of [
      [' && ', 'AND'],
      [' || ', 'OR'],
    ] as const) {
      const parts = expr.split(separator);
      const conditions: SimpleCondition[] = [];
      let allParsed = true;

      for (const part of parts) {
        const parsed = this._parseSingleCondition(part.trim());
        if (parsed) {
          conditions.push(parsed);
        } else {
          allParsed = false;
          break;
        }
      }

      if (allParsed && conditions.length > 0) {
        return { conditions, operator: op };
      }
    }

    // Single condition (no separator)
    const single = this._parseSingleCondition(expr.trim());
    if (single) {
      return { conditions: [single], operator: 'AND' };
    }

    return null;
  }

  private _getToolArguments(): string[] {
    if (!this.toolSchema?.properties) return [];
    return Object.keys(this.toolSchema.properties);
  }

  private _buildSimpleExpression(): string {
    if (!this._simpleField || !this._simpleValue) return '';
    return this._buildConditionExpression(
      this._simpleField,
      this._simpleOperator,
      this._simpleValue
    );
  }

  private _buildConditionExpression(
    field: string,
    operator: string,
    value: string
  ): string {
    if (!field || !value) return '';

    const fieldRef = `args.${field}`;
    const numVal = Number(value);
    const isNumber = !isNaN(numVal) && value.trim() !== '';

    switch (operator) {
      case '==':
        return isNumber
          ? `${fieldRef} == ${numVal}`
          : `${fieldRef} == "${value}"`;
      case '!=':
        return isNumber
          ? `${fieldRef} != ${numVal}`
          : `${fieldRef} != "${value}"`;
      case '>':
        return `${fieldRef} > ${isNumber ? numVal : `"${value}"`}`;
      case '>=':
        return `${fieldRef} >= ${isNumber ? numVal : `"${value}"`}`;
      case '<':
        return `${fieldRef} < ${isNumber ? numVal : `"${value}"`}`;
      case '<=':
        return `${fieldRef} <= ${isNumber ? numVal : `"${value}"`}`;
      case 'contains':
        return `${fieldRef}.contains("${value}")`;
      case 'starts_with':
        return `${fieldRef}.startsWith("${value}")`;
      case 'ends_with':
        return `${fieldRef}.endsWith("${value}")`;
      default:
        return `${fieldRef} ${operator} "${value}"`;
    }
  }

  private _buildMultiConditionExpression(): string {
    const parts = this._conditions
      .map((c) => this._buildConditionExpression(c.field, c.operator, c.value))
      .filter((p) => p.length > 0);
    if (parts.length === 0) return '';
    if (parts.length === 1) return parts[0];
    const joiner = this._conditionOperator === 'AND' ? ' && ' : ' || ';
    return parts.join(joiner);
  }

  private _addCondition() {
    this._conditions = [
      ...this._conditions,
      { field: '', operator: '==', value: '' },
    ];
  }

  private _removeCondition(index: number) {
    if (this._conditions.length <= 1) return;
    this._conditions = this._conditions.filter((_, i) => i !== index);
  }

  private _updateCondition(
    index: number,
    key: keyof SimpleCondition,
    value: string
  ) {
    this._conditions = this._conditions.map((c, i) =>
      i === index ? { ...c, [key]: value } : c
    );
  }

  private _toggleJoinOperator() {
    this._conditionOperator = this._conditionOperator === 'AND' ? 'OR' : 'AND';
  }

  private _handleSave() {
    let conditionExpr: string | null = null;

    if (this._hasAdvancedConditions) {
      if (this._useCelEditor) {
        conditionExpr = this._conditionExpression.trim() || null;
      } else {
        conditionExpr = this._buildMultiConditionExpression() || null;
      }
    } else {
      // OSS simple mode
      conditionExpr = this._buildSimpleExpression() || null;
    }

    const formData: RuleFormData = {
      action: this._action,
      condition_expression: conditionExpr,
      condition_type: conditionExpr ? 'cel' : 'simple',
      description: this._description.trim() || null,
      is_enabled: this._isEnabled,
      approval_policy_id:
        this._action === 'require_approval' ? this._approvalPolicyId : null,
    };

    this.dispatchEvent(
      new CustomEvent('save-rule', {
        detail: {
          rule: this.rule,
          formData,
        },
        bubbles: true,
        composed: true,
      })
    );
  }

  private _handleClose() {
    this.dispatchEvent(
      new CustomEvent('close', { bubbles: true, composed: true })
    );
  }

  private _renderOperatorSelect(
    value: string,
    onChange: (val: string) => void
  ) {
    return html`
      <sl-select
        size="small"
        value=${value}
        @sl-change=${(e: Event) => onChange((e.target as any).value)}
      >
        <sl-option value="==">equals</sl-option>
        <sl-option value="!=">not equals</sl-option>
        <sl-option value=">">greater than</sl-option>
        <sl-option value=">=">greater or equal</sl-option>
        <sl-option value="<">less than</sl-option>
        <sl-option value="<=">less or equal</sl-option>
        <sl-option value="contains">contains</sl-option>
        <sl-option value="starts_with">starts with</sl-option>
        <sl-option value="ends_with">ends with</sl-option>
      </sl-select>
    `;
  }

  private _renderFieldInput(value: string, onChange: (val: string) => void) {
    const args = this._getToolArguments();
    if (args.length > 0) {
      return html`
        <sl-select
          class="param-select"
          size="small"
          value=${value}
          @sl-change=${(e: Event) => onChange((e.target as any).value)}
          placeholder="Select parameter"
        >
          ${args.map((arg) => html`<sl-option value=${arg}>${arg}</sl-option>`)}
        </sl-select>
      `;
    }
    return html`
      <sl-input
        size="small"
        value=${value}
        @sl-input=${(e: Event) => onChange((e.target as any).value)}
        placeholder="e.g., command"
      ></sl-input>
    `;
  }

  private _renderConditionEditor() {
    if (!this._hasAdvancedConditions) {
      // Simple mode (OSS): single condition
      return html`
        <div class="condition-section">
          <div class="simple-condition">
            <div>
              <label>Parameter</label>
              ${this._renderFieldInput(
                this._simpleField,
                (v) => (this._simpleField = v)
              )}
            </div>
            <div>
              <label>Operator</label>
              ${this._renderOperatorSelect(
                this._simpleOperator,
                (v) => (this._simpleOperator = v)
              )}
            </div>
            <div>
              <label>Value</label>
              <sl-input
                size="small"
                value=${this._simpleValue}
                @sl-input=${(e: Event) =>
                  (this._simpleValue = (e.target as any).value)}
                placeholder="e.g., production"
              ></sl-input>
            </div>
          </div>
          ${this._simpleField && this._simpleValue
            ? html`<div
                class="cel-help"
                style="margin-top: var(--sl-spacing-small);"
              >
                Expression: <code>${this._buildSimpleExpression()}</code>
              </div>`
            : ''}
        </div>
      `;
    }

    // Advanced mode (EE)
    if (this._useCelEditor) {
      return this._renderCelEditor();
    }

    return this._renderMultiConditionEditor();
  }

  private _renderMultiConditionEditor() {
    const args = this._getToolArguments();
    const builtExpr = this._buildMultiConditionExpression();

    return html`
      <div class="condition-section">
        ${this._conditions.map((cond, i) => {
          const isLast = i === this._conditions.length - 1;
          return html`
            <div class="condition-row">
              <div class="simple-condition">
                <div>
                  ${i === 0 ? html`<label>Parameter</label>` : ''}
                  ${this._renderFieldInput(cond.field, (v) =>
                    this._updateCondition(i, 'field', v)
                  )}
                </div>
                <div>
                  ${i === 0 ? html`<label>Operator</label>` : ''}
                  ${this._renderOperatorSelect(cond.operator, (v) =>
                    this._updateCondition(i, 'operator', v)
                  )}
                </div>
                <div>
                  ${i === 0 ? html`<label>Value</label>` : ''}
                  <sl-input
                    size="small"
                    value=${cond.value}
                    @sl-input=${(e: Event) =>
                      this._updateCondition(
                        i,
                        'value',
                        (e.target as any).value
                      )}
                    placeholder="e.g., production"
                  ></sl-input>
                </div>
              </div>
              ${this._conditions.length > 1
                ? html`<sl-icon-button
                    name="x-lg"
                    label="Remove condition"
                    style="font-size: 0.75rem;"
                    @click=${() => this._removeCondition(i)}
                  ></sl-icon-button>`
                : ''}
            </div>
            ${!isLast
              ? html`
                  <div class="condition-join">
                    <span class="join-line"></span>
                    <span
                      class="join-toggle"
                      @click=${() => this._toggleJoinOperator()}
                      >${this._conditionOperator}</span
                    >
                    <span class="join-line"></span>
                  </div>
                `
              : ''}
          `;
        })}

        <div class="condition-actions">
          <sl-button
            size="small"
            variant="text"
            @click=${() => this._addCondition()}
          >
            <sl-icon slot="prefix" name="plus-lg"></sl-icon>
            Add condition
          </sl-button>
          <span class="cel-toggle">
            <sl-switch
              size="small"
              ?checked=${this._useCelEditor}
              @sl-change=${(e: Event) => {
                const checked = (e.target as any).checked;
                if (checked) {
                  // Pre-populate CEL editor with the built expression
                  this._conditionExpression = builtExpr;
                }
                this._useCelEditor = checked;
              }}
            >
              CEL editor
            </sl-switch>
          </span>
        </div>

        ${builtExpr
          ? html`<div
              class="cel-help"
              style="margin-top: var(--sl-spacing-small);"
            >
              Expression: <code>${builtExpr}</code>
            </div>`
          : ''}
      </div>
    `;
  }

  private _renderCelEditor() {
    const args = this._getToolArguments();

    return html`
      <div class="condition-section">
        <sl-textarea
          label="CEL Expression"
          size="small"
          rows="3"
          value=${this._conditionExpression}
          @sl-input=${(e: Event) =>
            (this._conditionExpression = (e.target as any).value)}
          placeholder='e.g., args.amount > 1000 && args.currency == "USD"'
          help-text="Leave empty for a catch-all rule (matches all calls)"
        ></sl-textarea>
        <div class="cel-help">
          <strong>Available variables:</strong> <code>args.*</code> (tool
          arguments), <code>tool_name</code>, <code>user_id</code><br />
          <strong>Examples:</strong>
          <code>args.command.contains("rm")</code>,
          <code>args.amount > 100</code>,
          <code>args.env == "production"</code>
        </div>
        ${args.length > 0
          ? html`
              <div class="args-list">
                <strong
                  style="font-size: var(--sl-font-size-x-small); color: var(--sl-color-neutral-600);"
                  >Tool parameters:</strong
                >
                ${args.map(
                  (arg) =>
                    html`<sl-badge variant="neutral" pill>${arg}</sl-badge>`
                )}
              </div>
            `
          : ''}

        <div class="condition-actions">
          <span class="cel-toggle">
            <sl-switch
              size="small"
              ?checked=${this._useCelEditor}
              @sl-change=${() => (this._useCelEditor = false)}
            >
              CEL editor
            </sl-switch>
          </span>
        </div>
      </div>
    `;
  }

  private _renderApprovalSection() {
    const hasAdvanced = this._hasAdvancedConditions;
    const humanPolicies = this.policies.filter(
      (p) => p.approval_type !== 'ai_driven'
    );
    const aiPolicies = this.policies.filter(
      (p) => p.approval_type === 'ai_driven'
    );

    return html`
      <div class="form-group">
        <label>Approval Configuration</label>
        <div class="approval-section">
          ${hasAdvanced
            ? html`
                <div class="approval-mode-cards">
                  <div
                    class="approval-mode-card ${this._approvalMode === 'human'
                      ? 'selected'
                      : ''}"
                    @click=${() => {
                      this._approvalMode = 'human';
                      this._approvalPolicyId = null;
                    }}
                  >
                    <div class="mode-icon">
                      <sl-icon name="person-check"></sl-icon>
                    </div>
                    <div class="mode-label">Human Approval</div>
                  </div>
                  <div
                    class="approval-mode-card ${this._approvalMode === 'ai'
                      ? 'selected'
                      : ''}"
                    @click=${() => {
                      this._approvalMode = 'ai';
                      this._approvalPolicyId = null;
                    }}
                  >
                    <div class="mode-icon">
                      <sl-icon name="robot"></sl-icon>
                    </div>
                    <div class="mode-label">AI Approval</div>
                  </div>
                </div>
              `
            : ''}

          <div class="policy-select-row">
            <sl-select
              size="small"
              placeholder="Select an approval policy..."
              value=${this._approvalPolicyId || ''}
              clearable
              @sl-change=${(e: Event) => {
                const val = (e.target as any).value;
                this._approvalPolicyId = val || null;
              }}
              @sl-clear=${() => {
                this._approvalPolicyId = null;
              }}
            >
              ${this._approvalMode === 'ai'
                ? html`
                    ${aiPolicies.length === 0
                      ? html`<sl-option disabled value=""
                          >No AI policies — create one below</sl-option
                        >`
                      : aiPolicies.map(
                          (p) =>
                            html`<sl-option value=${p.id}>${p.name}</sl-option>`
                        )}
                  `
                : html`
                    ${humanPolicies.length === 0
                      ? html`<sl-option disabled value=""
                          >No policies — create one below</sl-option
                        >`
                      : humanPolicies.map(
                          (p) =>
                            html`<sl-option value=${p.id}>${p.name}</sl-option>`
                        )}
                  `}
            </sl-select>
            <sl-button
              size="small"
              variant="text"
              @click=${() => {
                this._showNewPolicy = !this._showNewPolicy;
              }}
            >
              <sl-icon
                slot="prefix"
                name=${this._showNewPolicy ? 'dash-lg' : 'plus-lg'}
              ></sl-icon>
              ${this._showNewPolicy ? 'Cancel' : 'New'}
            </sl-button>
          </div>

          ${this._showNewPolicy ? this._renderInlineNewPolicy() : ''}
          ${this._approvalMode === 'ai' &&
          hasAdvanced &&
          !this._approvalPolicyId &&
          !this._showNewPolicy
            ? html`<div
                class="hint"
                style="margin-top: var(--sl-spacing-small);"
              >
                Select an existing AI policy or create a new one to configure
                model, prompt, confidence threshold, and fallback behavior.
              </div>`
            : ''}
        </div>
      </div>
    `;
  }

  private _renderInlineNewPolicy() {
    const isAiMode = this._approvalMode === 'ai' && this._hasAdvancedConditions;

    return html`
      <div class="ai-config" style="margin-top: var(--sl-spacing-small);">
        <div class="ai-config-title">
          New ${isAiMode ? 'AI' : ''} Approval Policy
        </div>
        <div class="ai-config-grid">
          <div class="ai-config-full">
            <sl-input
              size="small"
              label="Policy Name"
              placeholder="e.g., ${isAiMode
                ? 'AI Review for high-risk operations'
                : 'Manual review policy'}"
              value=${this._description || ''}
              @sl-input=${(e: Event) =>
                (this._description = (e.target as any).value)}
            ></sl-input>
          </div>
          ${isAiMode
            ? html`
                <div>
                  <sl-select
                    size="small"
                    label="AI Model"
                    value=${this._aiModel}
                    @sl-change=${(e: Event) =>
                      (this._aiModel = (e.target as any).value)}
                    placeholder="Select model..."
                  >
                    <sl-option value="gpt-4o">GPT-4o</sl-option>
                    <sl-option value="gpt-4o-mini">GPT-4o Mini</sl-option>
                    <sl-option value="claude-sonnet-4-20250514"
                      >Claude Sonnet</sl-option
                    >
                    <sl-option value="claude-opus-4-20250514"
                      >Claude Opus</sl-option
                    >
                  </sl-select>
                </div>
                <div>
                  <sl-input
                    size="small"
                    label="Confidence Threshold"
                    type="number"
                    min="0"
                    max="1"
                    step="0.05"
                    value=${this._aiConfidenceThreshold.toString()}
                    @sl-input=${(e: Event) =>
                      (this._aiConfidenceThreshold = parseFloat(
                        (e.target as any).value
                      ))}
                    help-text="0.0 – 1.0"
                  ></sl-input>
                </div>
                <div class="ai-config-full">
                  <sl-textarea
                    size="small"
                    label="Approval Guidelines / Prompt"
                    rows="3"
                    value=${this._aiGuidelines}
                    @sl-input=${(e: Event) =>
                      (this._aiGuidelines = (e.target as any).value)}
                    placeholder="Describe when the AI should approve or deny this tool call..."
                  ></sl-textarea>
                </div>
                <div>
                  <sl-select
                    size="small"
                    label="When Uncertain"
                    value=${this._aiFallbackBehavior}
                    @sl-change=${(e: Event) =>
                      (this._aiFallbackBehavior = (e.target as any).value)}
                  >
                    <sl-option value="approve">Approve</sl-option>
                    <sl-option value="deny">Deny</sl-option>
                    <sl-option value="escalate">Escalate to Human</sl-option>
                  </sl-select>
                </div>
                ${this._aiFallbackBehavior === 'escalate'
                  ? html`
                      <div>
                        <sl-select
                          size="small"
                          label="Escalation Policy"
                          value=${this._aiEscalationPolicyId || ''}
                          @sl-change=${(e: Event) =>
                            (this._aiEscalationPolicyId =
                              (e.target as any).value || null)}
                          placeholder="Select policy..."
                        >
                          ${this.policies
                            .filter((p) => p.approval_type !== 'ai_driven')
                            .map(
                              (p) =>
                                html`<sl-option value=${p.id}
                                  >${p.name}</sl-option
                                >`
                            )}
                          ${this.policies.filter(
                            (p) => p.approval_type !== 'ai_driven'
                          ).length === 0
                            ? html`<sl-option disabled value=""
                                >No human policies available</sl-option
                              >`
                            : ''}
                        </sl-select>
                      </div>
                    `
                  : ''}
              `
            : ''}
        </div>
        <div style="margin-top: var(--sl-spacing-small); text-align: right;">
          <sl-button
            size="small"
            variant="primary"
            @click=${() => this._handleCreateInlinePolicy()}
          >
            Create & Select Policy
          </sl-button>
        </div>
      </div>
    `;
  }

  private async _handleCreateInlinePolicy() {
    const isAiMode = this._approvalMode === 'ai' && this._hasAdvancedConditions;
    const name = this._description?.trim() || `Policy for ${this.toolName}`;

    const policyData: any = {
      name,
      description: name,
      approval_type: isAiMode ? 'ai_driven' : 'standard',
    };

    if (isAiMode) {
      policyData.approval_mode = 'ai_driven';
      policyData.ai_model = this._aiModel;
      policyData.ai_guidelines = this._aiGuidelines || null;
      policyData.ai_confidence_threshold = this._aiConfidenceThreshold;
      policyData.ai_fallback_behavior = this._aiFallbackBehavior;
      if (
        this._aiFallbackBehavior === 'escalate' &&
        this._aiEscalationPolicyId
      ) {
        policyData.escalation_policy_id = this._aiEscalationPolicyId;
      }
    }

    this.dispatchEvent(
      new CustomEvent('create-policy', {
        detail: { policyData },
        bubbles: true,
        composed: true,
      })
    );
  }

  render() {
    return html`
      <sl-dialog
        label="${this._isEditing ? 'Edit' : 'Add'} Access Rule${this.toolName
          ? ` — ${this.toolName}`
          : ''}"
        ?open=${this.open}
        @sl-request-close=${this._handleClose}
        style="--width: 560px; --sl-panel-background-color: var(--sl-color-neutral-0);"
      >
        ${this._error
          ? html`<sl-alert
              variant="danger"
              open
              closable
              @sl-after-hide=${() => (this._error = null)}
            >
              <sl-icon slot="icon" name="exclamation-octagon"></sl-icon>
              ${this._error}
            </sl-alert>`
          : ''}

        <div class="form-group">
          <label>Action</label>
          <div class="action-cards">
            <div
              class="action-card deny ${this._action === 'deny'
                ? 'selected'
                : ''}"
              @click=${() => (this._action = 'deny')}
            >
              <div class="action-icon">
                <sl-icon
                  name="x-octagon-fill"
                  style="font-size: 1.5rem; color: var(--sl-color-danger-500);"
                ></sl-icon>
              </div>
              <div class="action-label">Deny</div>
              <div class="action-desc">Block execution</div>
            </div>
            <div
              class="action-card approval ${this._action === 'require_approval'
                ? 'selected'
                : ''}"
              @click=${() => (this._action = 'require_approval')}
            >
              <div class="action-icon">
                <sl-icon
                  name="shield-lock-fill"
                  style="font-size: 1.5rem; color: var(--sl-color-primary-500);"
                ></sl-icon>
              </div>
              <div class="action-label">Require Approval</div>
              <div class="action-desc">Human or AI review</div>
            </div>
            <div
              class="action-card ${this._action === 'allow' ? 'selected' : ''}"
              @click=${() => (this._action = 'allow')}
            >
              <div class="action-icon">
                <sl-icon
                  name="check-circle-fill"
                  style="font-size: 1.5rem; color: var(--sl-color-success-500);"
                ></sl-icon>
              </div>
              <div class="action-label">Allow</div>
              <div class="action-desc">Execute freely</div>
            </div>
          </div>
        </div>

        ${this._action === 'require_approval'
          ? this._renderApprovalSection()
          : ''}

        <sl-divider></sl-divider>

        <div class="form-group">
          <label>Condition (when does this rule apply?)</label>
          <div class="hint">
            Leave empty for a catch-all rule that matches all calls.
          </div>
          ${this._renderConditionEditor()}
        </div>

        ${this._action === 'deny'
          ? html`
              <div class="form-group">
                <sl-textarea
                  label="Denial Message"
                  size="small"
                  rows="2"
                  value=${this._description}
                  @sl-input=${(e: Event) =>
                    (this._description = (e.target as any).value)}
                  placeholder="This operation is not allowed because..."
                  help-text="This message is returned to the AI agent when the call is denied."
                ></sl-textarea>
              </div>
            `
          : ''}
        ${this._action === 'require_approval'
          ? html`
              <div class="form-group">
                <sl-input
                  label="Description"
                  size="small"
                  value=${this._description}
                  @sl-input=${(e: Event) =>
                    (this._description = (e.target as any).value)}
                  placeholder="e.g., High-value transaction review"
                  help-text="Helps approvers understand why this rule exists."
                ></sl-input>
              </div>
            `
          : ''}
        ${this._action === 'allow'
          ? html`
              <div class="form-group">
                <sl-input
                  label="Description (optional)"
                  size="small"
                  value=${this._description}
                  @sl-input=${(e: Event) =>
                    (this._description = (e.target as any).value)}
                  placeholder="e.g., Low-risk read-only operations"
                ></sl-input>
              </div>
            `
          : ''}

        <div class="dialog-footer">
          <sl-button variant="default" @click=${this._handleClose}>
            Cancel
          </sl-button>
          <sl-button
            variant="primary"
            ?loading=${this._saving}
            @click=${this._handleSave}
          >
            ${this._isEditing ? 'Update Rule' : 'Add Rule'}
          </sl-button>
        </div>
      </sl-dialog>
    `;
  }
}
