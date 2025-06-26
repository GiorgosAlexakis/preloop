import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import './register-view';
import { RegisterView } from './register-view';

describe('RegisterView', () => {
  let element: RegisterView;
  const sandbox = sinon.createSandbox();

  beforeEach(async () => {
    element = await fixture(html`<register-view></register-view>`);
  });

  afterEach(() => {
    sandbox.restore();
  });

  it('should render the registration form', () => {
    const form = element.shadowRoot?.querySelector('form');
    expect(form).to.exist;
    const usernameInput = element.shadowRoot?.querySelector('#username');
    expect(usernameInput).to.exist;
    const emailInput = element.shadowRoot?.querySelector('#email');
    expect(emailInput).to.exist;
    const passwordInput = element.shadowRoot?.querySelector('#password');
    expect(passwordInput).to.exist;
    const registerButton = element.shadowRoot?.querySelector(
      'sl-button[type="submit"]'
    );
    expect(registerButton).to.exist;
  });

  it('should show an error message on failed registration', async () => {
    // Stub window.fetch to simulate a failed registration
    const fetchStub = sandbox.stub(window, 'fetch');
    fetchStub.resolves(new Response(null, { status: 400 }));

    const form = element.shadowRoot?.querySelector('form');
    form?.dispatchEvent(new Event('submit'));

    // Wait until the error message appears
    await waitUntil(
      () => element.shadowRoot?.querySelector('.error-message'),
      'Error message did not appear'
    );

    const errorMessage = element.shadowRoot?.querySelector('.error-message');
    expect(errorMessage).to.exist;
    expect(errorMessage?.textContent).to.contain('Failed to create an account');
    expect(fetchStub).to.have.been.calledOnce;
  });

  it('should not show an error message on successful registration', async () => {
    // Stub window.fetch to simulate a successful registration
    const fetchStub = sandbox.stub(window, 'fetch');
    fetchStub.resolves(new Response(null, { status: 200 }));

    const form = element.shadowRoot?.querySelector('form');
    form?.dispatchEvent(new Event('submit'));

    await element.updateComplete;

    const errorMessage = element.shadowRoot?.querySelector('.error-message');
    expect(errorMessage).to.not.exist;
    expect(fetchStub).to.have.been.calledOnce;
  });

  it('should have a link to the login page', () => {
    const loginLink = element.shadowRoot?.querySelector('a[href="/login"]');
    expect(loginLink).to.exist;
    expect(loginLink?.textContent).to.contain('Already have an account? Sign In');
  });
});
