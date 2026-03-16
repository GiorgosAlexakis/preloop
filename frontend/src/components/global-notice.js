var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
let GlobalNotice = class GlobalNotice extends LitElement {
    constructor() {
        super(...arguments);
        this._message = '';
    }
    connectedCallback() {
        super.connectedCallback();
        this._checkUrlForMessage();
    }
    _checkUrlForMessage() {
        const urlParams = new URLSearchParams(window.location.search);
        const message = urlParams.get('message');
        if (message) {
            this._message = message.replace(/_/g, ' '); // Replace underscores with spaces
            // Clean the URL after we have captured the message
            const newUrl = `${window.location.pathname}`;
            window.history.replaceState({}, '', newUrl);
        }
    }
    _handleClose() {
        this._message = '';
    }
    render() {
        if (!this._message) {
            return html ``;
        }
        return html `
      <sl-alert
        class="notice"
        variant="primary"
        closable
        open
        @sl-hide=${this._handleClose}
      >
        <sl-icon slot="icon" name="info-circle"></sl-icon>
        ${this._message}
      </sl-alert>
    `;
    }
};
GlobalNotice.styles = css `
    .notice {
      position: fixed;
      top: 1rem;
      right: 1rem;
      z-index: 1000;
    }
  `;
__decorate([
    state()
], GlobalNotice.prototype, "_message", void 0);
GlobalNotice = __decorate([
    customElement('global-notice')
], GlobalNotice);
export { GlobalNotice };
