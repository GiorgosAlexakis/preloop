import { html, fixture, expect } from '@open-wc/testing';

import './tool-rule-editor';
import type { ToolRuleEditor } from './tool-rule-editor';

describe('ToolRuleEditor', () => {
  it('renders dialog when open', async () => {
    const el = (await fixture(
      html`<tool-rule-editor
        .open=${true}
        .workflows=${[]}
        .features=${{}}
      ></tool-rule-editor>`
    )) as ToolRuleEditor;

    await el.updateComplete;

    const dialog = el.shadowRoot?.querySelector('sl-dialog');
    expect(dialog).to.exist;
    expect(dialog?.hasAttribute('open') || (dialog as any).open).to.be.true;
  });

  it('renders action cards for deny, require_approval, and allow', async () => {
    const el = (await fixture(
      html`<tool-rule-editor
        .open=${true}
        .workflows=${[]}
        .features=${{}}
      ></tool-rule-editor>`
    )) as ToolRuleEditor;

    await el.updateComplete;

    const actionCards = el.shadowRoot?.querySelectorAll('.action-card');
    expect(actionCards).to.have.lengthOf(3);

    const labels = Array.from(actionCards!).map(
      (c) => c.querySelector('.action-label')?.textContent
    );
    expect(labels).to.include('Deny');
    expect(labels).to.include('Require Approval');
    expect(labels).to.include('Allow');
  });

  it('dispatches close event when Cancel is clicked', async () => {
    const el = (await fixture(
      html`<tool-rule-editor
        .open=${true}
        .workflows=${[]}
        .features=${{}}
      ></tool-rule-editor>`
    )) as ToolRuleEditor;

    await el.updateComplete;

    let closeFired = false;
    el.addEventListener('close', () => {
      closeFired = true;
    });

    const cancelBtn = el.shadowRoot?.querySelector(
      'sl-button[variant="default"]'
    ) as HTMLElement;
    expect(cancelBtn).to.exist;
    cancelBtn.click();

    await el.updateComplete;
    expect(closeFired).to.be.true;
  });

  it('dispatches save-rule event when Add Rule is clicked', async () => {
    const el = (await fixture(
      html`<tool-rule-editor
        .open=${true}
        .workflows=${[]}
        .features=${{}}
      ></tool-rule-editor>`
    )) as ToolRuleEditor;

    await el.updateComplete;

    let saveDetail: { rule: unknown; formData: unknown } | null = null;
    el.addEventListener('save-rule', ((e: CustomEvent) => {
      saveDetail = e.detail;
    }) as EventListener);

    const saveBtn = el.shadowRoot?.querySelector(
      'sl-button[variant="primary"]'
    ) as HTMLElement;
    expect(saveBtn).to.exist;
    saveBtn.click();

    await el.updateComplete;
    expect(saveDetail).to.exist;
    expect(saveDetail?.formData).to.exist;
    expect((saveDetail?.formData as any).action).to.equal('deny');
  });

  it('shows Edit label when editing existing rule', async () => {
    const existingRule = {
      id: 'rule-1',
      account_id: 'acc-1',
      tool_configuration_id: 'cfg-1',
      action: 'allow' as const,
      condition_expression: null,
      condition_type: 'simple' as const,
      priority: 0,
      description: null,
      is_enabled: true,
      approval_workflow_id: null,
    };

    const el = (await fixture(
      html`<tool-rule-editor
        .open=${true}
        .rule=${existingRule}
        .workflows=${[]}
        .features=${{}}
      ></tool-rule-editor>`
    )) as ToolRuleEditor;

    await el.updateComplete;

    const dialog = el.shadowRoot?.querySelector('sl-dialog');
    expect(dialog?.getAttribute('label')).to.include('Edit');
  });
});
