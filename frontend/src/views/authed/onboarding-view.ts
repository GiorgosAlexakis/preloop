import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement } from 'lit/decorators.js';
import tailwindStyles from '../../styles/tailwind.css?inline';
import '../../components/view-header.ts';

import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
import '@shoelace-style/shoelace/dist/components/tab-panel/tab-panel.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/copy-button/copy-button.js';

@customElement('onboarding-view')
export class OnboardingView extends LitElement {
  static styles = [
    unsafeCSS(tailwindStyles),
    css`
      :host {
        display: block;
        padding: var(--sl-spacing-large);
        max-width: 800px;
        margin: 0 auto;
      }

      .hero {
        text-align: center;
        margin-bottom: var(--sl-spacing-3x-large);
      }

      .hero h1 {
        font-size: var(--sl-font-size-2x-large);
        margin-bottom: var(--sl-spacing-small);
        color: var(--sl-color-neutral-900);
      }

      .hero p {
        color: var(--sl-color-neutral-500);
        margin: 0;
      }

      .instruction-step {
        display: flex;
        gap: var(--sl-spacing-medium);
        margin-bottom: var(--sl-spacing-large);
      }

      .step-number {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: var(--sl-color-primary-100);
        color: var(--sl-color-primary-600);
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: bold;
        flex-shrink: 0;
      }

      .step-content h3 {
        margin: 0 0 var(--sl-spacing-x-small) 0;
        color: var(--sl-color-neutral-800);
      }

      .step-content p {
        margin: 0 0 var(--sl-spacing-medium) 0;
        color: var(--sl-color-neutral-600);
        font-size: var(--sl-font-size-small);
      }

      .code-block {
        background: var(--sl-color-neutral-50);
        border: 1px solid var(--sl-color-neutral-200);
        border-radius: var(--sl-border-radius-medium);
        padding: var(--sl-spacing-small) var(--sl-spacing-medium);
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .code-block code {
        font-family: var(--sl-font-mono);
        font-size: var(--sl-font-size-small);
        color: var(--sl-color-primary-600);
      }
    `,
  ];

  render() {
    return html`
      <div
        class="bg-background-dark text-text-main font-body p-6 md:p-12 min-h-[calc(100vh-64px)] w-full box-border flex justify-center items-start"
      >
        <div
          class="glass-panel w-full max-w-[800px] rounded-lg p-8 md:p-12 mt-8 border border-white/10 shadow-glow-primary"
        >
          <div class="text-center mb-12">
            <h1
              class="text-3xl md:text-4xl font-display font-bold text-transparent bg-clip-text bg-gradient-to-r from-primary to-success mb-4 shadow-neon-glow inline-block"
            >
              Initialize Workforce
            </h1>
            <p class="text-text-muted text-lg">
              Set up the Preloop CLI and connect your OpenClaw agents to the
              secure gateway.
            </p>
          </div>

          <sl-tab-group class="modern-tabs">
            <sl-tab slot="nav" panel="cli">
              <sl-icon name="terminal" class="mr-2"></sl-icon> CLI Setup
            </sl-tab>
            <sl-tab slot="nav" panel="plugin">
              <sl-icon name="puzzle" class="mr-2"></sl-icon> OpenClaw Plugin
            </sl-tab>
            <sl-tab slot="nav" panel="gateway">
              <sl-icon name="key" class="mr-2"></sl-icon> API Gateway
            </sl-tab>

            <sl-tab-panel name="cli">
              <div class="pt-8 space-y-8">
                <div class="flex gap-6 relative group">
                  <div
                    class="absolute -inset-2 bg-primary/5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                  ></div>
                  <div
                    class="relative z-10 w-12 h-12 rounded-full border border-primary/30 flex items-center justify-center font-mono font-bold text-primary shadow-glow-primary bg-background-dark shrink-0"
                  >
                    01
                  </div>
                  <div class="relative z-10 flex-1">
                    <h3
                      class="text-xl font-display font-bold text-text-main mb-2"
                    >
                      Install CLI
                    </h3>
                    <p class="text-text-muted mb-4">
                      Install the Preloop development tools globally using your
                      package manager of choice.
                    </p>
                    <div
                      class="bg-black/50 border border-white/10 rounded-md p-4 flex justify-between items-center group-hover:border-primary/50 transition-colors"
                    >
                      <code class="font-mono text-primary text-sm"
                        >npm install -g @preloop/cli</code
                      >
                      <sl-copy-button
                        value="npm install -g @preloop/cli"
                      ></sl-copy-button>
                    </div>
                  </div>
                </div>

                <div class="flex gap-6 relative group">
                  <div
                    class="absolute -inset-2 bg-success/5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                  ></div>
                  <div
                    class="relative z-10 w-12 h-12 rounded-full border border-success/30 flex items-center justify-center font-mono font-bold text-success shadow-glow-success bg-background-dark shrink-0"
                  >
                    02
                  </div>
                  <div class="relative z-10 flex-1">
                    <h3
                      class="text-xl font-display font-bold text-text-main mb-2"
                    >
                      Authenticate
                    </h3>
                    <p class="text-text-muted mb-4">
                      Run the login command. This will open a browser window to
                      securely authorize your local machine.
                    </p>
                    <div
                      class="bg-black/50 border border-white/10 rounded-md p-4 flex justify-between items-center group-hover:border-success/50 transition-colors"
                    >
                      <code class="font-mono text-success text-sm"
                        >preloop auth login</code
                      >
                      <sl-copy-button
                        value="preloop auth login"
                      ></sl-copy-button>
                    </div>
                  </div>
                </div>

                <div class="flex gap-6 relative group">
                  <div
                    class="absolute -inset-2 bg-primary/5 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity"
                  ></div>
                  <div
                    class="relative z-10 w-12 h-12 rounded-full border border-primary/30 flex items-center justify-center font-mono font-bold text-primary shadow-glow-primary bg-background-dark shrink-0"
                  >
                    03
                  </div>
                  <div class="relative z-10 flex-1">
                    <h3
                      class="text-xl font-display font-bold text-text-main mb-2"
                    >
                      Discover Agents
                    </h3>
                    <p class="text-text-muted mb-4">
                      Scan your local environment or remote registry to find
                      compatible AI agents to connect.
                    </p>
                    <div
                      class="bg-black/50 border border-white/10 rounded-md p-4 flex justify-between items-center group-hover:border-primary/50 transition-colors"
                    >
                      <code class="font-mono text-primary text-sm"
                        >preloop agents discover</code
                      >
                      <sl-copy-button
                        value="preloop agents discover"
                      ></sl-copy-button>
                    </div>
                  </div>
                </div>

                <div class="text-right mt-12 pt-6 border-t border-white/10">
                  <sl-button
                    variant="primary"
                    href="/console/agents"
                    class="shadow-glow-primary"
                  >
                    Proceed to Canvas
                    <sl-icon slot="suffix" name="arrow-right"></sl-icon>
                  </sl-button>
                </div>
              </div>
            </sl-tab-panel>

            <sl-tab-panel name="plugin">
              <div class="pt-8 text-center max-w-2xl mx-auto">
                <h3 class="text-2xl font-display font-bold text-text-main mb-2">
                  OpenClaw Integration
                </h3>
                <p class="text-text-muted mb-8">
                  Connect your workforce directly to the OpenClaw ecosystem.
                </p>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div
                    class="glass-panel border border-white/10 p-8 rounded-lg hover:border-primary/50 hover:bg-white/5 transition-all cursor-pointer group"
                  >
                    <sl-icon
                      name="box-arrow-up-right"
                      class="text-4xl text-primary mb-4 group-hover:rotate-12 transition-transform shadow-neon-glow"
                    ></sl-icon>
                    <h4 class="text-xl font-bold text-text-main mb-2">
                      OAuth Flow
                    </h4>
                    <p class="text-sm text-text-muted mb-6">
                      Quick connect via browser
                    </p>
                    <sl-button
                      variant="primary"
                      class="w-full shadow-glow-primary"
                      >Connect</sl-button
                    >
                  </div>
                  <div
                    class="glass-panel border border-white/10 p-8 rounded-lg hover:border-warning/50 hover:bg-white/5 transition-all cursor-pointer group"
                  >
                    <sl-icon
                      name="sliders"
                      class="text-4xl text-warning mb-4 group-hover:-rotate-12 transition-transform shadow-glow-warning"
                    ></sl-icon>
                    <h4 class="text-xl font-bold text-text-main mb-2">
                      Manual Config
                    </h4>
                    <p class="text-sm text-text-muted mb-6">
                      Use existing API keys
                    </p>
                    <sl-button variant="default" class="w-full"
                      >Configure</sl-button
                    >
                  </div>
                </div>
              </div>
            </sl-tab-panel>

            <sl-tab-panel name="gateway">
              <div class="pt-8">
                <h3
                  class="text-2xl font-display font-bold text-text-main flex items-center gap-3 mb-6"
                >
                  <sl-icon name="key" class="text-primary"></sl-icon> Gateway
                  API Keys
                </h3>

                <div
                  class="bg-black/50 p-6 rounded-lg flex items-center justify-between border border-white/10 mb-8"
                >
                  <div>
                    <div
                      class="text-[10px] font-bold text-text-muted uppercase tracking-widest mb-2 font-display"
                    >
                      Global Gateway Key
                    </div>
                    <code class="font-mono text-primary text-lg tracking-wider"
                      >pl_test_••••••••••••••••••••••••••••</code
                    >
                  </div>
                  <sl-button variant="primary" outline>Copy</sl-button>
                </div>

                <div
                  class="border-l-4 border-warning bg-warning/5 p-6 text-text-main text-sm rounded-r-lg leading-relaxed"
                >
                  <strong class="text-warning font-bold mr-2"
                    >Security Protocol:</strong
                  >
                  Each agent requires a unique API key for gateway routing. Do
                  not reuse keys across different workforce units. Use the
                  <code
                    class="text-primary font-mono bg-black/30 px-2 py-1 rounded mx-1"
                    >preloop keys create</code
                  >
                  command to generate scoped credentials.
                </div>
              </div>
            </sl-tab-panel>
          </sl-tab-group>
        </div>
      </div>
    `;
  }
}
