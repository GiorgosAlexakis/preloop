var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import consoleStyles from '../styles/console-styles.css?inline';
let ViewHeader = class ViewHeader extends LitElement {
    constructor() {
        super(...arguments);
        this.headerText = '';
        this.width = '';
    }
    render() {
        return html `
      <div class="column-layout ${this.width}">
        <div class="main-column">
          <div class="header">
            <h1>${this.headerText}</h1>
            <slot name="main-column"></slot>
          </div>
        </div>
      </div>
    `;
    }
};
ViewHeader.styles = [unsafeCSS(consoleStyles), css ``];
__decorate([
    property({ type: String })
], ViewHeader.prototype, "headerText", void 0);
__decorate([
    property({ type: String })
], ViewHeader.prototype, "width", void 0);
ViewHeader = __decorate([
    customElement('view-header')
], ViewHeader);
export { ViewHeader };
