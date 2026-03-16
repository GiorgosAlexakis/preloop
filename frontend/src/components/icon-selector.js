var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
let IconSelector = class IconSelector extends LitElement {
    constructor() {
        super(...arguments);
        this.selectedIcon = 'gear';
        this.icons = [
            'gear',
            'file-earmark-text',
            'tag',
            'bug',
            'lightbulb',
            'rocket',
        ];
    }
    render() {
        return html `
      <div class="icon-grid">
        ${this.icons.map((icon) => html `
            <div
              class="icon-wrapper ${this.selectedIcon === icon
            ? 'selected'
            : ''}"
              @click=${() => this.selectIcon(icon)}
            >
              <sl-icon name=${icon} style="font-size: 24px;"></sl-icon>
            </div>
          `)}
        <div class="icon-wrapper" @click=${() => this.uploadIcon()}>
          <sl-icon name="upload" style="font-size: 24px;"></sl-icon>
        </div>
      </div>
    `;
    }
    selectIcon(icon) {
        this.selectedIcon = icon;
        this.dispatchEvent(new CustomEvent('icon-change', { detail: { icon } }));
    }
    uploadIcon() {
        // TODO: Implement file upload
        alert('File upload not yet implemented');
    }
};
IconSelector.styles = css `
    .icon-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(48px, 1fr));
      gap: 8px;
    }
    .icon-wrapper {
      display: flex;
      justify-content: center;
      align-items: center;
      width: 48px;
      height: 48px;
      border: 1px solid var(--sl-color-neutral-200);
      border-radius: var(--sl-border-radius-medium);
      cursor: pointer;
    }
    .icon-wrapper.selected {
      border-color: var(--sl-color-primary-500);
    }
  `;
__decorate([
    property()
], IconSelector.prototype, "selectedIcon", void 0);
IconSelector = __decorate([
    customElement('icon-selector')
], IconSelector);
export { IconSelector };
