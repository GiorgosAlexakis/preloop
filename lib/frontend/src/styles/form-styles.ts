import { css } from 'lit';

export const formStyles = css`
  /* Shared Form Styles */
  .form-container {
    max-width: 400px;
    margin: 2rem auto;
    padding: 2rem;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  }

  .form-container h2 {
    text-align: center;
    margin-bottom: 1.5rem;
    color: var(--sl-color-neutral-800);
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-actions {
    margin-top: 1.5rem;
    text-align: center;
  }

  .form-actions button {
    width: 100%;
    padding: 0.75rem;
    background-color: var(--sl-color-primary-600);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 1rem;
  }

  .form-actions button:hover {
    background-color: var(--sl-color-primary-700);
  }

  .form-links {
    margin-top: 1rem;
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
`;
