import { css } from 'lit';

export const formStyles = css`
  /* Shared Form Styles — shadcn-style centered auth card */

  :host {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: calc(100vh - 80px);
    padding: 2rem 1rem 3rem;
    box-sizing: border-box;
    background-color: var(--sl-color-neutral-50);
  }

  .logo {
    text-align: center;
    padding: 1rem 2rem 1.5rem;
  }

  .logo img {
    max-width: 140px;
  }

  .error-message {
    color: var(--sl-color-danger-700);
    background-color: var(--sl-color-danger-50);
    border: 1px solid var(--sl-color-danger-200);
    border-radius: var(--sl-border-radius-medium);
    padding: 0.625rem 0.875rem;
    margin-bottom: 1rem;
    text-align: center;
    font-size: var(--sl-font-size-small);
  }

  .form-container {
    width: 100%;
    max-width: 400px;
    margin: 0 auto;
    padding: 2rem;
    background-color: var(--sl-color-neutral-0);
    border: 1px solid var(--sl-color-neutral-200);
    border-radius: var(--sl-border-radius-large);
    box-shadow: var(--sl-shadow-small);
  }

  .form-container h2 {
    text-align: center;
    margin-top: 0;
    margin-bottom: 0.5rem;
    font-size: 1.5rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    color: var(--sl-color-neutral-900);
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
    color: var(--sl-color-primary-600);
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
`;
