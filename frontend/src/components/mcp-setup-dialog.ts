import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

type SetupTab = 'claude-code' | 'codex-cli' | 'gemini-cli' | 'ide-json';

@customElement('mcp-setup-dialog')
export class MCPSetupDialog extends LitElement {
  static styles = css`
    .client-tabs {
      display: flex;
      justify-content: center;
      gap: 0.75rem;
      margin: 1.5rem 0 1.75rem 0;
      flex-wrap: wrap;
    }

    .intro {
      margin-bottom: 1rem;
      color: var(--sl-color-neutral-700);
      line-height: 1.5;
    }

    .intro strong {
      color: var(--sl-color-neutral-900);
    }

    .prereq {
      padding: 0.75rem;
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: 10px;
      background: var(--sl-color-neutral-0);
      margin-bottom: 1rem;
    }

    .prereq-title {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-bottom: 0.25rem;
    }

    .prereq-title h5 {
      margin: 0;
    }

    .prereq-link {
      color: var(--sl-color-primary-700);
      text-decoration: none;
      font-weight: 600;
      font-size: 0.875rem;
    }

    .prereq-link:hover {
      text-decoration: underline;
    }

    .client-tab {
      cursor: pointer;
      padding: 0.75rem 1rem;
      border-radius: 12px;
      transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      border: 1px solid var(--sl-color-neutral-200);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      background: var(--sl-color-neutral-0);
      box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    }

    .client-tab:hover {
      background: var(--sl-color-neutral-50);
      transform: translateY(-2px);
    }

    .client-tab.active {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
      box-shadow:
        0 0 0 1px var(--sl-color-primary-600),
        0 2px 4px rgba(var(--sl-color-primary-600-rgb), 0.1);
    }

    .client-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border-radius: 10px;
      background: var(--sl-color-neutral-0);
      border: 1px solid var(--sl-color-neutral-200);
      overflow: hidden;
      padding: 6px;
    }

    .client-icon img {
      height: 100%;
      width: 100%;
      object-fit: contain;
    }

    .client-label {
      font-weight: 600;
      color: var(--sl-color-neutral-900);
      font-size: 0.95rem;
      white-space: nowrap;
    }

    .client-logo-text {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      height: 20px;
      padding: 0 0.4rem;
      font-weight: 600;
      color: var(--sl-color-neutral-900);
      background: transparent;
      border-radius: 6px;
      letter-spacing: 0.2px;
      font-size: 0.9rem;
      white-space: nowrap;
    }

    .tab-content {
      margin-top: 1rem;
    }

    .tab-content h5 {
      margin: 1rem 0 0.5rem 0;
      color: var(--sl-color-neutral-700);
    }

    .tab-content h5:first-child {
      margin-top: 0;
    }

    .tab-content ul {
      margin: 0.5rem 0;
      padding-left: 1.5rem;
    }

    .tab-content li {
      margin: 0.25rem 0;
    }

    .tab-content p {
      margin: 0.5rem 0;
    }

    .tab-content code {
      background: var(--sl-color-neutral-100);
      padding: 0.125rem 0.375rem;
      border-radius: 3px;
      font-family: monospace;
      font-size: 0.875em;
    }

    .tab-content pre {
      background: var(--sl-color-neutral-100);
      padding: 0.75rem;
      border-radius: 4px;
      overflow-x: auto;
      font-size: 0.75rem;
      margin: 0.5rem 0;
    }

    .tab-content pre code {
      background: none;
      padding: 0;
    }

    .help-text {
      color: var(--sl-color-neutral-600);
      font-size: 0.875rem;
      margin: 0;
    }

    .step {
      padding: 0.75rem;
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: 8px;
      background: var(--sl-color-neutral-0);
      margin: 0.75rem 0;
    }

    .step-title {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 0.75rem;
      margin-bottom: 0.5rem;
    }

    .step-title h5 {
      margin: 0;
    }

    .code-block {
      position: relative;
    }

    .code-actions {
      display: flex;
      justify-content: flex-end;
      margin-top: 0.5rem;
    }
  `;

  @property({ type: Boolean })
  open = false;

  @state()
  private activeTab: SetupTab = 'claude-code';

  @state()
  private copiedKey: string | null = null;

  render() {
    const mcpUrl = `${window.location.origin}/mcp/v1`;
    const envVarName = 'PRELOOP_API_KEY';

    return html`
      <sl-dialog
        label="Setup Instructions"
        class="setup-dialog"
        ?open=${this.open}
        @sl-hide=${() => this._handleClose()}
        style="--width: 50rem;"
      >
        <div class="intro">
          Connect your IDE or CLI to the <strong>Preloop MCP server</strong> to
          use your enabled tools.
          <div style="margin-top: 0.5rem;">MCP URL: <code>${mcpUrl}</code></div>
        </div>

        <div class="prereq">
          <div class="prereq-title">
            <h5>Prerequisite: Create an API key</h5>
            <a class="prereq-link" href="/console/settings/api-keys"
              >Settings → API Keys</a
            >
          </div>
          <p class="help-text">
            You’ll use this key as a bearer token when connecting MCP clients.
          </p>
        </div>

        <div class="client-tabs">
          <div
            class="client-tab ${this.activeTab === 'claude-code'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('claude-code')}
          >
            <span class="client-icon">
              <img src="/images/logos/claude.svg" alt="Claude Code" />
            </span>
            <span class="client-label">Claude Code</span>
          </div>

          <div
            class="client-tab ${this.activeTab === 'codex-cli' ? 'active' : ''}"
            @click=${() => this._handleTabClick('codex-cli')}
          >
            <span class="client-icon">
              <img src="/images/logos/openai.svg" alt="OpenAI" />
            </span>
            <span class="client-label">Codex CLI</span>
          </div>

          <div
            class="client-tab ${this.activeTab === 'gemini-cli'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('gemini-cli')}
          >
            <span class="client-icon">
              <img src="/images/logos/gemini-cli.png" alt="Gemini" />
            </span>
            <span class="client-label">Gemini CLI</span>
          </div>

          <div
            class="client-tab ${this.activeTab === 'ide-json' ? 'active' : ''}"
            @click=${() => this._handleTabClick('ide-json')}
          >
            <span class="client-icon">
              <img src="/images/logos/vscode.svg" alt="VSCode" />
            </span>
            <span class="client-label"
              >VSCode <br /><small
                >Cursor / Windsurf / Antigravity / etc.</small
              ></span
            >
          </div>
        </div>

        <div class="tab-content">
          ${this.activeTab === 'claude-code'
            ? html`
                <div>
                  <div class="step">
                    <div class="step-title">
                      <h5>Setup</h5>
                    </div>
                    <p class="help-text">
                      Export your API key as an environment variable, then add
                      the MCP server.
                    </p>
                    <div class="code-block">
                      <pre><code>export ${envVarName}="YOUR_API_KEY_HERE"

claude mcp add --transport http preloop ${mcpUrl} --header "Authorization: Bearer $${envVarName}"</code></pre>
                      <div class="code-actions">
                        <sl-button
                          size="small"
                          @click=${() =>
                            this._copy(
                              `export ${envVarName}="YOUR_API_KEY_HERE"\n\nclaude mcp add --transport http preloop ${mcpUrl} --header "Authorization: Bearer $${envVarName}"`,
                              'claude'
                            )}
                          >${this.copiedKey === 'claude'
                            ? 'Copied'
                            : 'Copy'}</sl-button
                        >
                      </div>
                    </div>
                    <p class="help-text">
                      Replace <code>YOUR_API_KEY_HERE</code> with your actual
                      Preloop API key.
                    </p>
                  </div>
                </div>
              `
            : ''}
          ${this.activeTab === 'gemini-cli'
            ? html`
                <div>
                  <div class="step">
                    <div class="step-title">
                      <h5>Setup</h5>
                    </div>
                    <p class="help-text">
                      Install the MCP server using the Gemini CLI.
                    </p>
                    <div class="code-block">
                      <pre><code>export ${envVarName}="YOUR_API_KEY_HERE"

gemini mcp add preloop ${mcpUrl} --header "Authorization: Bearer $${envVarName}"</code></pre>
                      <div class="code-actions">
                        <sl-button
                          size="small"
                          @click=${() =>
                            this._copy(
                              `export ${envVarName}="YOUR_API_KEY_HERE"\n\ngemini mcp add preloop ${mcpUrl} --header "Authorization: Bearer $${envVarName}"`,
                              'gemini'
                            )}
                          >${this.copiedKey === 'gemini'
                            ? 'Copied'
                            : 'Copy'}</sl-button
                        >
                      </div>
                    </div>
                    <p class="help-text">
                      Replace <code>YOUR_API_KEY_HERE</code> with your actual
                      Preloop API key.
                    </p>
                  </div>
                </div>
              `
            : ''}
          ${this.activeTab === 'codex-cli'
            ? html`
                <div>
                  <div class="step">
                    <div class="step-title">
                      <h5>Setup</h5>
                    </div>
                    <p class="help-text">
                      Codex supports Streamable HTTP MCP servers via
                      <code>url</code>. Use <code>bearer_token_env_var</code> so
                      you don’t have to store secrets in the file.
                    </p>
                    <div class="code-block">
                      <pre><code>[mcp_servers.preloop]
url = "${mcpUrl}"
bearer_token_env_var = "${envVarName}"
</code></pre>
                      <div class="code-actions">
                        <sl-button
                          size="small"
                          @click=${() =>
                            this._copy(
                              `[mcp_servers.preloop]\nurl = "${mcpUrl}"\nbearer_token_env_var = "${envVarName}"\n`,
                              'codex-toml'
                            )}
                          >${this.copiedKey === 'codex-toml'
                            ? 'Copied'
                            : 'Copy'}</sl-button
                        >
                      </div>
                    </div>

                    <div class="code-block">
                      <pre><code>export ${envVarName}="YOUR_API_KEY_HERE"</code></pre>
                      <div class="code-actions">
                        <sl-button
                          size="small"
                          @click=${() =>
                            this._copy(
                              `export ${envVarName}="YOUR_API_KEY_HERE"`,
                              'codex-env'
                            )}
                          >${this.copiedKey === 'codex-env'
                            ? 'Copied'
                            : 'Copy'}</sl-button
                        >
                      </div>
                    </div>

                    <p class="help-text">
                      Then run <code>codex</code> and use <code>/mcp</code> in
                      the TUI to verify the server is connected.
                    </p>
                  </div>
                </div>
              `
            : ''}
          ${this.activeTab === 'ide-json'
            ? html`
                <div>
                  <div class="step">
                    <div class="step-title">
                      <h5>Setup (JSON MCP config)</h5>
                    </div>
                    <p class="help-text" style="margin-bottom: 0.5rem;">
                      This configuration works for:
                    </p>
                    <ul>
                      <li>Cursor</li>
                      <li>Windsurf</li>
                      <li>VSCode (vanilla)</li>
                      <li>Antigravity</li>
                    </ul>

                    <p class="help-text">Add this to your MCP settings:</p>
                    <div class="code-block">
                      <pre><code>{
  "mcpServers": {
    "preloop": {
      "url": "${mcpUrl}",
      "transport": "http-streaming",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}</code></pre>
                      <div class="code-actions">
                        <sl-button
                          size="small"
                          @click=${() =>
                            this._copy(
                              `{
  "mcpServers": {
    "preloop": {
      "url": "${mcpUrl}",
      "transport": "http-streaming",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY_HERE"
      }
    }
  }
}`,
                              'ide-json'
                            )}
                          >${this.copiedKey === 'ide-json'
                            ? 'Copied'
                            : 'Copy'}</sl-button
                        >
                      </div>
                    </div>
                    <p class="help-text">
                      Replace <code>YOUR_API_KEY_HERE</code> with your actual
                      Preloop API key.
                    </p>
                  </div>
                </div>
              `
            : ''}
        </div>

        <p class="help-text" style="margin-top: var(--sl-spacing-medium);">
          The built-in MCP server provides access to all your enabled tools,
          including tools from external MCP servers.
        </p>
        <sl-button
          slot="footer"
          variant="primary"
          @click=${() => this._handleClose()}
        >
          Close
        </sl-button>
      </sl-dialog>
    `;
  }

  private _handleTabClick(tab: SetupTab) {
    this.activeTab = tab;
  }

  private _handleClose() {
    this.dispatchEvent(new CustomEvent('close'));
  }

  private async _copy(text: string, key: string) {
    try {
      await navigator.clipboard.writeText(text);
      this.copiedKey = key;
      window.setTimeout(() => {
        if (this.copiedKey === key) {
          this.copiedKey = null;
        }
      }, 1200);
    } catch {
      this.copiedKey = null;
    }
  }
}
