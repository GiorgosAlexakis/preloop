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
    color: var(--destructive);
    margin-bottom: 1rem;
    text-align: center;
    font-size: 0.875rem;
  }

  .form-container {
    max-width: 400px;
    margin: 2rem auto;
    padding: 2rem;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
  }

  .form-container h2 {
    text-align: center;
    margin-bottom: 1.5rem;
    color: var(--foreground);
    font-size: 1.5rem;
    font-weight: 600;
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
    color: var(--muted-foreground);
    font-size: 0.875rem;
  }

  .form-links a {
    color: var(--primary);
    text-decoration: none;
  }

  .form-links a:hover {
    text-decoration: underline;
  }

  sl-alert {
    margin-bottom: 1rem;
  }
`;
