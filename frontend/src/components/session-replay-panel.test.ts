import { expect, fixture, html } from '@open-wc/testing';
import './session-replay-panel';
import type { SessionReplayPanel } from './session-replay-panel';

describe('SessionReplayPanel', () => {
  it('renders agent control messages in chat mode', async () => {
    const element = await fixture<SessionReplayPanel>(html`
      <session-replay-panel
        replayMode="chat"
        .session=${{
          id: 'session-1',
          sourceId: 'hermes-1',
          sourceType: 'hermes',
          title: 'Hermes',
          subtitle: null,
          sessionReference: null,
          runtimePrincipalName: 'Hermes',
          flowName: null,
          flowExecutionId: null,
          status: 'active_now',
          startedAt: '2026-06-07T12:00:00Z',
          lastActivityAt: '2026-06-07T12:05:00Z',
          endedAt: null,
          totalRequests: 0,
          successfulRequests: 0,
          failedRequests: 0,
          tokenUsage: {
            prompt_tokens: 0,
            completion_tokens: 0,
            total_tokens: 0,
          },
          estimatedCost: 0,
          latestModelAlias: null,
          latestProviderName: null,
          canLoadEvents: true,
          raw: {},
        }}
        .events=${[]}
        .activity=${[
          {
            activity_type: 'agent_control_message',
            timestamp: '2026-06-07T12:05:00Z',
            title: 'Operator message',
            summary: 'Please inspect the failing test.',
            status: 'delivered',
            api_usage_id: null,
            tool_name: null,
            server_name: null,
            auth_subject_type: null,
            api_key_id: null,
            api_key_name: null,
            estimated_cost: null,
            total_tokens: null,
            metadata: { source_metadata: { source: 'web' } },
          },
        ]}
      ></session-replay-panel>
    `);

    const text = element.shadowRoot?.textContent || '';
    expect(text).to.include('Please inspect the failing test.');
    expect(text).to.not.include('No conversation preview captured.');
  });
});
