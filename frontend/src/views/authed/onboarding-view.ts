import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import '../../components/view-header.ts';

import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
import '@shoelace-style/shoelace/dist/components/tab-panel/tab-panel.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/copy-button/copy-button.js';

@customElement('onboarding-view')
export class OnboardingView extends LitElement {
  static styles = css`
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
  `;

  render() {
    return html`
      <div class="hero">
        <h1>Initialize Workforce</h1>
        <p>
          Set up the Preloop CLI and connect your OpenClaw agents to the secure
          gateway.
        </p>
      </div>

      <sl-tab-group>
        <sl-tab slot="nav" panel="cli">
          <sl-icon name="terminal"></sl-icon> CLI Setup
        </sl-tab>
        <sl-tab slot="nav" panel="plugin">
          <sl-icon name="puzzle"></sl-icon> OpenClaw Plugin
        </sl-tab>
        <sl-tab slot="nav" panel="gateway">
          <sl-icon name="key"></sl-icon> API Gateway
        </sl-tab>

        <sl-tab-panel name="cli">
          <div style="padding-top: var(--sl-spacing-large);">
            <div class="instruction-step">
              <div class="step-number">01</div>
              <div class="step-content">
                <h3>Install CLI</h3>
                <p>
                  Install the Preloop development tools globally using your
                  package manager of choice.
                </p>
                <div class="code-block">
                  <code>npm install -g @preloop/cli</code>
                  <sl-copy-button
                    value="npm install -g @preloop/cli"
                  ></sl-copy-button>
                </div>
              </div>
            </div>

            <div class="instruction-step">
              <div class="step-number">02</div>
              <div class="step-content">
                <h3>Authenticate</h3>
                <p>
                  Run the login command. This will open a browser window to
                  securely authorize your local machine.
                </p>
                <div class="code-block">
                  <code>preloop auth login</code>
                  <sl-copy-button value="preloop auth login"></sl-copy-button>
                </div>
              </div>
            </div>

            <div class="instruction-step">
              <div class="step-number">03</div>
              <div class="step-content">
                <h3>Discover Agents</h3>
                <p>
                  Scan your local environment or remote registry to find
                  compatible AI agents to connect.
                </p>
                <div class="code-block">
                  <code>preloop agents discover</code>
                  <sl-copy-button
                    value="preloop agents discover"
                  ></sl-copy-button>
                </div>
              </div>
            </div>

            <div
              style="text-align: right; margin-top: var(--sl-spacing-large);"
            >
              <sl-button variant="primary" href="/console/agents">
                Proceed to Canvas
                <sl-icon slot="suffix" name="arrow-right"></sl-icon>
              </sl-button>
            </div>
          </div>
        </sl-tab-panel>

        <sl-tab-panel name="plugin">
          <div
            style="padding-top: var(--sl-spacing-large); text-align: center;"
          >
            <h3 style="margin-top: 0;">OpenClaw Integration</h3>
            <p
              style="color: var(--sl-color-neutral-500); margin-bottom: var(--sl-spacing-large);"
            >
              Connect your workforce directly to the OpenClaw ecosystem.
            </p>

            <div
              style="display: grid; grid-template-columns: 1fr 1fr; gap: var(--sl-spacing-medium);"
            >
              <div
                style="border: 1px solid var(--sl-color-neutral-200); padding: var(--sl-spacing-large); border-radius: var(--sl-border-radius-medium);"
              >
                <sl-icon
                  name="box-arrow-up-right"
                  style="font-size: 2rem; color: var(--sl-color-primary-600);"
                ></sl-icon>
                <h4 style="margin: var(--sl-spacing-small) 0 0 0;">
                  OAuth Flow
                </h4>
                <p
                  style="margin: 0; font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-500);"
                >
                  Quick connect via browser
                </p>
                <sl-button style="margin-top: var(--sl-spacing-medium);"
                  >Connect</sl-button
                >
              </div>
              <div
                style="border: 1px solid var(--sl-color-neutral-200); padding: var(--sl-spacing-large); border-radius: var(--sl-border-radius-medium);"
              >
                <sl-icon
                  name="sliders"
                  style="font-size: 2rem; color: var(--sl-color-neutral-600);"
                ></sl-icon>
                <h4 style="margin: var(--sl-spacing-small) 0 0 0;">
                  Manual Config
                </h4>
                <p
                  style="margin: 0; font-size: var(--sl-font-size-small); color: var(--sl-color-neutral-500);"
                >
                  Use existing API keys
                </p>
                <sl-button style="margin-top: var(--sl-spacing-medium);"
                  >Configure</sl-button
                >
              </div>
            </div>
          </div>
        </sl-tab-panel>

        <sl-tab-panel name="gateway">
          <div style="padding-top: var(--sl-spacing-large);">
            <h3
              style="margin-top: 0; display: flex; align-items: center; gap: var(--sl-spacing-small);"
            >
              <sl-icon name="key"></sl-icon> Gateway API Keys
            </h3>

            <div
              style="background: var(--sl-color-neutral-50); padding: var(--sl-spacing-medium); border-radius: var(--sl-border-radius-medium); display: flex; align-items: center; justify-content: space-between; border: 1px solid var(--sl-color-neutral-200);"
            >
              <div>
                <div
                  style="font-size: var(--sl-font-size-x-small); font-weight: bold; color: var(--sl-color-neutral-500); text-transform: uppercase;"
                >
                  Global Gateway Key
                </div>
                <code style="font-family: var(--sl-font-mono);"
                  >pl_test_••••••••••••••••••••••••••••</code
                >
              </div>
              <sl-button variant="text">Copy</sl-button>
            </div>

            <div
              style="margin-top: var(--sl-spacing-large); border-left: 4px solid var(--sl-color-warning-500); padding-left: var(--sl-spacing-medium); color: var(--sl-color-neutral-600); font-size: var(--sl-font-size-small);"
            >
              <strong>Security Protocol:</strong> Each agent requires a unique
              API key for gateway routing. Do not reuse keys across different
              workforce units. Use the
              <code style="color: var(--sl-color-primary-600);"
                >preloop keys create</code
              >
              command to generate scoped credentials.
            </div>
          </div>
        </sl-tab-panel>
      </sl-tab-group>
    `;
  }
}
