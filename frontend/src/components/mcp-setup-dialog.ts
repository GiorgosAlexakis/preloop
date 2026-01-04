import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import './ide-setup-tabs';
import { getIdeConfigs } from '../utils/ide-configs';

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
        <ide-setup-tabs
          .configs=${getIdeConfigs()}
          defaultTab="claude-code"
          helpText="The built-in MCP server provides access to all your enabled tools, including tools from external MCP servers."
        ></ide-setup-tabs>
      </sl-dialog>
    `;
  }

  private _handleClose() {
    this.dispatchEvent(new CustomEvent('close'));
  }
}
