import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import './login-view';
import { LoginView } from './login-view';

describe('LoginView', () => {
  let element: LoginView;
  const sandbox = sinon.createSandbox();

  beforeEach(async () => {
    element = await fixture(html`<login-view></login-view>`);
  });

  afterEach(() => {
    sandbox.restore();
  });

  it('should render the login form', () => {
    const form = element.shadowRoot?.querySelector('form');
    expect(form).to.exist;
    const usernameInput = element.shadowRoot?.querySelector('#username');
    expect(usernameInput).to.exist;
    const passwordInput = element.shadowRoot?.querySelector('#password');
    expect(passwordInput).to.exist;
    const loginButton = element.shadowRoot?.querySelector('sl-button[type="submit"]');
    expect(loginButton).to.exist;
  });

  it('should show an error message on failed login', async () => {
    // Stub window.fetch to simulate a failed login
    const fetchStub = sandbox.stub(window, 'fetch');
    fetchStub.resolves(
      new Response(null, {
        status: 401,
        statusText: 'Unauthorized',
      })
    );

    const form = element.shadowRoot?.querySelector('form');
    form?.dispatchEvent(new Event('submit'));

    // Wait until the error message appears in the DOM
    await waitUntil(
      () => element.shadowRoot?.querySelector('.error-message'),
      'Error message did not appear'
    );

    const errorMessage = element.shadowRoot?.querySelector('.error-message');
    expect(errorMessage).to.exist;
    expect(errorMessage?.textContent).to.contain('Invalid username or password');
    expect(fetchStub).to.have.been.calledOnce;
  });

  it('should not show an error message on successful login', async () => {
    // Stub window.fetch to simulate a successful login
    const fetchStub = sandbox.stub(window, 'fetch');
    fetchStub.resolves(
      new Response('{"access_token":"test_token"}', { status: 200 })
    );

    const usernameInput =
      element.shadowRoot?.querySelector<HTMLInputElement>('#username');
    usernameInput!.value = 'testuser';
    const passwordInput =
      element.shadowRoot?.querySelector<HTMLInputElement>('#password');
    passwordInput!.value = 'correctpassword';

    const form = element.shadowRoot?.querySelector('form');
    form?.dispatchEvent(new Event('submit'));

    await element.updateComplete;

    const errorMessage = element.shadowRoot?.querySelector('.error-message');
    expect(errorMessage).to.not.exist;
    expect(fetchStub).to.have.been.calledOnce;
  });

  it('should have links for password reset and registration', () => {
    const forgotPasswordLink =
      element.shadowRoot?.querySelector('a[href="/forgot-password"]');
    expect(forgotPasswordLink).to.exist;
    const signUpLink = element.shadowRoot?.querySelector('a[href="/register"]');
    expect(signUpLink).to.exist;
  });
});
