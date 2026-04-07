import { html, fixture, expect, oneEvent } from '@open-wc/testing';
import sinon, { SinonSandbox } from 'sinon';
import './add-tracker-modal.ts';
import { AddTrackerModal } from './add-tracker-modal';
import * as api from '../api';

describe('AddTrackerModal', () => {
  let element: AddTrackerModal;
  let sandbox: SinonSandbox;

  beforeEach(() => {
    localStorage.setItem('accessToken', 'test-access-token');
    localStorage.setItem('refreshToken', 'test-refresh-token');
    sandbox = sinon.createSandbox();
    sandbox.stub(window, 'fetch').resolves(new Response(JSON.stringify([])));
  });

  afterEach(() => {
    sandbox.restore();
    localStorage.clear();
  });

  const setupStubs = (el: AddTrackerModal) => {
    const validateStub = sandbox.stub();
    const addStub = sandbox.stub();
    const updateStub = sandbox.stub();
    const listProjectsStub = sandbox.stub();

    el._api = {
      ...api,
      validateTrackerToken: validateStub,
      addTracker: addStub,
      updateTracker: updateStub,
      listProjectsForOrg: listProjectsStub,
    };

    return { validateStub, addStub, updateStub, listProjectsStub };
  };

  describe('Add Mode', () => {
    beforeEach(async () => {
      element = await fixture(html`<add-tracker-modal></add-tracker-modal>`);
      await element.updateComplete;
    });

    it('renders correctly in initial add state (step 1)', async () => {
      const dialog = element.shadowRoot?.querySelector('sl-dialog');
      expect(dialog).to.exist;
      expect(dialog?.label).to.equal('Add Tracker');

      const nameInput = element.shadowRoot?.querySelector<HTMLInputElement>(
        'sl-input[name="name"]'
      );
      expect(nameInput).to.exist;
      expect(nameInput?.value).to.be.empty;

      const typeSelect = element.shadowRoot?.querySelector<HTMLSelectElement>(
        'sl-select[name="type"]'
      );
      expect(typeSelect).to.exist;
      expect(typeSelect?.value).to.equal('github');

      const nextButton = element.shadowRoot?.querySelector(
        'sl-button[variant="primary"]'
      );
      expect(nextButton).to.exist;
      expect(nextButton?.textContent?.trim()).to.equal('Next');
    });

    describe('Edit Mode', () => {
      const mockTracker = {
        id: '123',
        name: 'Test Tracker',
        tracker_type: 'gitlab',
        url: 'https://gitlab.com',
        connection_details: { username: 'testuser' },
        scope_rules: [
          {
            rule_type: 'INCLUDE',
            scope_type: 'ORGANIZATION',
            identifier: 'org1',
          },
        ],
      };

      beforeEach(async () => {
        element = await fixture(
          html`<add-tracker-modal .tracker=${mockTracker}></add-tracker-modal>`
        );
        await element.updateComplete;
      });

      it('renders correctly in initial edit state (step 1)', async () => {
        const dialog = element.shadowRoot?.querySelector('sl-dialog');
        expect(dialog).to.exist;
        expect(dialog?.label).to.equal('Edit Tracker');

        const nameInput = element.shadowRoot?.querySelector<HTMLInputElement>(
          'sl-input[name="name"]'
        );
        expect(nameInput?.value).to.equal(mockTracker.name);

        const typeSelect = element.shadowRoot?.querySelector<HTMLSelectElement>(
          'sl-select[name="type"]'
        );
        expect(typeSelect?.value).to.equal(mockTracker.tracker_type);

        const tokenInput = element.shadowRoot?.querySelector<HTMLInputElement>(
          'sl-input[name="api_key"]'
        );
        expect(tokenInput?.value).to.equal('unchanged');

        const saveButton = element.shadowRoot?.querySelector(
          'sl-button[variant="primary"]'
        );
        expect(saveButton?.textContent?.trim()).to.equal('Next');
      });
    });

    it('updates state on form input', async () => {
      element = await fixture(html`<add-tracker-modal></add-tracker-modal>`);
      await element.updateComplete;

      const nameInput = element.shadowRoot?.querySelector<HTMLInputElement>(
        'sl-input[name="name"]'
      );
      nameInput!.value = 'New Tracker Name';
      nameInput?.dispatchEvent(new Event('sl-input'));
      await element.updateComplete;
      expect(nameInput?.value).to.equal('New Tracker Name');

      const typeSelect = element.shadowRoot?.querySelector<HTMLSelectElement>(
        'sl-select[name="type"]'
      );
      typeSelect!.value = 'jira';
      typeSelect?.dispatchEvent(new Event('sl-change'));
      await element.updateComplete;
      expect(typeSelect?.value).to.equal('jira');
    });

    describe('Step 1 -> Step 2 Navigation', () => {
      beforeEach(async () => {
        element = await fixture(html`<add-tracker-modal></add-tracker-modal>`);
        await element.updateComplete;
      });

      it('transitions to step 2 on successful validation', async () => {
        const { validateStub } = setupStubs(element);
        validateStub.resolves({
          success: true,
          orgs: [{ id: 'org1', name: 'Org One' }],
        });

        const nextButton = element.shadowRoot?.querySelector<HTMLElement>(
          'sl-button[variant="primary"]'
        );
        nextButton?.click();
        await element.updateComplete;
        await element.updateComplete;

        expect(validateStub).to.have.been.calledOnce;
        const dialog = element.shadowRoot?.querySelector('sl-dialog');
        expect(dialog?.querySelector('h2')?.textContent).to.equal(
          'Configure Project Scope'
        );
      });

      it('shows an error message on failed validation', async () => {
        const { validateStub } = setupStubs(element);
        validateStub.resolves({ success: false, message: 'Invalid token' });

        const nextButton = element.shadowRoot?.querySelector<HTMLElement>(
          'sl-button[variant="primary"]'
        );
        nextButton?.click();
        await element.updateComplete;
        await element.updateComplete;

        expect(validateStub).to.have.been.calledOnce;
        const errorMessage = element.shadowRoot?.querySelector('.error');
        expect(errorMessage).to.exist;
        expect(errorMessage?.textContent).to.equal('Invalid token');
        const dialog = element.shadowRoot?.querySelector('sl-dialog');
        expect(dialog?.querySelector('h2')).to.not.exist;
      });

      describe('Saving', () => {
        it('calls addTracker and dispatches tracker-added on save in add mode', async () => {
          element = await fixture(
            html`<add-tracker-modal></add-tracker-modal>`
          );
          const { validateStub, addStub } = setupStubs(element);
          validateStub.resolves({
            success: true,
            orgs: [{ id: 'org1', name: 'Org One' }],
          });
          addStub.resolves({ id: '456' });

          const nextButton = element.shadowRoot?.querySelector<HTMLElement>(
            'sl-button[variant="primary"]'
          );
          nextButton?.click();
          await element.updateComplete;
          await element.updateComplete; // Wait for re-render

          const addButton = element.shadowRoot?.querySelector<HTMLElement>(
            'sl-button[variant="primary"]'
          );
          const listener = oneEvent(element, 'tracker-added');
          addButton?.click();
          const { detail } = await listener;

          expect(addStub).to.have.been.calledOnce;
          expect(detail.tracker.id).to.equal('456');
        });

        it('calls updateTracker and dispatches tracker-updated on save in edit mode', async () => {
          const mockTracker = {
            id: '123',
            name: 'Test Tracker',
            tracker_type: 'github',
            url: 'https://api.github.com',
            scope_rules: [],
          };
          element = await fixture(
            html`<add-tracker-modal
              .tracker=${mockTracker}
            ></add-tracker-modal>`
          );
          const { validateStub, updateStub } = setupStubs(element);
          validateStub.resolves({
            success: true,
            orgs: [{ id: 'org1', name: 'Org One' }],
          });
          updateStub.resolves({ id: '123' });

          const nextButton = element.shadowRoot?.querySelector<HTMLElement>(
            'sl-button[variant="primary"]'
          );
          nextButton?.click();
          await element.updateComplete;
          await element.updateComplete; // Wait for re-render

          const saveButton = element.shadowRoot?.querySelector<HTMLElement>(
            'sl-button[variant="primary"]'
          );
          const listener = oneEvent(element, 'tracker-updated');
          saveButton?.click();
          const { detail } = await listener;

          expect(updateStub).to.have.been.calledOnce;
          expect(detail.tracker.id).to.equal('123');
        });
      });

      describe('Cancel/Close', () => {
        it('dispatches close-modal event on cancel click', async () => {
          element = await fixture(
            html`<add-tracker-modal></add-tracker-modal>`
          );
          await element.updateComplete;

          const cancelButton = element.shadowRoot?.querySelector<HTMLElement>(
            'sl-button:not([variant="primary"])'
          );
          const listener = oneEvent(element, 'close-modal');
          cancelButton?.click();
          await listener;
        });

        it('dispatches close-modal event on dialog close', async () => {
          element = await fixture(
            html`<add-tracker-modal></add-tracker-modal>`
          );
          await element.updateComplete;

          const dialog = element.shadowRoot?.querySelector('sl-dialog');
          const listener = oneEvent(element, 'close-modal');
          dialog?.dispatchEvent(new CustomEvent('sl-request-close'));
          await listener;
        });
      });
    });
  });
});
