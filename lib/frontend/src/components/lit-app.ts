import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { router } from '../router';
import '../views/public/landing-view.ts';
import '../views/public/login-view.ts';
import '../views/public/register-view.ts';
import '../views/public/forgot-password-view.ts';
import '../views/public/request-demo-view.ts';
import '../views/public/whatis-mcp-view.ts';
import '../views/authed/console-shell.ts';
import '../views/authed/dashboard-view.ts';
import '../views/authed/trackers-view.ts';
import '../views/authed/issues-view.ts';
import '../views/authed/issues/duplicates-view.ts';
import '../views/authed/issues/assignments-view.ts';
import '../views/authed/api-usage-view.ts';
import '../views/authed/settings-view.ts';
import '../views/authed/settings/api-keys-view.ts';
import '../views/authed/settings/llm-models-view.ts';
import '../views/authed/settings/profile-view.ts';
import '../views/authed/settings/security-view.ts';
import './app-header.ts';
import './app-footer.ts';

@customElement('lit-app')
export class LitApp extends LitElement {
  static styles = css`
    :host {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    main {
      flex: 1;
      overflow-y: auto;
    }
  `;

  firstUpdated() {
    router.setOutlet(this.renderRoot.querySelector('main'));
    router.setRoutes([
      { path: '/', component: 'landing-view' },
      { path: '/login', component: 'login-view' },
      { path: '/register', component: 'register-view' },
      { path: '/forgot-password', component: 'forgot-password-view' },
      { path: '/request-demo', component: 'request-demo-view' },
      { path: '/whatis-mcp', component: 'whatis-mcp-view' },
      {
        path: '/console',
        component: 'console-shell',
        action: () => {
          // This is where you would add authentication checks
        },
        children: [
          { path: '', component: 'dashboard-view' },
          { path: 'trackers', component: 'trackers-view' },
          {
            path: 'issues',
            children: [
              { path: '', component: 'issues-view' },
              { path: 'duplicates', component: 'duplicates-view' },
              { path: 'assignments', component: 'assignments-view' },
            ],
          },
          { path: '/api-usage', component: 'api-usage-view' },
          {
            path: 'settings',
            children: [
              { path: '', component: 'settings-view' },
              { path: 'profile', component: 'profile-view' },
              { path: 'security', component: 'security-view' },
              { path: 'api-keys', component: 'api-keys-view' },
              { path: 'llm-models', component: 'llm-models-view' },
            ],
          },
        ],
      },
    ]);
  }

  render() {
    return html` <main></main> `;
  }
}
