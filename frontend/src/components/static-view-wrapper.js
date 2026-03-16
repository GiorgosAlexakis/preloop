var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { LitElement, html, css, unsafeCSS } from 'lit';
import { customElement } from 'lit/decorators.js';
import './app-header';
import './app-footer';
import landingStyles from '../styles/landing.css?inline';
/**
 * Wrapper component for static SSR content (privacy, terms, etc.)
 * Provides page structure (header, footer) around static HTML content
 */
let StaticViewWrapper = class StaticViewWrapper extends LitElement {
    render() {
        return html `
      <app-header></app-header>
      <main>
        <div class="text-section">
          <slot></slot>
        </div>
      </main>
      <app-footer></app-footer>
    `;
    }
};
StaticViewWrapper.styles = [
    unsafeCSS(landingStyles),
    css `
      :host {
        display: flex;
        flex-direction: column;
        min-height: 100vh;
        width: 100%;
      }

      main {
        flex: 1;
        padding: 2rem;
        max-width: 800px;
        margin: 0 auto;
        width: 100%;
      }

      /* Styles for slotted article content are now in the article's inline <style> tag
         in the light DOM, since ::slotted() can't style descendants */
    `,
];
StaticViewWrapper = __decorate([
    customElement('static-view-wrapper')
], StaticViewWrapper);
export { StaticViewWrapper };
