var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
let NewsCapsule = class NewsCapsule extends LitElement {
    constructor() {
        super(...arguments);
        this.newsItem = {
            label: 'New',
            text: 'Compliance Suggestions and Improved Reasoning',
            link: '/features/compliance',
        };
    }
    render() {
        return html `
      <a href="${this.newsItem.link}" class="capsule">
        <span class="label">${this.newsItem.label}</span>
        <span class="text">${this.newsItem.text}</span>
        <sl-icon name="arrow-right" class="arrow"></sl-icon>
      </a>
    `;
    }
};
NewsCapsule.styles = css `
    :host {
      display: block;
      text-align: center;
      margin-top: -4rem;
      margin-bottom: 4rem;
    }
    .capsule {
      display: inline-flex;
      align-items: center;
      gap: 0.75rem;
      background-color: rgba(255, 255, 255, 0.05);
      color: var(--sl-color-neutral-800);
      padding: 0.75rem 1.25rem;
      border-radius: 9999px;
      font-size: var(--sl-font-size-medium);
      text-decoration: none;
      transition: all 0.3s ease;
      border: 1px solid rgba(255, 255, 255, 0.1);
      backdrop-filter: blur(10px);
      box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    .capsule:hover {
      background-color: rgba(255, 255, 255, 0.1);
      border-color: rgba(255, 255, 255, 0.2);
      transform: translateY(-2px);
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
    }
    .label {
      font-weight: 600;
      background-color: var(--sl-color-primary-500);
      color: white;
      padding: 0.25rem 0.6rem;
      border-radius: 9999px;
      font-size: var(--sl-font-size-x-small);
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .text {
      font-weight: 400;
    }
    .arrow {
      color: var(--sl-color-neutral-600);
      transition: transform 0.3s ease;
    }
    .capsule:hover .arrow {
      transform: translateX(3px);
      color: var(--sl-color-neutral-800);
    }
  `;
__decorate([
    property({ type: Object })
], NewsCapsule.prototype, "newsItem", void 0);
NewsCapsule = __decorate([
    customElement('news-capsule')
], NewsCapsule);
export { NewsCapsule };
