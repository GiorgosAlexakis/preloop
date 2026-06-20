import { html, nothing } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { cn } from '../../lib/utils';
import { UiElement } from './base';

@customElement('sl-radio-group')
export class SlRadioGroup extends UiElement {
  @property({ type: String }) label = '';
  @property({ type: String }) value = '';
  @property({ type: String }) name = '';
  @property({ type: String }) size = 'medium';

  private _onChange(e: Event) {
    const target = e.target as HTMLInputElement;
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
      <fieldset part="form-control" class="grid gap-2" @change=${this._onChange}>
        ${this.label
          ? html`<legend class="text-sm font-medium">${this.label}</legend>`
          : nothing}
        <slot></slot>
      </fieldset>
    `;
  }
}

@customElement('sl-radio')
export class SlRadio extends UiElement {
  @property({ type: String }) value = '';
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) size = 'medium';

  render() {
    return html`
      <label part="base" class="inline-flex items-center gap-2 text-sm">
        <input
          part="control"
          type="radio"
          class="h-4 w-4 border-primary text-primary accent-primary focus:ring-ring"
          value=${this.value}
          ?disabled=${this.disabled}
        />
        <slot></slot>
      </label>
    `;
  }
}

@customElement('sl-radio-button')
export class SlRadioButton extends SlRadio {
  render() {
    return html`
      <label part="base" class="inline-flex">
        <input
          part="control"
          type="radio"
          class="peer sr-only"
          value=${this.value}
          ?disabled=${this.disabled}
        />
        <span
          class="inline-flex items-center justify-center rounded-md border border-input bg-background px-3 py-1.5 text-sm font-medium shadow-sm transition-colors peer-checked:bg-primary peer-checked:text-primary-foreground hover:bg-accent hover:text-accent-foreground peer-disabled:opacity-50"
        >
          <slot></slot>
        </span>
      </label>
    `;
  }
}

@customElement('sl-range')
export class SlRange extends UiElement {
  @property({ type: Number }) value = 0;
  @property({ type: Number }) min = 0;
  @property({ type: Number }) max = 100;
  @property({ type: Number }) step = 1;
  @property({ type: String }) label = '';
  @property({ type: Boolean }) disabled = false;
  @property({ type: String }) name = '';

  private _onInput(e: Event) {
    const target = e.target as HTMLInputElement;
    this.value = Number(target.value);
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
      <div part="form-control" class="grid w-full gap-2">
        ${this.label
          ? html`<label class="text-sm font-medium">${this.label}</label>`
          : nothing}
        <input
          part="input"
          type="range"
          class="h-2 w-full cursor-pointer appearance-none rounded-full bg-primary/20 accent-primary"
          .value=${String(this.value)}
          min=${this.min}
          max=${this.max}
          step=${this.step}
          name=${this.name || nothing}
          ?disabled=${this.disabled}
          @input=${this._onInput}
        />
      </div>
    `;
  }
}

@customElement('sl-tree')
export class SlTree extends UiElement {
  @property({ type: String }) selection = 'single';
  @property({ type: Boolean }) multiselect = false;

  render() {
    return html`
      <div part="base" class="flex flex-col gap-0.5" role="tree">
        <slot></slot>
      </div>
    `;
  }
}

@customElement('sl-tree-item')
export class SlTreeItem extends UiElement {
  @property({ type: Boolean, reflect: true }) expanded = false;
  @property({ type: Boolean, reflect: true }) selected = false;
  @property({ type: Boolean }) lazy = false;
  @property({ type: Boolean }) disabled = false;

  private _toggle() {
    this.expanded = !this.expanded;
  }

  render() {
    return html`
      <div part="base" class="flex flex-col" role="treeitem">
        <div
          part="item"
          class=${cn(
            'flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-sm hover:bg-accent',
            this.selected && 'bg-accent'
          )}
          @click=${() => {
            this.selected = !this.selected;
            this.dispatchEvent(
              new CustomEvent('sl-selection-change', {
                bubbles: true,
                composed: true,
              })
            );
          }}
        >
          <button
            type="button"
            class="inline-flex h-4 w-4 items-center justify-center"
            @click=${(e: Event) => {
              e.stopPropagation();
              this._toggle();
            }}
          >
            <sl-icon
              name="chevron-right"
              class=${cn('transition-transform', this.expanded && 'rotate-90')}
            ></sl-icon>
          </button>
          <slot name="expand-icon"></slot>
          <slot name="icon"></slot>
          <slot></slot>
        </div>
        ${this.expanded
          ? html`<div part="children" class="ml-4 border-l pl-2"><slot name="children"></slot></div>`
          : nothing}
      </div>
    `;
  }
}

@customElement('sl-carousel')
export class SlCarousel extends UiElement {
  @property({ type: Number }) slide = 0;
  @property({ type: Boolean }) navigation = true;
  @property({ type: Boolean }) pagination = false;
  @property({ type: Boolean }) loop = false;

  render() {
    return html`
      <div part="base" class="relative overflow-hidden rounded-lg">
        <div part="slides" class="flex transition-transform duration-300">
          <slot></slot>
        </div>
        ${this.navigation
          ? html`
              <button
                type="button"
                part="navigation-button navigation-button-previous"
                class="absolute left-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 p-2 shadow"
                @click=${() => this.slide--}
              >
                <sl-icon name="chevron-left"></sl-icon>
              </button>
              <button
                type="button"
                part="navigation-button navigation-button-next"
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded-full bg-background/80 p-2 shadow"
                @click=${() => this.slide++}
              >
                <sl-icon name="chevron-right"></sl-icon>
              </button>
            `
          : nothing}
      </div>
    `;
  }
}

@customElement('sl-carousel-item')
export class SlCarouselItem extends UiElement {
  render() {
    return html`
      <div part="base" class="min-w-full shrink-0">
        <slot></slot>
      </div>
    `;
  }
}

@customElement('sl-qr-code')
export class SlQrCode extends UiElement {
  @property({ type: String }) value = '';
  @property({ type: String }) label = '';
  @property({ type: Number }) size = 128;

  render() {
    const url = `https://api.qrserver.com/v1/create-qr-code/?size=${this.size}x${this.size}&data=${encodeURIComponent(this.value)}`;
    return html`
      <img
        part="image"
        src=${url}
        alt=${this.label || 'QR Code'}
        width=${this.size}
        height=${this.size}
        class="rounded-md border"
      />
    `;
  }
}

@customElement('sl-format-date')
export class SlFormatDate extends UiElement {
  @property({ type: String }) date = '';
  @property({ type: String }) month = 'short';
  @property({ type: String }) day = 'numeric';
  @property({ type: String }) year = 'numeric';
  @property({ type: String }) hour = '';
  @property({ type: String }) minute = '';
  @property({ type: String }) second = '';
  @property({ type: String }) timeZone = '';
  @property({ type: String }) weekday = '';

  render() {
    if (!this.date) return nothing;
    const options: Intl.DateTimeFormatOptions = {
      month: this.month as Intl.DateTimeFormatOptions['month'],
      day: this.day as Intl.DateTimeFormatOptions['day'],
      year: this.year as Intl.DateTimeFormatOptions['year'],
    };
    if (this.hour) options.hour = this.hour as Intl.DateTimeFormatOptions['hour'];
    if (this.minute) options.minute = this.minute as Intl.DateTimeFormatOptions['minute'];
    if (this.timeZone) options.timeZone = this.timeZone;
    const formatted = new Date(this.date).toLocaleDateString(undefined, options);
    return html`<span part="date">${formatted}</span>`;
  }
}

@customElement('sl-relative-time')
export class SlRelativeTime extends UiElement {
  @property({ type: String }) date = '';
  @property({ type: String }) format = 'narrow';
  @property({ type: Boolean }) sync = false;

  render() {
    if (!this.date) return nothing;
    const rtf = new Intl.RelativeTimeFormat(undefined, {
      numeric: 'auto',
      style: this.format as Intl.RelativeTimeFormatStyle,
    });
    const diff = Date.now() - new Date(this.date).getTime();
    const seconds = Math.round(diff / 1000);
    const minutes = Math.round(seconds / 60);
    const hours = Math.round(minutes / 60);
    const days = Math.round(hours / 24);
    let formatted: string;
    if (Math.abs(days) >= 1) formatted = rtf.format(-days, 'day');
    else if (Math.abs(hours) >= 1) formatted = rtf.format(-hours, 'hour');
    else if (Math.abs(minutes) >= 1) formatted = rtf.format(-minutes, 'minute');
    else formatted = rtf.format(-seconds, 'second');
    return html`<span part="date">${formatted}</span>`;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'sl-radio-group': SlRadioGroup;
    'sl-radio': SlRadio;
    'sl-radio-button': SlRadioButton;
    'sl-range': SlRange;
    'sl-tree': SlTree;
    'sl-tree-item': SlTreeItem;
    'sl-carousel': SlCarousel;
    'sl-carousel-item': SlCarouselItem;
    'sl-qr-code': SlQrCode;
    'sl-format-date': SlFormatDate;
    'sl-relative-time': SlRelativeTime;
  }
}
