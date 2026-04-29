import { expect } from '@open-wc/testing';

import './flow-view';
import type { FlowView } from './flow-view';

describe('FlowView model selection', () => {
  function createElement(): FlowView {
    return document.createElement('flow-view') as FlowView;
  }

  it('does not filter AI models by selected agent type', () => {
    const element = createElement() as any;
    element.flow = { name: 'Test', agent_type: 'gemini' };
    element.models = [
      { id: 'openai-1', name: 'GPT', provider_name: 'openai' },
      { id: 'anthropic-1', name: 'Claude', provider_name: 'anthropic' },
      { id: 'google-1', name: 'Gemini', provider_name: 'google' },
    ];

    expect(
      element.getSelectableModels().map((model: any) => model.id)
    ).to.deep.equal(['openai-1', 'anthropic-1', 'google-1']);
  });

  it('describes the gateway protocol selected for each harness', () => {
    const element = createElement() as any;

    expect(element.getAgentProtocolLabel('gemini')).to.equal(
      'Gemini-compatible gateway endpoint'
    );
    expect(element.getAgentProtocolLabel('codex')).to.equal(
      'OpenAI-compatible gateway endpoint'
    );
    expect(element.getAgentProtocolLabel('opencode')).to.equal(
      'OpenAI-compatible gateway endpoint'
    );
  });
});
