import { LitElement, html, css } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';

type SetupTab = 'claude-code' | 'cursor' | 'windsurf' | 'aider';

@customElement('mcp-setup-dialog')
export class MCPSetupDialog extends LitElement {
  static styles = css`
    .ide-tabs {
      display: flex;
      justify-content: center;
      gap: 1rem;
      margin-bottom: 1.5rem;
      flex-wrap: wrap;
    }

    .ide-logo-container {
      cursor: pointer;
      padding: 0.75rem;
      border-radius: 8px;
      transition: all 0.2s ease;
      border: 2px solid transparent;
    }

    .ide-logo-container:hover {
      background: var(--sl-color-neutral-50);
      transform: translateY(-2px);
    }

    .ide-logo-container.active {
      border-color: var(--sl-color-primary-600);
      background: var(--sl-color-primary-50);
    }

    .ide-logo-container img {
      display: block;
      height: 40px;
      width: auto;
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
  `;

  @property({ type: Boolean })
  open = false;

  @state()
  private activeTab: SetupTab = 'claude-code';

  render() {
    const mcpUrl = `${window.location.origin}/mcp/v1`;

    return html`
      <sl-dialog
        label="Setup Instructions"
        class="setup-dialog"
        ?open=${this.open}
        @sl-hide=${() => this._handleClose()}
        style="--width: 50rem;"
      >
        <div class="ide-tabs">
          <div
            class="ide-logo-container ${this.activeTab === 'claude-code'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('claude-code')}
          >
            <img src="/images/Claude_AI_logo.png" alt="Claude Code" />
          </div>
          <div
            class="ide-logo-container ${this.activeTab === 'cursor'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('cursor')}
          >
            <img src="/images/cursor_logo.png" alt="Cursor" />
          </div>
          <div
            class="ide-logo-container ${this.activeTab === 'windsurf'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('windsurf')}
          >
            <img src="/images/windsurf_logo.png" alt="Windsurf" />
          </div>
          <div
            class="ide-logo-container ${this.activeTab === 'aider'
              ? 'active'
              : ''}"
            @click=${() => this._handleTabClick('aider')}
          >
            <img src="/images/aider_logo.svg" alt="Aider CE" />
          </div>
        </div>

        <div class="tab-content">
          ${this.activeTab === 'claude-code'
            ? html`
                <div>
                  <h5>Prerequisites</h5>
                  <ul>
                    <li>
                      Preloop AI API key (create one in Settings → API Keys)
                    </li>
                    <li>Claude Code CLI</li>
                  </ul>
                  <h5>Setup</h5>
                  <p>
                    Run this command in your terminal to add Preloop AI to
                    Claude Code:
                  </p>
                  <pre><code>claude mcp add --transport http preloop ${mcpUrl} --header "Authorization: Bearer YOUR_API_KEY_HERE"</code></pre>
                  <p style="margin-top: 1rem;">
                    Replace <code>YOUR_API_KEY_HERE</code> with your actual
                    Preloop AI API key.
                  </p>
                </div>
              `
            : ''}
          ${this.activeTab === 'cursor'
            ? html`
                <div>
                  <h5>Prerequisites</h5>
                  <ul>
                    <li>
                      Preloop AI API key (create one in Settings → API Keys)
                    </li>
                    <li>Cursor IDE</li>
                  </ul>
                  <h5>Setup</h5>
                  <p>Add to your Cursor MCP settings:</p>
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
                </div>
              `
            : ''}
          ${this.activeTab === 'windsurf'
            ? html`
                <div>
                  <h5>Prerequisites</h5>
                  <ul>
                    <li>
                      Preloop AI API key (create one in Settings → API Keys)
                    </li>
                    <li>Windsurf IDE</li>
                  </ul>
                  <h5>Setup</h5>
                  <p>Add to your Windsurf MCP settings:</p>
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
                </div>
              `
            : ''}
          ${this.activeTab === 'aider'
            ? html`
                <div>
                  <h5>Prerequisites</h5>
                  <ul>
                    <li>
                      Preloop AI API key (create one in Settings → API Keys)
                    </li>
                    <li>
                      Aider CE (Community Edition with MCP support):
                      <code
                        >pip install
                        git+https://github.com/dwash96/aider-ce.git</code
                      >
                    </li>
                  </ul>
                  <h5>Setup</h5>
                  <p>Create or edit <code>~/.aider/mcp_settings.json</code>:</p>
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
                  <p style="margin-top: 1rem;">
                    <strong>Usage:</strong> Run <code>aider</code> in your
                    project directory. It will automatically load MCP tools from
                    Preloop AI.
                  </p>
                  <p
                    style="margin-top: 0.5rem; color: var(--sl-color-neutral-600); font-size: 0.875rem;"
                  >
                    Note: Aider CE is required for MCP support. The official
                    aider package does not support MCP servers.
                  </p>
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
}
