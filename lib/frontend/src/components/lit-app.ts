import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { router } from '../router';
import { webSocketService } from '../services/websocket-service';
import '../views/public/landing-view.ts';
import '../views/public/login-view.ts';
import '../views/public/register-view.ts';
import '../views/public/forgot-password-view.ts';
import '../views/public/reset-password-view.ts';
import '../views/public/verify-email-view.ts';
import '../views/public/request-demo-view.ts';
import '../views/public/whatis-mcp-view.ts';
import '../views/public/pricing-view.ts';
import '../views/public/welcome-view.ts';
import '../views/public/static-view.ts';
import '../views/authed/console-shell.ts';
import '../views/authed/dashboard-view.ts';
import '../views/authed/trackers-view.ts';
import '../views/authed/issues-view.ts';
import '../views/authed/issues-compliance-view.ts';
import '../views/authed/issues-dependencies-view.ts';
import '../views/authed/issues/duplicates-view.ts';
import '../views/authed/issues/assignments-view.ts';
import '../views/authed/api-usage-view.ts';
import '../views/authed/settings-view.ts';
import '../views/authed/settings/api-keys-view.ts';
import '../views/authed/settings/ai-models-view.ts';
import '../views/authed/settings/profile-view.ts';
import '../views/authed/settings/security-view.ts';
import '../views/authed/settings/appearance-view.ts';
import '../views/authed/settings/subscription-view.ts';
import '../views/authed/flows-view.ts';
import '../views/authed/flow-view.ts';
import '../views/authed/flow-executions-view.ts';
import '../views/authed/flow-execution-view.ts';
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
    this.connectWebSocket();
    this.setupEventListeners();
    router.setOutlet(this.renderRoot.querySelector('main'));
    router.setRoutes([
      { path: '/', component: 'landing-view' },
      { path: '/login', component: 'login-view' },
      { path: '/register', component: 'register-view' },
      { path: '/forgot-password', component: 'forgot-password-view' },
      { path: '/reset-password', component: 'reset-password-view' },
      { path: '/verify-email', component: 'verify-email-view' },
      { path: '/request-demo', component: 'request-demo-view' },
      { path: '/whatis-mcp', component: 'whatis-mcp-view' },
      {
        path: '/docs',
        action: (context, commands) => {
          const view = commands.component('static-view') as any;
          view.src = '/content/docs.md';
          return view;
        },
      },
      {
        path: '/terms',
        action: (context, commands) => {
          const view = commands.component('static-view') as any;
          view.src = '/content/terms.md';
          return view;
        },
      },
      {
        path: '/privacy',
        action: (context, commands) => {
          const view = commands.component('static-view') as any;
          view.src = '/content/privacy.md';
          return view;
        },
      },
      { path: '/pricing', component: 'public-pricing-view' },
      { path: '/welcome', component: 'welcome-view' },
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
              { path: 'compliance', component: 'issues-compliance-view' },
              { path: 'dependencies', component: 'issues-dependencies-view' },
              { path: 'duplicates', component: 'duplicates-view' },
              { path: 'assignments', component: 'assignments-view' },
            ],
          },
          {
            path: 'flows',
            children: [
              { path: '', component: 'flows-view' },
              { path: 'new', component: 'flow-view' },
              { path: ':flowId', component: 'flow-view' },
              { path: 'executions', component: 'flow-executions-view' },
              {
                path: 'executions/:executionId',
                component: 'flow-execution-view',
              },
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
              { path: 'ai-models', component: 'ai-models-view' },
              { path: 'appearance', component: 'appearance-view' },
              { path: 'subscription', component: 'subscription-view' },
            ],
          },
          { path: 'pricing', component: 'pricing-view' },
        ],
      },
    ]);
  }

  render() {
    return html` <main></main> `;
  }

  connectWebSocket() {
    const wsUrl = `ws${window.location.protocol === 'https:' ? 's' : ''}://${window.location.host}/api/v1/ws`;
    webSocketService.connect(wsUrl, (message) => {
      // Handle incoming messages from the server
      // For now, we just log them
      console.log('Received message:', message);
    });
  }

  setupEventListeners() {
    this.addEventListener('click', (e) => this.trackEvent('click', e));
    // Add other event listeners as needed
  }

  trackEvent(type: string, event: Event) {
    const target = event.target as HTMLElement;
    const payload = {
      type,
      target: {
        id: target.id,
        tagName: target.tagName,
        innerText: target.innerText.slice(0, 100), // Limit text length
      },
      path: window.location.pathname,
    };
    webSocketService.send(payload);
  }
}
