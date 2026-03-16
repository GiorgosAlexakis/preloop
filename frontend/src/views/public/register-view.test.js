import { html, fixture, expect, waitUntil } from '@open-wc/testing';
import sinon from 'sinon';
import './register-view';
describe('RegisterView', () => {
    let element;
    let fetchStub;
    beforeEach(async () => {
        // Set up minimal BRAND_CONFIG for getBrandConfig()
        window.BRAND_CONFIG = {
            name: 'Test Brand',
            domain: 'test.example.com',
            company: { legal_name: 'Test Co', address: '123 Test', city: 'Test' },
            branding: {
                logo_light: '/logo.svg',
                logo_dark: '/logo-dark.svg',
                favicon: '/favicon.ico',
                primary_color: '#000',
                gradient_product: '',
                gradient_ai: '',
            },
            social: { twitter: '', linkedin: '', instagram: '' },
        };
        element = await fixture(html `<register-view></register-view>`);
        // Stub fetch before each test
        fetchStub = sinon.stub(window, 'fetch');
    });
    afterEach(() => {
        // Restore fetch after each test
        fetchStub.restore();
        // Clean up BRAND_CONFIG
        delete window.BRAND_CONFIG;
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
        const registerButton = element.shadowRoot?.querySelector('sl-button[type="submit"]');
        expect(registerButton).to.exist;
    });
    it('should show an error message on failed registration', async () => {
        // Stub fetch to simulate a failed registration with error detail
        fetchStub.resolves(new Response(JSON.stringify({ detail: 'Email already registered' }), {
            status: 400,
        }));
        // Fill in the form fields
        const usernameInput = element.shadowRoot?.querySelector('#username');
        const emailInput = element.shadowRoot?.querySelector('#email');
        const passwordInput = element.shadowRoot?.querySelector('#password');
        usernameInput.value = 'testuser';
        emailInput.value = 'test@example.com';
        passwordInput.value = 'password123';
        const form = element.shadowRoot?.querySelector('form');
        const submitEvent = new SubmitEvent('submit', {
            bubbles: true,
            cancelable: true,
        });
        form.dispatchEvent(submitEvent);
        // Wait until the error message appears
        await waitUntil(() => element.shadowRoot?.querySelector('.error-message'), 'Error message did not appear');
        const errorMessage = element.shadowRoot?.querySelector('.error-message');
        expect(errorMessage).to.exist;
        expect(errorMessage?.textContent).to.contain('Email already registered');
        expect(fetchStub).to.have.been.calledOnce;
    });
    it('should not show an error message on successful registration', async () => {
        // Stub fetch to simulate a successful registration
        fetchStub.resolves(new Response(JSON.stringify({}), { status: 200 }));
        // Fill in the form fields
        const usernameInput = element.shadowRoot?.querySelector('#username');
        const emailInput = element.shadowRoot?.querySelector('#email');
        const passwordInput = element.shadowRoot?.querySelector('#password');
        usernameInput.value = 'testuser';
        emailInput.value = 'test@example.com';
        passwordInput.value = 'password123';
        const form = element.shadowRoot?.querySelector('form');
        const submitEvent = new SubmitEvent('submit', {
            bubbles: true,
            cancelable: true,
        });
        form.dispatchEvent(submitEvent);
        // Wait for the async operation to complete
        await new Promise((resolve) => setTimeout(resolve, 100));
        await element.updateComplete;
        // Check that no error message appears
        const errorMessage = element.shadowRoot?.querySelector('.error-message');
        expect(errorMessage).to.not.exist;
        // Verify fetch was called
        expect(fetchStub).to.have.been.calledOnce;
    });
    it('should have a link to the login page', () => {
        const loginLink = element.shadowRoot?.querySelector('a[href="/login"]');
        expect(loginLink).to.exist;
        expect(loginLink?.textContent).to.contain('Already have an account? Sign In');
    });
});
