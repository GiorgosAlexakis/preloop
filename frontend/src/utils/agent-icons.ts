import { html, type TemplateResult } from 'lit';

export function renderAgentIcon(
  sourceType: string | null | undefined,
  style: string = ''
): TemplateResult {
  const renderIcon = (name: string, src?: string) => {
    return src
      ? html`<sl-icon src="${src}" style="${style}"></sl-icon>`
      : html`<sl-icon name="${name}" style="${style}"></sl-icon>`;
  };

  switch (sourceType) {
    case 'claude_code':
      return renderIcon('code-slash');
    case 'claude_desktop':
      return renderIcon('display');
    case 'openclaw':
      return renderIcon('', '/images/logos/openclaw.svg');
    case 'codex':
      return renderIcon('braces');
    case 'desktop_agent':
      return renderIcon('pc-display');
    case 'custom':
      return renderIcon('robot');
    default:
      return renderIcon('robot');
  }
}
