import { html, nothing } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-input')
export class SlInput extends UiElement {
  @property({ type: String }) label = '';
  @property({ type: String }) type = 'text';
  @property({ type: String }) value = '';
  @property({ type: String }) name = '';
  @property({ type: String }) placeholder = '';
  @property({ type: String }) helpText = '';
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) readonly = false;
  @property({ type: Boolean, attribute: 'password-toggle' }) passwordToggle =
    false;
  @property({ type: Boolean }) clearable = false;
  @property({ type: String }) size = 'medium';
  @property({ type: String }) pattern = '';
  @property({ type: Number }) minlength = 0;
  @property({ type: Number }) maxlength = 0;
  @property({ type: String }) autocomplete = '';

  @state() private _showPassword = false;

  private _onInput(e: Event) {
    const target = e.target as HTMLInputElement;
    this.value = target.value;
    this.dispatchEvent(
      new CustomEvent('sl-input', { bubbles: true, composed: true })
    );
    this.dispatchEvent(
      new CustomEvent('sl-change', {
        bubbles: true,
        composed: true,
        detail: { value: this.value },
      })
    );
  }

  private _togglePassword() {
    this._showPassword = !this._showPassword;
  }

  private _clear() {
    this.value = '';
    this._onInput({ target: { value: '' } } as unknown as Event);
  }

  render() {
    const inputType =
      this.type === 'password' && this._showPassword ? 'text' : this.type;
    const sizeClass =
      this.size === 'small'
        ? 'h-8 text-xs'
        : this.size === 'large'
          ? 'h-11 text-base'
          : 'h-9 text-sm';

    return html`
      <div part="form-control" class="grid w-full gap-1.5">
        ${this.label
          ? html`<label
              part="label"
              class="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >${this.label}</label
            >`
          : nothing}
        <div class="relative flex items-center">
          <slot name="prefix"></slot>
          <input
            part="input"
            class=${cn(
              'flex w-full rounded-md border border-input bg-transparent px-3 py-1 shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50',
              sizeClass
            )}
            type=${inputType}
            .value=${this.value}
            name=${this.name || nothing}
            id=${this.id || nothing}
            placeholder=${this.placeholder || nothing}
            ?required=${this.required}
            ?disabled=${this.disabled}
            ?readonly=${this.readonly}
            pattern=${this.pattern || nothing}
            minlength=${this.minlength || nothing}
            maxlength=${this.maxlength || nothing}
            autocomplete=${this.autocomplete || nothing}
            @input=${this._onInput}
          />
          ${this.passwordToggle && this.type === 'password'
            ? html`
                <button
                  type="button"
                  part="password-toggle-button"
                  class="absolute right-2 inline-flex h-6 w-6 items-center justify-center text-muted-foreground hover:text-foreground"
                  @click=${this._togglePassword}
                  tabindex="-1"
                >
                  <sl-icon
                    name=${this._showPassword ? 'eye-slash' : 'eye'}
                  ></sl-icon>
                </button>
              `
            : nothing}
          ${this.clearable && this.value
            ? html`
                <button
                  type="button"
                  class="absolute right-2 inline-flex h-6 w-6 items-center justify-center text-muted-foreground hover:text-foreground"
                  @click=${this._clear}
                  tabindex="-1"
                >
                  <sl-icon name="x"></sl-icon>
                </button>
              `
            : nothing}
          <slot name="suffix"></slot>
        </div>
        ${this.helpText
          ? html`<p part="help-text" class="text-xs text-muted-foreground">
              ${this.helpText}
            </p>`
          : nothing}
        <slot name="help-text"></slot>
      </div>
    `;
  }
}

@customElement('sl-textarea')
export class SlTextarea extends UiElement {
  @property({ type: String }) label = '';
  @property({ type: String }) value = '';
  @property({ type: String }) name = '';
  @property({ type: String }) placeholder = '';
  @property({ type: Boolean }) required = false;
  @property({ type: Boolean }) disabled = false;
  @property({ type: Boolean }) readonly = false;
  @property({ type: Number }) rows = 4;
  @property({ type: Number }) resize: 'none' | 'vertical' | 'auto' = 0 as never;

  private _onInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    this.value = target.value;
    this.dispatchEvent(
      new CustomEvent('sl-input', { bubbles: true, composed: true })
    );
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
        <textarea
          part="textarea"
          class="flex min-h-[60px] w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          .value=${this.value}
          name=${this.name || nothing}
          placeholder=${this.placeholder || nothing}
          rows=${this.rows}
          ?required=${this.required}
          ?disabled=${this.disabled}
          ?readonly=${this.readonly}
          @input=${this._onInput}
        ></textarea>
      </div>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-input': SlInput;
    'sl-textarea': SlTextarea;
  }
}
