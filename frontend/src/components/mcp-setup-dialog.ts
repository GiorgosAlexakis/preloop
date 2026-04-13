import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';

@customElement('mcp-setup-dialog')
export class MCPSetupDialog extends LitElement {
  static styles = css`
    sl-dialog::part(panel) {
      background: transparent;
      box-shadow: none;
    }

    sl-dialog::part(body) {
      padding: 0;
    }

    sl-dialog::part(overlay) {
      backdrop-filter: blur(4px);
    }
  `;

  @property({ type: Boolean })
  open = false;

  render() {
    return html`
      <sl-dialog
        ?open=${this.open}
        @sl-hide=${() => this._handleClose()}
        style="--width: 65rem;"
      >
        <div
          style="background: var(--sl-color-neutral-950); padding: 4rem; border-radius: var(--sl-border-radius-large); color: white; text-align: left;"
        >
          <h2
            style="margin-bottom: 2rem; font-size: 2rem; text-align: center; font-weight: 500;"
          >
            Start with preloop agents discover
          </h2>
          <p
            style="text-align: center; color: var(--sl-color-neutral-400); margin-bottom: 3rem; font-size: 1.1rem;"
          >
            Install the CLI to onboard existing agents or connect them manually.
          </p>

          <div style="margin-bottom: 1.5rem;">
            <div
              style="font-weight: 600; margin-bottom: 0.5rem; color: var(--sl-color-neutral-300);"
            >
              1. Install the CLI
            </div>
            <div
              style="display: flex; align-items: center; background: #000; padding: 1rem; border-radius: var(--sl-border-radius-medium); border: 1px solid var(--sl-color-neutral-800);"
            >
              <code
                style="color: var(--sl-color-primary-400); flex: 1; font-size: 1.1rem; user-select: all;"
                >curl -fsSL https://preloop.ai/install/cli | sh</code
              >
            </div>
          </div>

          <div style="margin-bottom: 1.5rem;">
            <div
              style="font-weight: 600; margin-bottom: 0.5rem; color: var(--sl-color-neutral-300);"
            >
              2. Authenticate
            </div>
            <div
              style="display: flex; align-items: center; background: #000; padding: 1rem; border-radius: var(--sl-border-radius-medium); border: 1px solid var(--sl-color-neutral-800);"
            >
              <code
                style="color: var(--sl-color-primary-400); flex: 1; font-size: 1.1rem; user-select: all;"
                >preloop login</code
              >
            </div>
          </div>

          <div style="margin-bottom: 1.5rem;">
            <div
              style="font-weight: 600; margin-bottom: 0.5rem; color: var(--sl-color-neutral-300);"
            >
              3. Discover Agents
            </div>
            <div
              style="display: flex; align-items: center; background: #000; padding: 1rem; border-radius: var(--sl-border-radius-medium); border: 1px solid var(--sl-color-neutral-800);"
            >
              <code
                style="color: var(--sl-color-primary-400); flex: 1; font-size: 1.1rem; user-select: all;"
                >preloop agents discover</code
              >
            </div>
          </div>
        </div>
      </sl-dialog>
    `;
  }

  private _handleClose() {
    this.dispatchEvent(new CustomEvent('close'));
  }
}
