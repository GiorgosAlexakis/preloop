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
