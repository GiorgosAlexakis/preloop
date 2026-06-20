import { html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-select')
export class SlSelect extends UiElement {
  @property({ type: String }) label = '';
  @property({ type: String }) value = '';
  @property({ type: String }) name = '';
  @property({ type: String }) placeholder = '';
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) clearable = false;
  @property({ type: Boolean }) hoist = false;
  @property({ type: String }) size = 'medium';
  @property({ type: Number }) maxOptionsVisible = 10;

  @state() private _open = false;

  private _onChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    this.value = target.value;
    this.dispatchEvent(
      new CustomEvent('sl-change', {
        bubbles: true,
        composed: true,
        detail: { value: this.value },
      })
    );
  }

  render() {
    return html`
      <div part="form-control" class="grid w-full gap-1.5">
        ${this.label
          ? html`<label class="text-sm font-medium leading-none"
              >${this.label}</label
            >`
          : nothing}
        <div part="combobox" class="relative">
          <select
            part="display-input"
            class="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 appearance-none bg-background"
            .value=${this.value}
            name=${this.name || nothing}
            ?disabled=${this.disabled}
            ?required=${this.required}
            @change=${this._onChange}
          >
            ${this.placeholder
              ? html`<option value="" disabled ?selected=${!this.value}>
                  ${this.placeholder}
                </option>`
              : nothing}
            <slot></slot>
          </select>
          <sl-icon
            name="chevron-down"
            class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
          ></sl-icon>
        </div>
        <slot name="help-text"></slot>
      </div>
    `;
  }
}

@customElement('sl-option')
export class SlOption extends UiElement {
  @property({ type: String }) value = '';
  @property({ type: Boolean }) disabled = false;

  render() {
    return html`
      <option
        part="base"
        value=${this.value}
        ?disabled=${this.disabled}
      >
        <slot></slot>
      </option>
    `;
  }
}

@customElement('sl-option-group')
export class SlOptionGroup extends UiElement {
  @property({ type: String }) label = '';

  render() {
    return html`
      <optgroup part="base" label=${this.label}>
        <slot></slot>
      </optgroup>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-select': SlSelect;
    'sl-option': SlOption;
    'sl-option-group': SlOptionGroup;
  }
}
