var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css } from 'lit';
import { customElement, state } from 'lit/decorators.js';
import { formStyles } from '../../styles/form-styles';
import '@shoelace-style/shoelace/dist/components/input/input.js';
import '@shoelace-style/shoelace/dist/components/select/select.js';
import '@shoelace-style/shoelace/dist/components/option/option.js';
import '@shoelace-style/shoelace/dist/components/checkbox/checkbox.js';
import '@shoelace-style/shoelace/dist/components/textarea/textarea.js';
import '@shoelace-style/shoelace/dist/components/button/button.js';
import '@shoelace-style/shoelace/dist/components/alert/alert.js';
import '../../components/logo-component';
let RequestDemoView = class RequestDemoView extends LitElement {
    constructor() {
        super(...arguments);
        this._name = '';
        this._email = '';
        this._role = '';
        this._organization = '';
        this._headcount = '';
        this._trackers = [];
        this._comments = '';
        this._submitting = false;
        this._error = null;
        this._success = false;
    }
    _handleTrackerChange(event) {
        const checkbox = event.target;
        if (checkbox.checked) {
            this._trackers = [...this._trackers, checkbox.value];
        }
        else {
            this._trackers = this._trackers.filter((t) => t !== checkbox.value);
        }
    }
    async _handleSubmit(event) {
        event.preventDefault();
        this._submitting = true;
        this._error = null;
        this._success = false;
        // In a real app, you would send this data to your backend.
        console.log('Submitting demo request:', {
            name: this._name,
            email: this._email,
            role: this._role,
            organization: this._organization,
            headcount: this._headcount,
            trackers: this._trackers,
            comments: this._comments,
        });
        const response = await fetch('https://spacecode.ai/api/v1/leads', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                name: this._name,
                email: this._email,
                role: this._role,
                org: this._organization,
                headcount: this._headcount,
                trackers: this._trackers,
                comments: this._comments,
                source: 'request-demo preloop',
            }),
        });
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        this._submitting = false;
        this._success = true;
    }
    render() {
        if (this._success) {
            return html `
        <div class="container">
          <sl-alert variant="success" open>
            <sl-icon slot="icon" name="check2-circle"></sl-icon>
            <strong>Thank you!</strong><br />
            Your demo request has been received. We'll be in touch shortly.
          </sl-alert>
        </div>
      `;
        }
        return html `
      <div class="container">
        <div class="logo">
          <a href="/">
            <logo-component></logo-component>
          </a>
        </div>
        <div class="form-container">
          <h2>Request a Demo</h2>
          <form @submit=${this._handleSubmit}>
            <sl-input
              label="Full Name"
              required
              .value=${this._name}
              @sl-input=${(e) => (this._name = e.target.value)}
            ></sl-input>

            <sl-input
              label="Work Email"
              type="email"
              required
              .value=${this._email}
              @sl-input=${(e) => (this._email = e.target.value)}
            ></sl-input>

            <sl-input
              label="Role"
              required
              .value=${this._role}
              @sl-input=${(e) => (this._role = e.target.value)}
            ></sl-input>

            <sl-input
              label="Organization"
              required
              .value=${this._organization}
              @sl-input=${(e) => (this._organization = e.target.value)}
            ></sl-input>

            <sl-select
              label="Headcount"
              required
              .value=${this._headcount}
              @sl-change=${(e) => (this._headcount = e.target.value)}
            >
              <sl-option value="1-50">1-50</sl-option>
              <sl-option value="51-200">51-200</sl-option>
              <sl-option value="201-1000">201-1,000</sl-option>
              <sl-option value="1001-5000">1,001-5,000</sl-option>
              <sl-option value="5000+">5,000+</sl-option>
            </sl-select>

            <div class="tracker-group">
              <label>Trackers Used</label>
              <sl-checkbox
                value="GitHub"
                @sl-change=${this._handleTrackerChange}
                >GitHub</sl-checkbox
              >
              <sl-checkbox
                value="GitLab"
                @sl-change=${this._handleTrackerChange}
                >GitLab</sl-checkbox
              >
              <sl-checkbox value="Jira" @sl-change=${this._handleTrackerChange}
                >Jira</sl-checkbox
              >
              <sl-checkbox
                value="Linear"
                @sl-change=${this._handleTrackerChange}
                >Linear</sl-checkbox
              >
            </div>

            <sl-textarea
              label="Additional Comments"
              resize="auto"
              .value=${this._comments}
              @sl-input=${(e) => (this._comments = e.target.value)}
            ></sl-textarea>

            ${this._error
            ? html `<sl-alert variant="danger" open>${this._error}</sl-alert>`
            : ''}

            <sl-button
              type="submit"
              variant="primary"
              ?loading=${this._submitting}
            >
              Request Demo
            </sl-button>
          </form>
        </div>
      </div>
    `;
    }
};
RequestDemoView.styles = [
    formStyles,
    css `
      h1 {
        text-align: center;
        margin-bottom: 2rem;
      }
      sl-input,
      sl-select {
        margin: 1rem 0;
      }
      .tracker-group {
        margin-bottom: 1.5rem;
        display: flex;
        flex-direction: column;
        gap: var(--sl-spacing-small);
      }
      sl-checkbox {
        display: block;
      }
      sl-button {
        width: 100%;
        margin-top: 2rem;
      }
    `,
];
__decorate([
    state()
], RequestDemoView.prototype, "_name", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_email", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_role", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_organization", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_headcount", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_trackers", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_comments", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_submitting", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_error", void 0);
__decorate([
    state()
], RequestDemoView.prototype, "_success", void 0);
RequestDemoView = __decorate([
    customElement('request-demo-view')
], RequestDemoView);
export { RequestDemoView };
