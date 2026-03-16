var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { Router } from '@vaadin/router';
import { router } from '../../router';
import '@shoelace-style/shoelace/dist/components/tab-group/tab-group.js';
import '@shoelace-style/shoelace/dist/components/tab/tab.js';
let SettingsView = class SettingsView extends LitElement {
    constructor() {
        super(...arguments);
        this.location = router.location;
        this.tabs = [
            { path: '/console/settings/profile', label: 'Profile' },
            { path: '/console/settings/security', label: 'Security' },
            { path: '/console/settings/subscription', label: 'Subscription' },
            { path: '/console/settings/api-keys', label: 'API Keys' },
            { path: '/console/settings/ai-models', label: 'AI Models' },
            { path: '/console/settings/appearance', label: 'Appearance' },
        ];
    }
    onTabSelected(e) {
        const tab = e.detail.tab;
        Router.go(tab.panel);
    }
    render() {
        return html `
      <sl-tab-group @sl-tab-select=${this.onTabSelected}>
        ${this.tabs.map((tab) => html `<sl-tab panel=${tab.path}>${tab.label}</sl-tab>`)}
      </sl-tab-group>
      <slot></slot>
    `;
    }
};
SettingsView.styles = css `
    :host {
      display: block;
      padding: var(--lumo-space-l);
    }
    sl-tab-group {
      margin-bottom: var(--lumo-space-l);
    }
  `;
__decorate([
    state()
], SettingsView.prototype, "location", void 0);
SettingsView = __decorate([
    customElement('settings-view')
], SettingsView);
export { SettingsView };
