import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';
import { router } from '../router';
import '../views/public/landing-view.ts';
import './static-view-wrapper.ts';
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
import '../views/authed/tools-view.ts';
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
import '../views/authed/settings/account-view.ts';
import '../views/authed/settings/user-management-view.ts';
import '../views/authed/settings/team-management-view.ts';
import '../views/authed/settings/invitation-management-view.ts';
import '../views/authed/notification-preferences-view.ts';
import '../components/settings-tabs.ts';
import '../views/authed/flows-view.ts';
import '../views/authed/flow-view.ts';
import '../views/authed/flow-executions-view.ts';
import '../views/authed/flow-execution-view.ts';
import '../views/authed/approval-view.ts';
import './app-header.ts';
import './app-footer.ts';

@customElement('lit-app')
export class LitApp extends LitElement {
  private hasNavigated = false;

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

    const outlet = this.renderRoot.querySelector('main');
    const ssrRoute = this.getAttribute('data-ssr-route');
    const currentPath = window.location.pathname;

    // Check if SSR content matches current route
    const ssrContent = this.querySelector('landing-view, static-view-wrapper');

    if (ssrContent && ssrRoute === currentPath) {
      // SSR content matches current route - move it to outlet for router to use
      outlet?.appendChild(ssrContent);
    } else if (ssrContent) {
      // SSR content doesn't match current route - remove it
      // This happens when index.html is served for non-root routes
      ssrContent.remove();
    }

    // Always initialize router
    router.setOutlet(outlet);
    router.setRoutes([
      {
        path: '/',
        action: (context, commands) => {
          // Check if landing-view already exists (from SSR or previous navigation)
          let existingLandingView = this.querySelector('landing-view');

          // Also check if it's already in the outlet
          if (!existingLandingView) {
            const outlet = this.renderRoot.querySelector('main');
            existingLandingView = outlet?.querySelector('landing-view') || null;
          }

          if (existingLandingView) {
            // Check if it has loaded content (either visible or hidden slots)
            // Don't check children.length because _loadSlottedContent hides them
            const hasLoadedContent =
              (existingLandingView as any)._featureSlides?.length > 0 ||
              (existingLandingView as any)._faqs?.length > 0;

            if (hasLoadedContent) {
              // Reuse existing component with its state intact
              return existingLandingView;
            }
          }

          // Fallback: create new landing-view (no SSR content available)
          return commands.component('landing-view');
        },
      },
      { path: '/login', component: 'login-view' },
      { path: '/register', component: 'register-view' },
      { path: '/forgot-password', component: 'forgot-password-view' },
      { path: '/reset-password', component: 'reset-password-view' },
      { path: '/verify-email', component: 'verify-email-view' },
      { path: '/request-demo', component: 'request-demo-view' },
      {
        path: '/whatis-mcp',
        action: (context, commands) => {
          // Check if we have SSR content for this EXACT route on first load
          const outlet = this.renderRoot.querySelector('main');
          const existingWrapper = outlet?.querySelector('static-view-wrapper');
          const ssrRoute = this.getAttribute('data-ssr-route');

          if (
            existingWrapper &&
            ssrRoute === '/whatis-mcp' &&
            !this.hasNavigated
          ) {
            // Reuse SSR content on first load only
            this.hasNavigated = true;
            return existingWrapper;
          }

          // Load markdown dynamically
          const view = commands.component('static-view') as any;
          view.src = '/content/whatis-mcp.md';
          return view;
        },
      },
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
          // Check if we have SSR content for this EXACT route on first load
          const outlet = this.renderRoot.querySelector('main');
          const existingWrapper = outlet?.querySelector('static-view-wrapper');
          const ssrRoute = this.getAttribute('data-ssr-route');

          if (existingWrapper && ssrRoute === '/terms' && !this.hasNavigated) {
            // Reuse SSR content on first load only
            this.hasNavigated = true;
            return existingWrapper;
          }

          // Load markdown dynamically
          const view = commands.component('static-view') as any;
          view.src = '/content/terms.md';
          return view;
        },
      },
      {
        path: '/privacy',
        action: (context, commands) => {
          // Check if we have SSR content for this EXACT route on first load
          const outlet = this.renderRoot.querySelector('main');
          const existingWrapper = outlet?.querySelector('static-view-wrapper');
          const ssrRoute = this.getAttribute('data-ssr-route');

          if (
            existingWrapper &&
            ssrRoute === '/privacy' &&
            !this.hasNavigated
          ) {
            // Reuse SSR content on first load only
            this.hasNavigated = true;
            return existingWrapper;
          }

          // Load markdown dynamically
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
          { path: 'tools', component: 'tools-view' },
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
              { path: 'executions', component: 'flow-executions-view' },
              {
                path: 'executions/:executionId',
                component: 'flow-execution-view',
              },
              { path: ':flowId', component: 'flow-view' },
            ],
          },
          { path: '/api-usage', component: 'api-usage-view' },
          { path: 'settings', redirect: '/console/settings/profile' },
          { path: 'settings/profile', component: 'profile-view' },
          { path: 'settings/security', component: 'security-view' },
          { path: 'settings/api-keys', component: 'api-keys-view' },
          { path: 'settings/ai-models', component: 'ai-models-view' },
          { path: 'settings/appearance', component: 'appearance-view' },
          { path: 'settings/account', component: 'account-view' },
          { path: 'settings/users', component: 'user-management-view' },
          { path: 'settings/teams', component: 'team-management-view' },
          {
            path: 'settings/invitations',
            component: 'invitation-management-view',
          },
          {
            path: 'settings/notification-preferences',
            component: 'notification-preferences-view',
          },
          { path: 'pricing', component: 'pricing-view' },
          { path: 'approval/:requestId', component: 'approval-view' },
        ],
      },
    ]);
  }

  render() {
    return html` <main></main> `;
  }

  connectWebSocket() {
    // Connect to general flow updates WebSocket
    // This is handled by webSocketService.connectToFlowUpdates()
    // which is called from flow-executions-view
    // No need to connect here globally
  }

  setupEventListeners() {
    // Event listeners can be added here as needed
  }
}
