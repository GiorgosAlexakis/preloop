import { expect } from '@open-wc/testing';
import sinon from 'sinon';

import { sendAgentControlVoiceTranscript } from './api';

describe('Agent Control API', () => {
  let fetchStub: sinon.SinonStub;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-token');
    fetchStub = sinon.stub(window, 'fetch');
  });

  afterEach(() => {
    fetchStub.restore();
    localStorage.removeItem('accessToken');
  });

  it('routes voice transcripts to the voice transcript endpoint', async () => {
    fetchStub.resolves(
      new Response(
        JSON.stringify({
          command_id: 'cmd-1',
          managed_agent_id: 'agent-1',
          session_mode: 'new',
          published: true,
        }),
        {
          status: 202,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const response = await sendAgentControlVoiceTranscript('agent-1', {
      transcript: 'Summarize your current status',
      start_new_session: true,
      metadata: { requested_from: 'test' },
      voice: { locale: 'en-US' },
    });

    expect(response.command_id).to.equal('cmd-1');
    expect(fetchStub.calledOnce).to.equal(true);
    const [url, init] = fetchStub.firstCall.args as [string, RequestInit];
    expect(url).to.equal('/api/v1/agents/agent-1/control/voice-transcripts');
    expect(init.method).to.equal('POST');
    expect(new Headers(init.headers).get('Authorization')).to.equal(
      'Bearer test-token'
    );
    expect(JSON.parse(init.body as string)).to.deep.equal({
      transcript: 'Summarize your current status',
      start_new_session: true,
      metadata: { requested_from: 'test' },
      voice: { locale: 'en-US' },
    });
  });
});
