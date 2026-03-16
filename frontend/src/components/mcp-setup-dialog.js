var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/dialog/dialog.js';
import './ide-setup-tabs';
import { getIdeConfigs } from '../utils/ide-configs';
let MCPSetupDialog = class MCPSetupDialog extends LitElement {
    constructor() {
        super(...arguments);
        this.open = false;
    }
    render() {
        return html `
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
    _handleClose() {
        this.dispatchEvent(new CustomEvent('close'));
    }
};
MCPSetupDialog.styles = css `
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
__decorate([
    property({ type: Boolean })
], MCPSetupDialog.prototype, "open", void 0);
MCPSetupDialog = __decorate([
    customElement('mcp-setup-dialog')
], MCPSetupDialog);
export { MCPSetupDialog };
