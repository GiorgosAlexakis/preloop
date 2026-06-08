import { expect } from '@open-wc/testing';

import type { ManagedAgentSummary } from '../types';
import { getAgentControlState } from './agent-control';

const baseAgent = {
  id: 'agent-1',
  runtime_session_id: null,
  owner_user_id: null,
  owner_username: null,
  owner_email: null,
  display_name: 'OpenClaw',
  session_source_type: 'openclaw',
  session_source_id: 'openclaw-1',
  session_reference: null,
  enrolled_via: 'cli',
  managed_mcp_servers: [],
  lifecycle_state: 'active',
  lifecycle_reason: null,
  lifecycle_updated_at: null,
  is_active_now: false,
  activity_status: 'idle',
  last_seen_at: new Date().toISOString(),
  started_at: null,
  last_activity_at: null,
  ended_at: null,
  total_requests: 0,
  estimated_cost: 0,
  configured_model_alias: null,
  latest_model_alias: null,
  latest_provider_name: null,
  last_request_at: null,
  mcp_proxy_configured: false,
  model_gateway_configured: false,
  onboarding_state: 'incomplete',
  live_validation_supported: false,
  live_validation_passed: null,
  live_validation_status: 'unsupported',
  last_validated_at: null,
} satisfies ManagedAgentSummary;

describe('getAgentControlState', () => {
  it('shows install_pending without enabling prompts', () => {
    const state = getAgentControlState({
      ...baseAgent,
      control_state: 'install_pending',
      control_enabled: false,
      control_online: false,
      control_capabilities: [],
    });

    expect(state.visible).to.equal(true);
    expect(state.enabled).to.equal(false);
    expect(state.label).to.equal('Install pending');
  });

  it('labels verified offline plugins as configured', () => {
    const state = getAgentControlState({
      ...baseAgent,
      control_state: 'plugin_configured',
      control_enabled: true,
      control_online: false,
      control_capabilities: ['send_text_prompt'],
    });

    expect(state.enabled).to.equal(true);
    expect(state.online).to.equal(false);
    expect(state.label).to.equal('Agent Control configured');
  });
});
