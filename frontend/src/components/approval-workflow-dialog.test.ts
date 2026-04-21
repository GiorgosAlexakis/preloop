import { html, fixture, expect } from '@open-wc/testing';
import sinon from 'sinon';

import './approval-workflow-dialog';
import type { ApprovalWorkflowDialog } from './approval-workflow-dialog';

describe('ApprovalWorkflowDialog', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');
    fetchStub = sinon.stub(window, 'fetch');
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.clear();
  });

  it('shows Slack, Mattermost, and Webhook in OSS mode', async () => {
    const el = (await fixture(
      html`<approval-workflow-dialog
        .open=${true}
        .features=${{}}
      ></approval-workflow-dialog>`
    )) as ApprovalWorkflowDialog;
    await el.updateComplete;

    const options = Array.from(
      el.shadowRoot!.querySelectorAll('sl-option')
    ).map((option) => option.getAttribute('value'));

    expect(options).to.include('standard');
    expect(options).to.include('slack');
    expect(options).to.include('mattermost');
    expect(options).to.include('webhook');
    expect(options).to.not.include('ai_driven');
  });

  it('normalises legacy approval_type="manual" to "standard" when populating the form', async () => {
    const el = (await fixture(
      html`<approval-workflow-dialog
        .open=${true}
        .features=${{}}
        .policy=${{
          id: 'wf-legacy',
          name: 'Default Approval Workflow',
          approval_type: 'manual',
          is_default: true,
        } as any}
      ></approval-workflow-dialog>`
    )) as ApprovalWorkflowDialog;
    await el.updateComplete;

    // The dialog dropdown only knows "standard" / "slack" / "mattermost" /
    // "webhook" / "ai_driven", so the legacy "manual" value (the older
    // synonym for in-UI human approval) must be coerced to "standard" or
    // the type field renders blank.
    expect((el as any)._approvalType).to.equal('standard');
  });

  it('binds the approver multiselect value to prefixed user/team ids', async () => {
    const el = (await fixture(
      html`<approval-workflow-dialog
        .open=${true}
        .features=${{ advanced_approvals: true }}
      ></approval-workflow-dialog>`
    )) as ApprovalWorkflowDialog;

    // Skip the auto-loader; we want full control over users/teams.
    (el as any)._users = [
      { id: 'user-1', username: 'alice', email: 'alice@example.com' },
      { id: 'user-2', username: 'bob', email: 'bob@example.com' },
    ];
    (el as any)._teams = [{ id: 'team-1', name: 'platform' }];
    (el as any)._approverUserIds = ['user-1'];
    (el as any)._approverTeamIds = ['team-1'];
    (el as any)._approvalType = 'standard';
    (el as any).requestUpdate();
    await el.updateComplete;

    // The controlled <sl-select> value must use the same `user:` / `team:`
    // prefixes as the <sl-option> values — otherwise Shoelace renders
    // nothing as selected and clicks on options appear to do nothing
    // because the controlled value never matches any option after the
    // round-trip.
    const select = el.shadowRoot!.querySelector(
      'sl-select[placeholder="Select users or teams..."]'
    ) as HTMLElement & { value: string | string[] };
    expect(Array.from(select.value as string[])).to.deep.equal([
      'user:user-1',
      'team:team-1',
    ]);

    // Simulate the user selecting alice and the platform team via the
    // multiselect. The change handler must strip the prefixes back into
    // the raw id arrays the API expects.
    (el as any)._handleApproverChange({
      target: { value: ['user:user-2', 'team:team-1'] },
    });
    expect((el as any)._approverUserIds).to.deep.equal(['user-2']);
    expect((el as any)._approverTeamIds).to.deep.equal(['team-1']);
  });

  it('submits webhook_url for Slack workflows', async () => {
    fetchStub.callsFake(
      async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString();
        const method = (init?.method || 'GET').toUpperCase();

        if (url.endsWith('/api/v1/approval-workflows') && method === 'POST') {
          return new Response(
            JSON.stringify({
              id: 'workflow-1',
              account_id: 'account-1',
              name: 'Slack approvals',
              approval_type: 'slack',
              approval_mode: 'standard',
              is_default: false,
              async_approval_enabled: false,
            }),
            {
              status: 201,
              headers: { 'Content-Type': 'application/json' },
            }
          );
        }

        return new Response(JSON.stringify({ detail: 'Unhandled request' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      }
    );

    const el = (await fixture(
      html`<approval-workflow-dialog
        .open=${true}
        .features=${{}}
      ></approval-workflow-dialog>`
    )) as ApprovalWorkflowDialog;
    await el.updateComplete;

    (el as any)._name = 'Slack approvals';
    (el as any)._approvalType = 'slack';
    (el as any)._webhookUrl = 'https://hooks.slack.com/services/test';
    (el as any)._channel = '#approvals';

    await (el as any)._handleSave();

    const createCall = fetchStub.getCalls().find((call) => {
      const url = String(call.args[0]);
      const method = String(
        (call.args[1] as RequestInit | undefined)?.method || 'GET'
      ).toUpperCase();
      return url.endsWith('/api/v1/approval-workflows') && method === 'POST';
    });

    expect(createCall).to.exist;

    const body = JSON.parse(
      (createCall!.args[1] as RequestInit).body as string
    );
    expect(body.approval_type).to.equal('slack');
    expect(body.channel).to.equal('#approvals');
    expect(body.approval_config.webhook_url).to.equal(
      'https://hooks.slack.com/services/test'
    );
  });
});
