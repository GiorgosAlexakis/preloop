var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
let SettingsTabs = class SettingsTabs extends LitElement {
    constructor() {
        super(...arguments);
        this.active = '';
        this.features = {};
    }
    get tabs() {
        const hasUserMgmt = this.features['user_management'] === true;
        const allTabs = [
            { path: '/console/settings/profile', label: 'Profile' },
            { path: '/console/settings/security', label: 'Security' },
            { path: '/console/settings/account', label: 'Account', ee: true },
            { path: '/console/settings/users', label: 'Users', ee: true },
            { path: '/console/settings/teams', label: 'Teams', ee: true },
            { path: '/console/settings/invitations', label: 'Invitations', ee: true },
            { path: '/console/settings/api-keys', label: 'API Keys' },
            { path: '/console/settings/ai-models', label: 'AI Models' },
            { path: '/console/settings/appearance', label: 'Appearance' },
        ];
        return allTabs.filter((t) => !t.ee || hasUserMgmt);
    }
    onTabSelect(e) {
        const panel = e.detail.name;
        if (panel) {
            Router.go(panel);
        }
    }
    render() {
        return html `
      <sl-tab-group @sl-tab-show=${this.onTabSelect}>
        ${this.tabs.map((tab) => html `
            <sl-tab
              slot="nav"
              panel=${tab.path}
              ?active=${this.active === tab.path}
            >
              ${tab.label}
            </sl-tab>
          `)}
      </sl-tab-group>
    `;
    }
};
SettingsTabs.styles = css `
    :host {
      display: block;
      margin-bottom: 2rem;
    }
    sl-tab-group {
      --indicator-color: var(--sl-color-primary-600);
    }
  `;
__decorate([
    property({ type: String })
], SettingsTabs.prototype, "active", void 0);
__decorate([
    property({ type: Object })
], SettingsTabs.prototype, "features", void 0);
SettingsTabs = __decorate([
    customElement('settings-tabs')
], SettingsTabs);
export { SettingsTabs };
