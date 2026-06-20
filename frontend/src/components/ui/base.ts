import { LitElement } from 'lit';

/** Base class for shadcn-style components using light DOM so Tailwind works. */
export class UiElement extends LitElement {
  createRenderRoot(): HTMLElement | DocumentFragment {
    return this;
  }
}
