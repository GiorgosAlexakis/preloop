import { LitElement } from 'lit';
import { Router } from '@vaadin/router';
import { DEFAULT_SIMILARITY_THRESHOLD } from './config';
// Global refresh promise to prevent concurrent refresh requests
let refreshPromise = null;
export function extractErrorMessage(errorData, defaultMessage) {
    if (errorData && errorData.detail) {
        if (Array.isArray(errorData.detail)) {
            return errorData.detail
                .map((item) => item.msg || JSON.stringify(item))
                .join(', ');
        }
        else if (typeof errorData.detail === 'object') {
            return JSON.stringify(errorData.detail);
        }
        return String(errorData.detail);
    }
    return defaultMessage;
}
async function refreshToken() {
    // If a refresh is already in progress, wait for it
    if (refreshPromise) {
        return refreshPromise;
    }
    // Start a new refresh
    refreshPromise = (async () => {
        try {
            const refreshTokenValue = localStorage.getItem('refreshToken');
            if (!refreshTokenValue) {
                console.error('No refresh token available');
                return null;
            }
            const response = await fetch(`/api/v1/auth/refresh`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ refresh_token: refreshTokenValue }),
            });
            if (!response.ok) {
                throw new Error('Failed to refresh token');
            }
            const data = await response.json();
            localStorage.setItem('accessToken', data.access_token);
            localStorage.setItem('refreshToken', data.refresh_token);
            return data.access_token;
        }
        catch (error) {
            console.error('Error refreshing token:', error);
            // Clear tokens and redirect to login
            localStorage.removeItem('accessToken');
            localStorage.removeItem('refreshToken');
            Router.go('/login');
            return null;
        }
        finally {
            // Clear the refresh promise so future requests can refresh again
            refreshPromise = null;
        }
    })();
    return refreshPromise;
}
export async function fetchWithAuth(url, options = {}) {
    let accessToken = localStorage.getItem('accessToken');
    if (!accessToken) {
        // This case should ideally not be hit if the app is correctly protecting routes
        console.error('No access token found');
        Router.go('/login');
        throw new Error('Not authenticated');
    }
    const headers = new Headers(options.headers || {});
    headers.set('Authorization', `Bearer ${accessToken}`);
    options.headers = headers;
    let response = await fetch(url, options);
    if (response.status === 401) {
        console.log('Access token expired, attempting to refresh...');
        const newAccessToken = await refreshToken();
        if (newAccessToken) {
            headers.set('Authorization', `Bearer ${newAccessToken}`);
            options.headers = headers;
            // Retry the request with the new token
            response = await fetch(url, options);
        }
        else {
            // If refresh fails, the refreshToken function will handle redirection
            Router.go('/login');
            throw new Error('Failed to refresh token, redirecting to login.');
        }
    }
    if (response.status === 429) {
        window.dispatchEvent(new CustomEvent('show-upgrade-modal', {
            bubbles: true,
            composed: true,
        }));
    }
    return response;
}
export async function fetchPublic(url, options = {}) {
    const response = await fetch(url, options);
    // You might want to add basic error handling here if needed
    return response;
}
export class AuthedElement extends LitElement {
    async fetchData(url, options = {}) {
        try {
            const response = await fetchWithAuth(url, options);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return await response.json();
        }
        catch (error) {
            console.error('Failed to fetch data:', error);
            // The fetchWithAuth function handles redirection on auth failure
            return null;
        }
    }
}
export async function getApiUsageStats() {
    const response = await fetchWithAuth('/api/v1/auth/api-usage');
    if (!response.ok) {
        throw new Error('Failed to fetch API usage stats');
    }
    return response.json();
}
function buildGatewayUsageQuery(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.startDate) {
        queryParams.set('start_date', params.startDate);
    }
    if (params.endDate) {
        queryParams.set('end_date', params.endDate);
    }
    if (params.query) {
        queryParams.set('query', params.query);
    }
    if (params.providerName) {
        queryParams.set('provider_name', params.providerName);
    }
    if (params.modelAlias) {
        queryParams.set('model_alias', params.modelAlias);
    }
    if (params.flowId) {
        queryParams.set('flow_id', params.flowId);
    }
    if (params.runtimeSessionId) {
        queryParams.set('runtime_session_id', params.runtimeSessionId);
    }
    if (params.sessionSourceType) {
        queryParams.set('session_source_type', params.sessionSourceType);
    }
    if (typeof params.limit === 'number') {
        queryParams.set('limit', String(params.limit));
    }
    if (typeof params.offset === 'number') {
        queryParams.set('offset', String(params.offset));
    }
    const queryString = queryParams.toString();
    return queryString ? `?${queryString}` : '';
}
function buildRuntimeSessionListQuery(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.startDate) {
        queryParams.set('start_date', params.startDate);
    }
    if (params.endDate) {
        queryParams.set('end_date', params.endDate);
    }
    if (params.query) {
        queryParams.set('query', params.query);
    }
    if (params.sessionSourceType) {
        queryParams.set('session_source_type', params.sessionSourceType);
    }
    if (params.status) {
        queryParams.set('status', params.status);
    }
    if (typeof params.limit === 'number') {
        queryParams.set('limit', String(params.limit));
    }
    if (typeof params.offset === 'number') {
        queryParams.set('offset', String(params.offset));
    }
    const queryString = queryParams.toString();
    return queryString ? `?${queryString}` : '';
}
function buildManagedAgentListQuery(params = {}) {
    const queryParams = new URLSearchParams();
    if (params.query) {
        queryParams.set('query', params.query);
    }
    if (params.sessionSourceType) {
        queryParams.set('session_source_type', params.sessionSourceType);
    }
    if (params.status) {
        queryParams.set('status', params.status);
    }
    if (typeof params.limit === 'number') {
        queryParams.set('limit', String(params.limit));
    }
    if (typeof params.offset === 'number') {
        queryParams.set('offset', String(params.offset));
    }
    const queryString = queryParams.toString();
    return queryString ? `?${queryString}` : '';
}
export async function getAccountGatewayUsageSummary(params = {}) {
    const response = await fetchWithAuth(`/api/v1/account/gateway-usage/summary${buildGatewayUsageQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch account gateway usage summary');
    }
    return response.json();
}
export async function getFlowGatewayUsageSummary(flowId, params = {}) {
    const response = await fetchWithAuth(`/api/v1/flows/${flowId}/gateway-usage/summary${buildGatewayUsageQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch flow gateway usage summary');
    }
    return response.json();
}
export async function getAccountGatewayUsageSearch(params = {}) {
    const response = await fetchWithAuth(`/api/v1/account/gateway-usage/search${buildGatewayUsageQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch account gateway usage search results');
    }
    return response.json();
}
export async function getAccountRuntimeSessions(params = {}) {
    const response = await fetchWithAuth(`/api/v1/runtime-sessions${buildRuntimeSessionListQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch sessions');
    }
    return response.json();
}
export async function getAccountAgents(params = {}) {
    const response = await fetchWithAuth(`/api/v1/agents${buildManagedAgentListQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch managed agents');
    }
    return response.json();
}
export async function getAccountAgent(agentId) {
    const response = await fetchWithAuth(`/api/v1/agents/${agentId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch managed agent');
    }
    return response.json();
}
export async function updateAccountAgent(agentId, payload) {
    const response = await fetchWithAuth(`/api/v1/agents/${agentId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error('Failed to update managed agent');
    }
    return response.json();
}
export async function getAccountRuntimeSessionDetail(runtimeSessionId, params = {}) {
    const queryParams = new URLSearchParams();
    if (params.startDate) {
        queryParams.set('start_date', params.startDate);
    }
    if (params.endDate) {
        queryParams.set('end_date', params.endDate);
    }
    if (params.interactionQuery) {
        queryParams.set('interaction_query', params.interactionQuery);
    }
    if (typeof params.interactionLimit === 'number') {
        queryParams.set('interaction_limit', String(params.interactionLimit));
    }
    if (typeof params.interactionOffset === 'number') {
        queryParams.set('interaction_offset', String(params.interactionOffset));
    }
    const queryString = queryParams.toString();
    const response = await fetchWithAuth(`/api/v1/runtime-sessions/${runtimeSessionId}${queryString ? `?${queryString}` : ''}`);
    if (!response.ok) {
        throw new Error('Failed to fetch session detail');
    }
    return response.json();
}
export async function updateAccountRuntimeSession(runtimeSessionId, payload) {
    const response = await fetchWithAuth(`/api/v1/runtime-sessions/${runtimeSessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        throw new Error('Failed to update session');
    }
    return response.json();
}
export async function getTrackers() {
    const response = await fetchWithAuth('/api/v1/trackers');
    if (!response.ok) {
        throw new Error('Failed to fetch trackers');
    }
    return response.json();
}
export async function addTracker(trackerData) {
    const response = await fetchWithAuth('/api/v1/trackers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(trackerData),
    });
    if (!response.ok) {
        throw new Error('Failed to add tracker');
    }
    return response.json();
}
export async function updateTracker(trackerId, trackerData) {
    const response = await fetchWithAuth(`/api/v1/trackers/${trackerId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(trackerData),
    });
    if (!response.ok) {
        throw new Error('Failed to update tracker');
    }
    return response.json();
}
export async function validateTrackerToken(type, token, url, username, id) {
    console.log('Validating tracker token', type, token, url, username);
    const payload = {
        tracker_type: type,
        api_key: token,
    };
    if (id) {
        payload.tracker_id = id;
    }
    if (url) {
        payload.url = url;
    }
    if (type.toLowerCase() === 'jira' && username) {
        payload.connection_details = { username };
    }
    const response = await fetchWithAuth('/api/v1/trackers/test-and-list-orgs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Failed to validate token');
    }
    return response.json();
}
export async function listProjectsForOrg(trackerType, token, orgId, url, username, trackerId) {
    const payload = {
        tracker_id: trackerId,
        tracker_type: trackerType,
        api_key: token,
        organization_identifier: orgId,
    };
    if (url) {
        payload.url = url;
    }
    if (trackerType.toLowerCase() === 'jira' && username) {
        payload.connection_details = { username };
    }
    const response = await fetchWithAuth('/api/v1/trackers/list-projects-for-org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.message || 'Failed to list projects for organization');
    }
    return response.json();
}
export async function getDuplicateIssues(status = 'opened') {
    const response = await fetchWithAuth(`/api/v1/issue-duplicates/?status=${status}`);
    if (!response.ok) {
        throw new Error('Failed to fetch duplicate issues');
    }
    return response.json();
}
export async function getIssueCount() {
    const response = await fetchWithAuth('/api/v1/issues-count');
    if (!response.ok) {
        throw new Error('Failed to fetch issue count');
    }
    return response.json();
}
export async function searchIssues(params) {
    const queryParams = new URLSearchParams();
    // Use similarity search when there's a query, fulltext otherwise
    if (params.query && params.query.trim()) {
        queryParams.append('search_type', 'similarity');
        queryParams.append('embedding_type', 'issue');
        queryParams.append('query', params.query);
    }
    else {
        // Use fulltext search with empty query to list all issues
        queryParams.append('search_type', 'fulltext');
        queryParams.append('query', '');
        queryParams.append('sort', 'newest');
    }
    if (params.limit) {
        queryParams.append('limit', params.limit.toString());
    }
    if (params.skip) {
        queryParams.append('skip', params.skip.toString());
    }
    if (params.project_ids && params.project_ids.length > 0) {
        params.project_ids.forEach((id) => queryParams.append('project_id', id));
    }
    if (params.status) {
        queryParams.append('status', params.status);
    }
    const response = await fetchWithAuth(`/api/v1/search?${queryParams.toString()}`);
    if (!response.ok) {
        throw new Error('Failed to fetch issues list');
    }
    const data = await response.json();
    return data.results.map((r) => r.item);
}
export async function post(url, body) {
    const response = await window.fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        // Try to extract error detail from response body
        let errorMessage = `HTTP error! status: ${response.status}`;
        try {
            const errorData = await response.json();
            if (errorData.detail) {
                errorMessage = extractErrorMessage(errorData, errorMessage);
            }
        }
        catch (e) {
            // If JSON parsing fails, use the default error message
        }
        throw new Error(errorMessage);
    }
    return response.json();
}
export async function detectIssueDependencies(issueIds) {
    const response = await fetchWithAuth('/api/v1/issue-dependencies/detect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_ids: issueIds }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to detect issue dependencies'));
    }
    return response.json();
}
export async function extendIssueDependencyScan(issueIds, extendBy) {
    const response = await fetchWithAuth('/api/v1/issue-dependencies/extend', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ issue_ids: issueIds, extend_by: extendBy }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to extend issue dependency scan'));
    }
    return response.json();
}
export async function commitIssueDependencies(dependencies) {
    const response = await fetchWithAuth('/api/v1/issue-dependencies/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dependencies }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to commit issue dependencies'));
    }
    return response.json();
}
// Account
export async function getUserProfile() {
    const response = await fetchWithAuth('/api/v1/auth/users/me');
    if (!response.ok) {
        throw new Error('Failed to fetch user profile');
    }
    return response.json();
}
export async function getAccountDetails() {
    const response = await fetchWithAuth('/api/v1/account/details');
    if (!response.ok) {
        throw new Error('Failed to fetch account details');
    }
    return response.json();
}
export async function updateUserProfile(details) {
    const response = await fetchWithAuth('/api/v1/auth/users/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(details),
    });
    if (!response.ok) {
        throw new Error('Failed to update user profile');
    }
    return response.json();
}
export async function changePassword(passwords) {
    const response = await fetchWithAuth('/api/v1/auth/users/me/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(passwords),
    });
    if (response.status === 204) {
        return;
    }
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to change password'));
    }
}
// API Keys
export async function getApiKeys() {
    const response = await fetchWithAuth('/api/v1/auth/api-keys');
    if (!response.ok) {
        throw new Error('Failed to fetch API keys');
    }
    return response.json();
}
export async function createApiKey(name, expires_at) {
    const body = { name, expires_at };
    const response = await fetchWithAuth('/api/v1/auth/api-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create API key'));
    }
    return response.json();
}
export async function deleteApiKey(keyId) {
    const response = await fetchWithAuth(`/api/v1/auth/api-keys/${keyId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete API key');
    }
}
// AI Models
export async function getAIModels() {
    const response = await fetchWithAuth('/api/v1/ai-models');
    if (!response.ok) {
        throw new Error('Failed to fetch AI models');
    }
    return response.json();
}
export async function getAIModel(modelId) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI model');
    }
    return response.json();
}
export async function createAIModel(model) {
    const response = await fetchWithAuth('/api/v1/ai-models', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(model),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create AI model'));
    }
    return response.json();
}
export async function updateAIModel(modelId, model) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(model),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update AI model'));
    }
    return response.json();
}
export async function deleteAIModel(modelId) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to delete AI model'));
    }
}
export async function getAvailableModelsForProvider(provider, apiKey) {
    let url = `/api/v1/ai-models/providers/${provider}/available-models`;
    if (apiKey) {
        url += `?api_key=${encodeURIComponent(apiKey)}`;
    }
    // Use fetch instead of fetchWithAuth since this endpoint doesn't require authentication
    const response = await fetch(url);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to fetch available models'));
    }
    return response.json();
}
export async function getAIModelGatewayUsageSummary(modelId, params = {}) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}/summary${buildGatewayUsageQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI model usage summary');
    }
    return response.json();
}
export async function getAIModelRuntimeSessions(modelId, params = {}) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}/runtime-sessions${buildRuntimeSessionListQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI model runtime sessions');
    }
    return response.json();
}
export async function getAIModelGatewayUsageSearch(modelId, params = {}) {
    const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}/interactions${buildGatewayUsageQuery(params)}`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI model interactions');
    }
    return response.json();
}
// Flows
export async function getFlows() {
    const response = await fetchWithAuth('/api/v1/flows');
    if (!response.ok) {
        throw new Error('Failed to fetch flows');
    }
    return response.json();
}
export async function getFlow(flowId) {
    const response = await fetchWithAuth(`/api/v1/flows/${flowId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch flow');
    }
    return response.json();
}
export async function createFlow(flow) {
    const response = await fetchWithAuth('/api/v1/flows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to create flow');
    }
    return response.json();
}
export async function updateFlow(flowId, flow) {
    const response = await fetchWithAuth(`/api/v1/flows/${flowId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(flow),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to update flow');
    }
    return response.json();
}
export async function deleteFlow(flowId) {
    const response = await fetchWithAuth(`/api/v1/flows/${flowId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete flow');
    }
}
export async function getFlowPresets() {
    const response = await fetchWithAuth('/api/v1/flows/presets');
    if (!response.ok) {
        throw new Error('Failed to fetch flow presets');
    }
    return response.json();
}
export async function getFlowExecutions(options) {
    const params = new URLSearchParams();
    if (options?.limit !== undefined) {
        params.set('limit', options.limit.toString());
    }
    if (options?.skip !== undefined) {
        params.set('skip', options.skip.toString());
    }
    const queryString = params.toString();
    const url = `/api/v1/flows/executions${queryString ? `?${queryString}` : ''}`;
    const response = await fetchWithAuth(url);
    if (!response.ok) {
        throw new Error('Failed to fetch flow executions');
    }
    return response.json();
}
export async function getFlowExecution(executionId) {
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch flow execution');
    }
    return response.json();
}
export async function getFlowExecutionMetrics(executionId) {
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}/metrics`);
    if (!response.ok) {
        throw new Error('Failed to fetch execution metrics');
    }
    return response.json();
}
export async function getFlowExecutionLogs(executionId, tail) {
    const params = tail !== undefined ? `?tail=${tail}` : '';
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}/logs${params}`);
    if (!response.ok) {
        throw new Error('Failed to fetch execution logs');
    }
    return response.json();
}
export async function getFlowExecutionGatewayEvents(executionId, tail) {
    const params = tail !== undefined ? `?tail=${tail}` : '';
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}/gateway-events${params}`);
    if (!response.ok) {
        throw new Error('Failed to fetch execution gateway events');
    }
    return response.json();
}
export async function triggerFlowExecution(flowId, triggerEventData) {
    const response = await fetchWithAuth(`/api/v1/flows/${flowId}/trigger`, {
        method: 'POST',
        headers: triggerEventData
            ? { 'Content-Type': 'application/json' }
            : undefined,
        body: triggerEventData ? JSON.stringify(triggerEventData) : undefined,
    });
    if (!response.ok) {
        throw new Error('Failed to trigger flow execution');
    }
    return response.json();
}
export async function sendCommandToExecution(executionId, command, payload) {
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}/command`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, payload }),
    });
    if (!response.ok) {
        throw new Error('Failed to send command to execution');
    }
}
export async function retryFlowExecution(executionId) {
    const response = await fetchWithAuth(`/api/v1/flows/executions/${executionId}/retry`, {
        method: 'POST',
    });
    if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || 'Failed to retry flow execution');
    }
    return response.json();
}
export async function cloneFlowPreset(presetId) {
    const response = await fetchWithAuth(`/api/v1/flows/presets/${presetId}/clone`, {
        method: 'POST',
    });
    if (!response.ok) {
        throw new Error('Failed to clone flow preset');
    }
    return response.json();
}
export async function listProjects() {
    const response = await fetchWithAuth('/api/v1/projects');
    if (!response.ok) {
        throw new Error('Failed to fetch projects');
    }
    return response.json();
}
export async function getEmbeddingsForProjects(projectIds) {
    const params = new URLSearchParams();
    if (projectIds.length > 0) {
        params.append('project_ids', projectIds.join(','));
    }
    const queryString = params.toString();
    const url = queryString
        ? `/api/v1/embeddings?${queryString}`
        : '/api/v1/embeddings';
    try {
        const response = await fetchWithAuth(url);
        if (!response.ok) {
            console.error('Failed to fetch embeddings:', response.statusText);
            throw new Error('Failed to fetch embeddings for projects');
        }
        return await response.json();
    }
    catch (error) {
        console.error('Error in getEmbeddingsForProjects:', error);
        return null;
    }
}
export async function listOrganizations() {
    const response = await fetchWithAuth('/api/v1/organizations');
    if (!response.ok) {
        throw new Error('Failed to fetch organizations');
    }
    const data = await response.json();
    return data.items;
}
export async function listIssueDuplicates(options = {}) {
    const { limit = 10, skip = 0, project_ids = [], status = 'opened', similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD, resolution = 'all', } = options;
    const params = new URLSearchParams({
        limit: limit.toString(),
        skip: skip.toString(),
    });
    project_ids.forEach((id) => params.append('project_ids', id));
    params.append('status', status);
    params.append('similarity_threshold', similarity_threshold.toString());
    if (resolution && resolution !== 'all') {
        params.append('resolution', resolution);
    }
    const response = await fetchWithAuth(`/api/v1/issue-duplicates?${params.toString()}`);
    if (!response.ok) {
        throw new Error('Failed to fetch duplicate issues');
    }
    return response.json();
}
export async function checkAIVerdict(issue1_id, issue2_id) {
    const response = await fetchWithAuth(`/api/v1/issue-duplicates/check?issue1_id=${issue1_id}&issue2_id=${issue2_id}`);
    if (!response.ok) {
        throw new Error('Failed to fetch AI verdict');
    }
    return response.json();
}
export async function getProjectDuplicateStats(options) {
    const { project_ids = [], status = 'opened', similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD, } = options;
    const params = new URLSearchParams();
    project_ids.forEach((id) => params.append('project_ids', id));
    params.append('status', status);
    params.append('similarity_threshold', similarity_threshold.toString());
    const url = `/api/v1/project-duplicate-stats?${params.toString()}`;
    console.log(url);
    const response = await fetchWithAuth(url);
    if (!response.ok) {
        throw new Error('Failed to fetch project duplicate stats');
    }
    return response.json();
}
export async function dismissDuplicatePair(issue1Id, issue2Id) {
    console.log(`Dismissing duplicate pair: ${issue1Id} and ${issue2Id}`);
    // Simulate network delay
    await new Promise((resolve) => setTimeout(resolve, 500));
    // In a real implementation, you would make a call to your backend here
    // to record the dismissal.
    return Promise.resolve({ success: true });
}
export async function getResolutionSuggestion(issue1_id, issue2_id, resolution) {
    const response = await fetchWithAuth('/api/v1/ai-suggestion', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ issue1_id, issue2_id, resolution }),
    });
    if (!response.ok) {
        throw new Error('Failed to get resolution suggestion');
    }
    return response.json();
}
export async function executeIssueDuplicateResolution(resolutionData) {
    const response = await fetchWithAuth('/api/v1/issue-duplicates/execute-resolution', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(resolutionData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to execute issue duplicate resolution'));
    }
    return response.json();
}
export async function getIssueCompliance(issueId, promptName) {
    const response = await fetchWithAuth(`/api/v1/issue_compliance/${issueId}?prompt_name=${promptName}`, {
        method: 'GET',
    });
    if (!response.ok) {
        throw new Error('Failed to fetch issue compliance');
    }
    return response.json();
}
export async function getComplianceImprovementSuggestion(issueId, promptName) {
    const response = await fetchWithAuth(`/api/v1/issue_compliance_suggestion/${issueId}?prompt_name=${promptName}`);
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to get compliance improvement suggestion'));
    }
    return response.json();
}
export async function proposeResolution(resolutionData) {
    return await fetchWithAuth('/api/v1/issue-duplicates/propose-resolution', {
        method: 'PATCH',
        body: JSON.stringify(resolutionData),
    });
}
export async function updateIssueContent(issueId, title, description, changes) {
    const response = await fetchWithAuth(`/api/v1/issue_compliance_update/${issueId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, description, changes }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update issue content'));
    }
    return response.json();
}
export async function getCompliancePrompts() {
    const response = await fetchWithAuth('/api/v1/issue_compliance_prompts');
    if (!response.ok) {
        throw new Error('Failed to fetch compliance prompts');
    }
    return response.json();
}
// Billing
export async function fetchPlans() {
    const response = await fetchWithAuth('/api/v1/billing/plans');
    if (!response.ok) {
        throw new Error('Failed to fetch plans');
    }
    return response.json();
}
export async function getCurrentSubscription() {
    const response = await fetchWithAuth('/api/v1/billing/subscription');
    if (!response.ok) {
        if (response.status === 404) {
            return null; // No subscription found
        }
        throw new Error('Failed to fetch subscription');
    }
    return response.json();
}
// Tools API
export async function getTools() {
    const response = await fetchWithAuth('/api/v1/tools');
    if (!response.ok) {
        throw new Error('Failed to fetch tools');
    }
    return response.json();
}
export async function createToolConfiguration(config) {
    const response = await fetchWithAuth('/api/v1/tool-configurations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create tool configuration'));
    }
    return response.json();
}
export async function getToolConfiguration(configId) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch tool configuration');
    }
    return response.json();
}
export async function updateToolConfiguration(configId, config) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update tool configuration'));
    }
    return response.json();
}
export async function deleteToolConfiguration(configId) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete tool configuration');
    }
}
// Tool Approval Condition API
export async function getToolApprovalCondition(configId) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}/approval-condition`);
    if (!response.ok) {
        // 404 is expected if no condition exists yet
        if (response.status === 404) {
            return null;
        }
        throw new Error('Failed to fetch tool approval condition');
    }
    return response.json();
}
export async function updateToolApprovalCondition(configId, condition) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}/condition`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approval_condition: condition }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update tool approval condition'));
    }
    return response.json();
}
export async function listAccessRules(configId) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}/access-rules`);
    if (!response.ok) {
        throw new Error('Failed to fetch access rules');
    }
    return response.json();
}
export async function createAccessRule(configId, rule) {
    const response = await fetchWithAuth(`/api/v1/tool-configurations/${configId}/access-rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rule),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create access rule'));
    }
    return response.json();
}
export async function updateAccessRule(ruleId, rule) {
    const response = await fetchWithAuth(`/api/v1/access-rules/${ruleId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(rule),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update access rule'));
    }
    return response.json();
}
export async function deleteAccessRule(ruleId) {
    const response = await fetchWithAuth(`/api/v1/access-rules/${ruleId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete access rule');
    }
}
// Approval Workflows API
export async function getApprovalWorkflows() {
    const response = await fetchWithAuth('/api/v1/approval-workflows');
    if (!response.ok) {
        throw new Error('Failed to fetch approval workflows');
    }
    return response.json();
}
export async function createApprovalWorkflow(workflow) {
    const response = await fetchWithAuth('/api/v1/approval-workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create approval workflow'));
    }
    return response.json();
}
export async function getApprovalWorkflow(workflowId) {
    const response = await fetchWithAuth(`/api/v1/approval-workflows/${workflowId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch approval workflow');
    }
    return response.json();
}
export async function updateApprovalWorkflow(workflowId, workflow) {
    const response = await fetchWithAuth(`/api/v1/approval-workflows/${workflowId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(workflow),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update approval workflow'));
    }
    return response.json();
}
export async function deleteApprovalWorkflow(workflowId) {
    const response = await fetchWithAuth(`/api/v1/approval-workflows/${workflowId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete approval workflow');
    }
}
// MCP Servers API
export async function getMCPServers() {
    const response = await fetchWithAuth('/api/v1/mcp-servers');
    if (!response.ok) {
        throw new Error('Failed to fetch MCP servers');
    }
    return response.json();
}
export async function createMCPServer(server) {
    const response = await fetchWithAuth('/api/v1/mcp-servers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(server),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create MCP server'));
    }
    return response.json();
}
export async function getMCPServer(serverId) {
    const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch MCP server');
    }
    return response.json();
}
export async function updateMCPServer(serverId, server) {
    const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(server),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update MCP server'));
    }
    return response.json();
}
export async function deleteMCPServer(serverId) {
    const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        throw new Error('Failed to delete MCP server');
    }
}
export async function scanMCPServer(serverId) {
    const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}/scan`, {
        method: 'POST',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to scan MCP server'));
    }
    return response.json();
}
export async function getMCPServerTools(serverId) {
    const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}/tools`);
    if (!response.ok) {
        throw new Error('Failed to fetch MCP server tools');
    }
    return response.json();
}
// Tools API - Get all available tools (built-in and external)
export async function getAllTools() {
    const response = await fetchWithAuth('/api/v1/tools');
    if (!response.ok) {
        throw new Error('Failed to fetch tools');
    }
    return response.json();
}
// Approval Requests API
export async function getApprovalRequest(requestId) {
    const response = await fetchWithAuth(`/api/v1/approval-requests/${requestId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch approval request');
    }
    return response.json();
}
export async function listApprovalRequests(params) {
    const queryParams = new URLSearchParams();
    if (params?.status)
        queryParams.append('status', params.status);
    if (params?.execution_id)
        queryParams.append('execution_id', params.execution_id);
    if (params?.limit)
        queryParams.append('limit', params.limit.toString());
    if (params?.skip)
        queryParams.append('skip', params.skip.toString());
    const response = await fetchWithAuth(`/api/v1/approval-requests?${queryParams.toString()}`);
    if (!response.ok) {
        throw new Error('Failed to fetch approval requests');
    }
    return response.json();
}
export async function approveRequest(requestId, comment) {
    const response = await fetchWithAuth(`/api/v1/approval-requests/${requestId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: true, comment: comment || null }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to approve request'));
    }
    return response.json();
}
export async function declineRequest(requestId, comment) {
    const response = await fetchWithAuth(`/api/v1/approval-requests/${requestId}/decline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved: false, comment: comment || null }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to decline request'));
    }
    return response.json();
}
// ============================================================================
// User Management API Functions
// ============================================================================
export async function getUsers(skip = 0, limit = 100) {
    const response = await fetchWithAuth(`/api/v1/users?skip=${skip}&limit=${limit}`);
    if (!response.ok) {
        throw new Error('Failed to fetch users');
    }
    return response.json();
}
export async function getUser(userId) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch user');
    }
    return response.json();
}
export async function createUser(userData) {
    const response = await fetchWithAuth('/api/v1/users', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create user'));
    }
    return response.json();
}
export async function updateUser(userId, userData) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(userData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update user'));
    }
    return response.json();
}
export async function deleteUser(userId) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}/deactivate`, {
        method: 'POST',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to deactivate user'));
    }
}
// ============================================================================
// Team Management API Functions
// ============================================================================
export async function getTeams(skip = 0, limit = 100) {
    const response = await fetchWithAuth(`/api/v1/teams?skip=${skip}&limit=${limit}`);
    if (!response.ok) {
        throw new Error('Failed to fetch teams');
    }
    return response.json();
}
export async function getTeam(teamId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch team');
    }
    return response.json();
}
export async function createTeam(teamData) {
    const response = await fetchWithAuth('/api/v1/teams', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(teamData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create team'));
    }
    return response.json();
}
export async function updateTeam(teamId, teamData) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(teamData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to update team'));
    }
    return response.json();
}
export async function deleteTeam(teamId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to delete team'));
    }
}
export async function getTeamMembers(teamId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/members`);
    if (!response.ok) {
        throw new Error('Failed to fetch team members');
    }
    return response.json();
}
export async function addTeamMember(teamId, userId, roleId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/members`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, role_id: roleId }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to add team member'));
    }
    return response.json();
}
export async function removeTeamMember(teamId, userId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/members/${userId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to remove team member'));
    }
}
export async function getTeamRoles(teamId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/roles`);
    if (!response.ok) {
        throw new Error('Failed to fetch team roles');
    }
    return response.json();
}
export async function assignTeamRole(teamId, roleId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/roles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: roleId }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to assign role to team'));
    }
}
export async function removeTeamRole(teamId, roleId) {
    const response = await fetchWithAuth(`/api/v1/teams/${teamId}/roles/${roleId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to remove role from team'));
    }
}
// ============================================================================
// Invitation Management API Functions
// ============================================================================
export async function getInvitations(skip = 0, limit = 100, status) {
    let url = `/api/v1/invitations?skip=${skip}&limit=${limit}`;
    if (status) {
        url += `&status=${status}`;
    }
    const response = await fetchWithAuth(url);
    if (!response.ok) {
        throw new Error('Failed to fetch invitations');
    }
    return response.json();
}
export async function createInvitation(invitationData) {
    const response = await fetchWithAuth('/api/v1/invitations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(invitationData),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to create invitation'));
    }
    return response.json();
}
export async function resendInvitation(invitationId) {
    const response = await fetchWithAuth(`/api/v1/invitations/${invitationId}/resend`, {
        method: 'POST',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to resend invitation'));
    }
}
export async function cancelInvitation(invitationId) {
    const response = await fetchWithAuth(`/api/v1/invitations/${invitationId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to cancel invitation'));
    }
}
// ============================================================================
// Role Management API Functions
// ============================================================================
export async function getRoles() {
    const response = await fetchWithAuth('/api/v1/roles');
    if (!response.ok) {
        throw new Error('Failed to fetch roles');
    }
    return response.json();
}
export async function getUserRoles(userId) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}/roles`);
    if (!response.ok) {
        throw new Error('Failed to fetch user roles');
    }
    return response.json();
}
export async function assignUserRole(userId, roleId) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}/roles`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role_id: roleId }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to assign role'));
    }
}
export async function removeUserRole(userId, roleId) {
    const response = await fetchWithAuth(`/api/v1/users/${userId}/roles/${roleId}`, {
        method: 'DELETE',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to remove role'));
    }
}
export async function getFeatures() {
    const response = await fetchPublic('/api/v1/features');
    if (!response.ok) {
        throw new Error('Failed to fetch features');
    }
    return response.json();
}
export async function getAccountOrganization() {
    const response = await fetchWithAuth('/api/v1/account/details');
    if (!response.ok) {
        throw new Error('Failed to fetch account organization');
    }
    return response.json();
}
export async function updateAccountOrganization(details) {
    const response = await fetchWithAuth('/api/v1/account/details', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(details),
    });
    if (!response.ok) {
        throw new Error('Failed to update account organization');
    }
    return response.json();
}
export async function getTrackerAuthMethods() {
    const response = await fetchWithAuth('/api/v1/trackers/auth-methods');
    if (!response.ok) {
        throw new Error('Failed to fetch tracker auth methods');
    }
    return response.json();
}
export async function getGitHubAuthUrl() {
    const response = await fetchWithAuth('/api/v1/auth/github/authorize');
    if (!response.ok) {
        throw new Error('Failed to get GitHub authorization URL');
    }
    return response.json();
}
export async function getGitHubInstallations() {
    const response = await fetchWithAuth('/api/v1/github/installations');
    if (!response.ok) {
        throw new Error('Failed to fetch GitHub installations');
    }
    const data = await response.json();
    return data.installations;
}
export async function getGitHubInstallation(installationId) {
    const response = await fetchWithAuth(`/api/v1/github/installations/${installationId}`);
    if (!response.ok) {
        throw new Error('Failed to fetch GitHub installation');
    }
    return response.json();
}
export async function unlinkGitHubInstallation(installationId) {
    const response = await fetchWithAuth(`/api/v1/github/installations/${installationId}`, { method: 'DELETE' });
    if (!response.ok) {
        throw new Error('Failed to unlink GitHub installation');
    }
}
export async function completeGitHubInstallation(data) {
    // Backend expects installation_id and optional code as query parameters
    const params = new URLSearchParams();
    params.set('installation_id', data.installation_id);
    if (data.code) {
        params.set('code', data.code);
    }
    const response = await fetchWithAuth(`/api/v1/auth/github/complete-installation?${params.toString()}`, {
        method: 'POST',
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to complete GitHub installation');
    }
    return response.json();
}
// Policy Generation API
export async function generatePolicy(options) {
    const response = await fetchWithAuth('/api/v1/policies/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            prompt: options.prompt,
            include_current_config: options.includeCurrentConfig ?? true,
        }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to generate policy'));
    }
    return response.json();
}
export async function generatePolicyFromAudit(options) {
    const response = await fetchWithAuth('/api/v1/policies/generate-from-audit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            start_date: options?.startDate || null,
            end_date: options?.endDate || null,
        }),
    });
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(extractErrorMessage(errorData, 'Failed to generate policy from audit logs'));
    }
    return response.json();
}
