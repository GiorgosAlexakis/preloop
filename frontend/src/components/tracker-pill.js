var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import '@shoelace-style/shoelace/dist/components/icon/icon.js';
import '@shoelace-style/shoelace/dist/components/tag/tag.js';
let TrackerPill = class TrackerPill extends LitElement {
    getTrackerIcon(tracker) {
        const type = tracker.type?.toLowerCase() || '';
        const name = tracker.name?.toLowerCase() || '';
        if (type.includes('jira') || name.includes('jira')) {
            return 'jira';
        }
        if (type.includes('github') || name.includes('github')) {
            return 'github';
        }
        if (type.includes('gitlab') || name.includes('gitlab')) {
            return 'gitlab';
        }
        return 'box-seam';
    }
    render() {
        if (!this.tracker) {
            return html ``;
        }
        const iconName = this.getTrackerIcon(this.tracker);
        return html `
      <sl-tag size="medium" pill>
        <sl-icon name="${iconName}"></sl-icon>
        ${this.tracker.name}
      </sl-tag>
    `;
    }
};
TrackerPill.styles = css `
    sl-tag {
      display: inline-flex;
      align-items: center;
    }

    sl-icon {
      font-size: var(--sl-font-size-medium);
      margin-right: var(--sl-spacing-x-small);
    }
  `;
__decorate([
    property({ type: Object })
], TrackerPill.prototype, "tracker", void 0);
TrackerPill = __decorate([
    customElement('tracker-pill')
], TrackerPill);
export { TrackerPill };
