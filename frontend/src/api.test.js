var __decorate = (this && this.__decorate) || function (decorators, target, key, desc) {
    var c = arguments.length, r = c < 3 ? target : desc === null ? desc = Object.getOwnPropertyDescriptor(target, key) : desc, d;
    if (typeof Reflect === "object" && typeof Reflect.decorate === "function") r = Reflect.decorate(decorators, target, key, desc);
    else for (var i = decorators.length - 1; i >= 0; i--) if (d = decorators[i]) r = (c < 3 ? d(r) : c > 3 ? d(target, key, r) : d(target, key)) || r;
    return c > 3 && r && Object.defineProperty(target, key, r), r;
};
import { expect } from '@open-wc/testing';
import sinon from 'sinon';
import { Router } from '@vaadin/router';
import { fetchWithAuth, AuthedElement } from './api.js';
import { customElement } from 'lit/decorators.js';
// Minimal test element that exposes fetchData for testing
let TestAuthedElement = class TestAuthedElement extends AuthedElement {
    async fetchDataForTest(url, options) {
        return this.fetchData(url, options);
    }
};
TestAuthedElement = __decorate([
    customElement('test-authed-element')
], TestAuthedElement);
describe('api', () => {
    let fetchStub;
    let routerGoStub;
    beforeEach(() => {
        localStorage.setItem('accessToken', 'test-access-token');
        localStorage.setItem('refreshToken', 'test-refresh-token');
        fetchStub = sinon.stub(window, 'fetch');
        routerGoStub = sinon.stub(Router, 'go');
    });
    afterEach(() => {
        fetchStub.restore();
        routerGoStub.restore();
        localStorage.clear();
    });
    describe('fetchWithAuth', () => {
        it('includes Authorization header with access token', async () => {
            fetchStub.resolves(new Response(JSON.stringify({}), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            }));
            await fetchWithAuth('/api/v1/test');
            expect(fetchStub).to.have.been.calledOnce;
            const [url, options] = fetchStub.firstCall.args;
            expect(url).to.equal('/api/v1/test');
            expect(options?.headers).to.be.instanceOf(Headers);
            expect((options?.headers).get('Authorization')).to.equal('Bearer test-access-token');
        });
        it('redirects to login when no access token', async () => {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            let threw = false;
            try {
                await fetchWithAuth('/api/v1/test');
            }
            catch (e) {
                threw = true;
                expect(e.message).to.include('Not authenticated');
            }
            expect(threw).to.be.true;
            expect(routerGoStub).to.have.been.calledWith('/login');
        });
        it('refreshes token and retries on 401', async () => {
            const successResponse = new Response(JSON.stringify({ data: 'ok' }), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            });
            let callCount = 0;
            fetchStub.callsFake(async (input) => {
                callCount++;
                const url = typeof input === 'string' ? input : input.toString();
                if (callCount === 1) {
                    return new Response(JSON.stringify({}), {
                        status: 401,
                        headers: { 'Content-Type': 'application/json' },
                    });
                }
                if (url.includes('/api/v1/auth/refresh')) {
                    return new Response(JSON.stringify({
                        access_token: 'new-access-token',
                        refresh_token: 'new-refresh-token',
                    }), { status: 200, headers: { 'Content-Type': 'application/json' } });
                }
                return successResponse;
            });
            const response = await fetchWithAuth('/api/v1/test');
            expect(response?.status).to.equal(200);
            expect(fetchStub).to.have.been.calledThrice; // initial 401, refresh, retry
            const refreshCall = fetchStub
                .getCalls()
                .find((c) => String(c.args[0]).includes('/api/v1/auth/refresh'));
            expect(refreshCall).to.exist;
            const retryCall = fetchStub
                .getCalls()
                .find((c) => String(c.args[0]) === '/api/v1/test' &&
                c.args[1]?.headers &&
                c.args[1].headers instanceof Headers &&
                c.args[1].headers.get('Authorization') === 'Bearer new-access-token');
            expect(retryCall).to.exist;
        });
        it('redirects to login when refresh fails on 401', async () => {
            fetchStub.callsFake(async (input) => {
                const url = typeof input === 'string' ? input : input.toString();
                if (url.includes('/api/v1/auth/refresh')) {
                    return new Response(JSON.stringify({ detail: 'Invalid refresh token' }), { status: 401, headers: { 'Content-Type': 'application/json' } });
                }
                return new Response(JSON.stringify({}), {
                    status: 401,
                    headers: { 'Content-Type': 'application/json' },
                });
            });
            let threw = false;
            try {
                await fetchWithAuth('/api/v1/test');
            }
            catch (e) {
                threw = true;
                expect(e.message).to.include('Failed to refresh token, redirecting to login.');
            }
            expect(threw).to.be.true;
            expect(routerGoStub).to.have.been.calledWith('/login');
        });
    });
    describe('AuthedElement.fetchData', () => {
        it('returns parsed JSON on success', async () => {
            const testData = { id: '1', name: 'Test' };
            fetchStub.resolves(new Response(JSON.stringify(testData), {
                status: 200,
                headers: { 'Content-Type': 'application/json' },
            }));
            const el = document.createElement('test-authed-element');
            document.body.appendChild(el);
            await el.updateComplete;
            const result = await el.fetchDataForTest('/api/v1/test');
            expect(result).to.deep.equal(testData);
            document.body.removeChild(el);
        });
        it('returns null on HTTP error', async () => {
            fetchStub.resolves(new Response(JSON.stringify({ detail: 'Not found' }), {
                status: 404,
                headers: { 'Content-Type': 'application/json' },
            }));
            const el = document.createElement('test-authed-element');
            document.body.appendChild(el);
            await el.updateComplete;
            const result = await el.fetchDataForTest('/api/v1/test');
            expect(result).to.be.null;
            document.body.removeChild(el);
        });
        it('returns null when fetchWithAuth throws (e.g. auth failure)', async () => {
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            const el = document.createElement('test-authed-element');
            document.body.appendChild(el);
            await el.updateComplete;
            const result = await el.fetchDataForTest('/api/v1/test');
            expect(result).to.be.null;
            document.body.removeChild(el);
        });
    });
});
