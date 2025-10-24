import { LitElement } from 'lit';
import { Router } from '@vaadin/router';
import { DEFAULT_SIMILARITY_THRESHOLD } from './config';
import type {
  FetchIssuesListParams,
  SearchIssuesParams,
  SearchIssuesResponse,
  ApiKey,
  Project,
  Organization,
  Issue,
  DuplicatePair,
  DuplicatesResponse,
  IssueComplianceResult,
  CompliancePromptMetadata,
  ComplianceSuggestion,
  DependencyResponse,
} from './types';

async function refreshToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem('refreshToken');
  if (!refreshToken) {
    console.error('No refresh token available');
    return null;
  }

  try {
    const response = await fetch(`/api/v1/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      throw new Error('Failed to refresh token');
    }

    const data = await response.json();
    localStorage.setItem('accessToken', data.access_token);
    localStorage.setItem('refreshToken', data.refresh_token);
    return data.access_token;
  } catch (error) {
    console.error('Error refreshing token:', error);
    // Clear tokens and redirect to login
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    Router.go('/login');
    return null;
  }
}

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
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
    } else {
      // If refresh fails, the refreshToken function will handle redirection
      Router.go('/login');
      throw new Error('Failed to refresh token, redirecting to login.');
    }
  }

  if (response.status === 429) {
    window.dispatchEvent(
      new CustomEvent('show-upgrade-modal', {
        bubbles: true,
        composed: true,
      })
    );
  }

  return response;
}
export async function fetchPublic(
  url: string,
  options: RequestInit = {}
): Promise<Response> {
  const response = await fetch(url, options);
  // You might want to add basic error handling here if needed
  return response;
}

export class AuthedElement extends LitElement {
  protected async fetchData(url: string, options: RequestInit = {}) {
    try {
      const response = await fetchWithAuth(url, options);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      return await response.json();
    } catch (error) {
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

export async function getTrackers() {
  const response = await fetchWithAuth('/api/v1/trackers');
  if (!response.ok) {
    throw new Error('Failed to fetch trackers');
  }
  return response.json();
}

export async function addTracker(trackerData: any) {
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

export async function updateTracker(trackerId: string, trackerData: any) {
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

export async function validateTrackerToken(
  type: string,
  token: string,
  url?: string,
  username?: string,
  id?: string
) {
  console.log('Validating tracker token', type, token, url, username);
  const payload: {
    tracker_id?: string;
    tracker_type: string;
    api_key: string;
    url?: string;
    connection_details?: { username?: string };
  } = {
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

export async function listProjectsForOrg(
  trackerType: string,
  token: string,
  orgId: string,
  url?: string,
  username?: string,
  trackerId?: string
) {
  const payload: any = {
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

  const response = await fetchWithAuth(
    '/api/v1/trackers/list-projects-for-org',
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.message || 'Failed to list projects for organization'
    );
  }
  return response.json();
}

export async function getDuplicateIssues(
  status: 'opened' | 'closed' | 'all' = 'opened'
) {
  const response = await fetchWithAuth(
    `/api/v1/issue-duplicates/?status=${status}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch duplicate issues');
  }
  return response.json();
}

export async function getIssueCount(): Promise<{ total_issues: number }> {
  const response = await fetchWithAuth('/api/v1/issues-count');
  if (!response.ok) {
    throw new Error('Failed to fetch issue count');
  }
  return response.json();
}

export async function searchIssues(
  params: FetchIssuesListParams
): Promise<any[]> {
  const queryParams = new URLSearchParams();
  queryParams.append('search_type', 'similarity');
  queryParams.append('embedding_type', 'issue');

  if (params.query) {
    queryParams.append('query', params.query);
  } else {
    // The new endpoint requires a query, so we'll use an empty one to get all issues.
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

  const response = await fetchWithAuth(
    `/api/v1/search?${queryParams.toString()}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch issues list');
  }
  const data = await response.json();
  return data.results.map((r: any) => r.item);
}

export async function post(url: string, body: any) {
  const response = await window.fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include',
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  return response.json();
}

export async function detectIssueDependencies(
  issueIds: string[]
): Promise<DependencyResponse> {
  const response = await fetchWithAuth('/api/v1/issue-dependencies/detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_ids: issueIds }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to detect issue dependencies');
  }
  return response.json();
}

export async function extendIssueDependencyScan(
  issueIds: string[],
  extendBy: number
): Promise<DependencyResponse> {
  const response = await fetchWithAuth('/api/v1/issue-dependencies/extend', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ issue_ids: issueIds, extend_by: extendBy }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || 'Failed to extend issue dependency scan'
    );
  }
  return response.json();
}

export async function commitIssueDependencies(
  dependencies: DependencyPair[]
): Promise<DependencyResponse> {
  const response = await fetchWithAuth('/api/v1/issue-dependencies/commit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dependencies }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to commit issue dependencies');
  }
  return response.json();
}

// Account
export async function getAccountDetails() {
  const response = await fetchWithAuth('/api/v1/auth/users/me');
  if (!response.ok) {
    throw new Error('Failed to fetch account details');
  }
  return response.json();
}

export async function updateAccountDetails(details: { full_name: string }) {
  const response = await fetchWithAuth('/api/v1/auth/users/me', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(details),
  });
  if (!response.ok) {
    throw new Error('Failed to update account details');
  }
  return response.json();
}

export async function changePassword(passwords: {
  current_password: string;
  new_password: string;
}) {
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
    throw new Error(errorData.detail || 'Failed to change password');
  }
}

// API Keys
export async function getApiKeys(): Promise<ApiKey[]> {
  const response = await fetchWithAuth('/api/v1/auth/api-keys');
  if (!response.ok) {
    throw new Error('Failed to fetch API keys');
  }
  return response.json();
}

export async function createApiKey(
  name: string,
  expires_at: string | null
): Promise<ApiKey> {
  const body = { name, expires_at };
  const response = await fetchWithAuth('/api/v1/auth/api-keys', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error('Failed to create API key');
  }
  return response.json();
}

export async function deleteApiKey(keyId: string) {
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

export async function createAIModel(model: any) {
  const response = await fetchWithAuth('/api/v1/ai-models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  });
  if (!response.ok) {
    throw new Error('Failed to create AI model');
  }
  return response.json();
}

export async function updateAIModel(modelId: string, model: any) {
  const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  });
  if (!response.ok) {
    throw new Error('Failed to update AI model');
  }
  return response.json();
}

export async function deleteAIModel(modelId: string) {
  const response = await fetchWithAuth(`/api/v1/ai-models/${modelId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete AI model');
  }
}

// Flows
export async function getFlows(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/flows');
  if (!response.ok) {
    throw new Error('Failed to fetch flows');
  }
  return response.json();
}

export async function getFlow(flowId: string): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/flows/${flowId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch flow');
  }
  return response.json();
}

export async function createFlow(flow: any): Promise<any> {
  const response = await fetchWithAuth('/api/v1/flows', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(flow),
  });
  if (!response.ok) {
    throw new Error('Failed to create flow');
  }
  return response.json();
}

export async function updateFlow(flowId: string, flow: any): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/flows/${flowId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(flow),
  });
  if (!response.ok) {
    throw new Error('Failed to update flow');
  }
  return response.json();
}

export async function deleteFlow(flowId: string) {
  const response = await fetchWithAuth(`/api/v1/flows/${flowId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete flow');
  }
}

export async function getFlowPresets(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/flows/presets');
  if (!response.ok) {
    throw new Error('Failed to fetch flow presets');
  }
  return response.json();
}

export async function getFlowExecutions(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/flows/executions');
  if (!response.ok) {
    throw new Error('Failed to fetch flow executions');
  }
  return response.json();
}

export async function getFlowExecution(executionId: string): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/flows/executions/${executionId}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch flow execution');
  }
  return response.json();
}

export async function triggerFlowExecution(flowId: string): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/flows/${flowId}/trigger`, {
    method: 'POST',
  });
  if (!response.ok) {
    throw new Error('Failed to trigger flow execution');
  }
  return response.json();
}

export async function sendCommandToExecution(
  executionId: string,
  command: string,
  payload?: any
): Promise<void> {
  const response = await fetchWithAuth(
    `/api/v1/flows/executions/${executionId}/command`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ command, payload }),
    }
  );
  if (!response.ok) {
    throw new Error('Failed to send command to execution');
  }
}

export async function cloneFlowPreset(presetId: string): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/flows/presets/${presetId}/clone`,
    {
      method: 'POST',
    }
  );
  if (!response.ok) {
    throw new Error('Failed to clone flow preset');
  }
  return response.json();
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetchWithAuth('/api/v1/projects');
  if (!response.ok) {
    throw new Error('Failed to fetch projects');
  }
  return response.json();
}

export async function getEmbeddingsForProjects(
  projectIds: string[]
): Promise<{ data: any[] } | null> {
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
  } catch (error) {
    console.error('Error in getEmbeddingsForProjects:', error);
    return null;
  }
}

export async function listOrganizations(): Promise<Organization[]> {
  const response = await fetchWithAuth('/api/v1/organizations');
  if (!response.ok) {
    throw new Error('Failed to fetch organizations');
  }
  const data: any = await response.json();
  return data.items;
}

export async function listIssueDuplicates(
  options: {
    limit?: number;
    skip?: number;
    project_ids?: string[];
    similarity_threshold?: number;
    status?: 'opened' | 'closed' | 'all';
    resolution?: 'resolved' | 'unresolved' | 'all';
  } = {}
): Promise<DuplicatesResponse> {
  const {
    limit = 10,
    skip = 0,
    project_ids = [],
    status = 'opened',
    similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD,
    resolution = 'all',
  } = options;

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

  const response = await fetchWithAuth(
    `/api/v1/issue-duplicates?${params.toString()}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch duplicate issues');
  }
  return response.json();
}

export async function checkAIVerdict(issue1_id: string, issue2_id: string) {
  const response = await fetchWithAuth(
    `/api/v1/issue-duplicates/check?issue1_id=${issue1_id}&issue2_id=${issue2_id}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch AI verdict');
  }
  return response.json();
}

export async function getProjectDuplicateStats(options: {
  project_ids?: string[];
  status?: 'opened' | 'closed' | 'all';
  similarity_threshold?: number;
}): Promise<any> {
  const {
    project_ids = [],
    status = 'opened',
    similarity_threshold = DEFAULT_SIMILARITY_THRESHOLD,
  } = options;
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

export async function dismissDuplicatePair(
  issue1Id: string,
  issue2Id: string
): Promise<{ success: boolean }> {
  console.log(`Dismissing duplicate pair: ${issue1Id} and ${issue2Id}`);

  // Simulate network delay
  await new Promise((resolve) => setTimeout(resolve, 500));

  // In a real implementation, you would make a call to your backend here
  // to record the dismissal.

  return Promise.resolve({ success: true });
}

export async function getResolutionSuggestion(
  issue1_id: string,
  issue2_id: string,
  resolution: 'merged' | 'deconflicted'
): Promise<any> {
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

export async function executeIssueDuplicateResolution(
  resolutionData: any
): Promise<any> {
  const response = await fetchWithAuth(
    '/api/v1/issue-duplicates/execute-resolution',
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(resolutionData),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || 'Failed to execute issue duplicate resolution'
    );
  }
  return response.json();
}

export async function getIssueCompliance(
  issueId: string,
  promptName: string
): Promise<IssueComplianceResult> {
  const response = await fetchWithAuth(
    `/api/v1/issue_compliance/${issueId}?prompt_name=${promptName}`,
    {
      method: 'GET',
    }
  );
  if (!response.ok) {
    throw new Error('Failed to fetch issue compliance');
  }
  return response.json();
}

export async function getComplianceImprovementSuggestion(
  issueId: string,
  promptName: string
): Promise<ComplianceSuggestion> {
  const response = await fetchWithAuth(
    `/api/v1/issue_compliance_suggestion/${issueId}?prompt_name=${promptName}`
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      errorData.detail || 'Failed to get compliance improvement suggestion'
    );
  }
  return response.json();
}

export async function proposeResolution(resolutionData: any) {
  return await fetchWithAuth('/api/v1/issue-duplicates/propose-resolution', {
    method: 'PATCH',
    body: JSON.stringify(resolutionData),
  });
}

export async function updateIssueContent(
  issueId: string,
  title: string,
  description: string,
  changes: string
): Promise<Issue> {
  const response = await fetchWithAuth(
    `/api/v1/issue_compliance_update/${issueId}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, description, changes }),
    }
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update issue content');
  }

  return response.json();
}

export async function getCompliancePrompts(): Promise<
  CompliancePromptMetadata[]
> {
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
export async function getTools(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/tools');
  if (!response.ok) {
    throw new Error('Failed to fetch tools');
  }
  return response.json();
}

export async function createToolConfiguration(config: any): Promise<any> {
  const response = await fetchWithAuth('/api/v1/tool-configurations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to create tool configuration');
  }
  return response.json();
}

export async function getToolConfiguration(configId: string): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/tool-configurations/${configId}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch tool configuration');
  }
  return response.json();
}

export async function updateToolConfiguration(
  configId: string,
  config: any
): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/tool-configurations/${configId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update tool configuration');
  }
  return response.json();
}

export async function deleteToolConfiguration(configId: string): Promise<void> {
  const response = await fetchWithAuth(
    `/api/v1/tool-configurations/${configId}`,
    {
      method: 'DELETE',
    }
  );
  if (!response.ok) {
    throw new Error('Failed to delete tool configuration');
  }
}

// Approval Policies API
export async function getApprovalPolicies(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/approval-policies');
  if (!response.ok) {
    throw new Error('Failed to fetch approval policies');
  }
  return response.json();
}

export async function createApprovalPolicy(policy: any): Promise<any> {
  const response = await fetchWithAuth('/api/v1/approval-policies', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(policy),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to create approval policy');
  }
  return response.json();
}

export async function getApprovalPolicy(policyId: string): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/approval-policies/${policyId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch approval policy');
  }
  return response.json();
}

export async function updateApprovalPolicy(
  policyId: string,
  policy: any
): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/approval-policies/${policyId}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(policy),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update approval policy');
  }
  return response.json();
}

export async function deleteApprovalPolicy(policyId: string): Promise<void> {
  const response = await fetchWithAuth(
    `/api/v1/approval-policies/${policyId}`,
    {
      method: 'DELETE',
    }
  );
  if (!response.ok) {
    throw new Error('Failed to delete approval policy');
  }
}

// MCP Servers API
export async function getMCPServers(): Promise<any[]> {
  const response = await fetchWithAuth('/api/v1/mcp-servers');
  if (!response.ok) {
    throw new Error('Failed to fetch MCP servers');
  }
  return response.json();
}

export async function createMCPServer(server: any): Promise<any> {
  const response = await fetchWithAuth('/api/v1/mcp-servers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(server),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to create MCP server');
  }
  return response.json();
}

export async function getMCPServer(serverId: string): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`);
  if (!response.ok) {
    throw new Error('Failed to fetch MCP server');
  }
  return response.json();
}

export async function updateMCPServer(
  serverId: string,
  server: any
): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(server),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to update MCP server');
  }
  return response.json();
}

export async function deleteMCPServer(serverId: string): Promise<void> {
  const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete MCP server');
  }
}

export async function scanMCPServer(serverId: string): Promise<any> {
  const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}/scan`, {
    method: 'POST',
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to scan MCP server');
  }
  return response.json();
}

export async function getMCPServerTools(serverId: string): Promise<any[]> {
  const response = await fetchWithAuth(`/api/v1/mcp-servers/${serverId}/tools`);
  if (!response.ok) {
    throw new Error('Failed to fetch MCP server tools');
  }
  return response.json();
}

// Approval Requests API
export async function getApprovalRequest(requestId: string): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/approval-requests/${requestId}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch approval request');
  }
  return response.json();
}

export async function listApprovalRequests(params?: {
  status?: string;
  execution_id?: string;
  limit?: number;
  skip?: number;
}): Promise<any[]> {
  const queryParams = new URLSearchParams();
  if (params?.status) queryParams.append('status', params.status);
  if (params?.execution_id)
    queryParams.append('execution_id', params.execution_id);
  if (params?.limit) queryParams.append('limit', params.limit.toString());
  if (params?.skip) queryParams.append('skip', params.skip.toString());

  const response = await fetchWithAuth(
    `/api/v1/approval-requests?${queryParams.toString()}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch approval requests');
  }
  return response.json();
}

export async function approveRequest(
  requestId: string,
  comment?: string
): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/approval-requests/${requestId}/approve`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: true, comment: comment || null }),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to approve request');
  }
  return response.json();
}

export async function declineRequest(
  requestId: string,
  comment?: string
): Promise<any> {
  const response = await fetchWithAuth(
    `/api/v1/approval-requests/${requestId}/decline`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ approved: false, comment: comment || null }),
    }
  );
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || 'Failed to decline request');
  }
  return response.json();
}
