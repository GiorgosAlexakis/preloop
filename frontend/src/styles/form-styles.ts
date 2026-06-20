import { css } from 'lit';

export const formStyles = css`
  /* Shared Form Styles */

  .logo {
    text-align: center;
    padding: 2rem;
  }

  .logo img {
    max-width: 150px;
  }

  .error-message {
    color: var(--sl-color-danger-700);
    background: var(--sl-color-danger-50);
    border: 1px solid
      color-mix(in srgb, var(--sl-color-danger-500) 25%, transparent);
    border-radius: var(--sl-border-radius-medium);
    padding: 0.75rem 1rem;
    margin-bottom: 1rem;
    text-align: center;
  }

  .form-container {
    max-width: 400px;
    margin: clamp(2rem, 6vw, 5rem) auto;
    padding: 2rem;
    background: hsl(var(--card));
    border: 1px solid hsl(var(--border));
    border-radius: var(--sl-border-radius-x-large);
    box-shadow: var(--shadow-shadcn-lg);
    color: hsl(var(--card-foreground));
  }

  .form-container h2 {
    text-align: center;
    margin-bottom: 1.5rem;
    color: hsl(var(--foreground));
    font-size: 1.75rem;
    font-weight: 700;
    letter-spacing: -0.035em;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-actions {
    margin-top: 2rem;
    text-align: center;
  }

  .form-actions sl-button {
    width: 100%;
  }

  .form-links {
    margin-top: 2rem;
    text-align: center;
    color: hsl(var(--muted-foreground));
  }

  .form-links a {
    color: var(--sl-color-primary-600);
    text-decoration: none;
  }

  .form-links a:hover {
    text-decoration: underline;
  }

  sl-alert {
    margin-bottom: 1rem;
  }

  sl-input::part(base),
  sl-textarea::part(base) {
    border-radius: calc(var(--radius) - 4px);
  }

  sl-button::part(base) {
    border-radius: calc(var(--radius) - 4px);
    font-weight: 500;
  }
`;
