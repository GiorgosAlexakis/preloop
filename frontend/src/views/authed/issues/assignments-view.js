var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
let AssignmentsView = class AssignmentsView extends LitElement {
    render() {
        return html ` <h1>Coming Soon</h1> `;
    }
};
AssignmentsView.styles = css `
    :host {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100%;
      color: var(--lumo-contrast-60pct);
    }
    h1 {
      font-size: var(--lumo-font-size-xxl);
    }
  `;
AssignmentsView = __decorate([
    customElement('assignments-view')
], AssignmentsView);
export { AssignmentsView };
