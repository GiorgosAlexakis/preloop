import { LitElement } from 'lit';
import { Router } from '@vaadin/router';

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
  id?: string,
  type: string,
  token: string,
  url?: string,
  username?: string
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
  trackerId: string,
  trackerType: string,
  token: string,
  orgId: string,
  url?: string,
  username?: string
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

export async function getDuplicateIssues() {
  const response = await fetchWithAuth('/api/v1/issue-duplicates/');
  if (!response.ok) {
    throw new Error('Failed to fetch duplicate issues');
  }
  return response.json();
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
export interface ApiKey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  key?: string;
}

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

// LLM Models
export async function getLlmModels() {
  const response = await fetchWithAuth('/api/v1/llm-models');
  if (!response.ok) {
    throw new Error('Failed to fetch LLM models');
  }
  return response.json();
}

export async function createLlmModel(model: any) {
  const response = await fetchWithAuth('/api/v1/llm-models', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  });
  if (!response.ok) {
    throw new Error('Failed to create LLM model');
  }
  return response.json();
}

export async function updateLlmModel(modelId: string, model: any) {
  const response = await fetchWithAuth(`/api/v1/llm-models/${modelId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(model),
  });
  if (!response.ok) {
    throw new Error('Failed to update LLM model');
  }
  return response.json();
}

export async function deleteLlmModel(modelId: string) {
  const response = await fetchWithAuth(`/api/v1/llm-models/${modelId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error('Failed to delete LLM model');
  }
}

export interface Project {
  id: number;
  name: string;
  identifier: string;
  organization_id: number;
}

export interface Organization {
  id: number;
  name: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetchWithAuth('/api/v1/projects');
  if (!response.ok) {
    throw new Error('Failed to fetch projects');
  }
  return response.json();
}

export interface IssueEmbedding {
  issue_id: string;
  project_id: string;
  issue_key: string;
  issue_title: string;
  issue_created_at: string;
  embedding: number[];
}

export async function getEmbeddingsForProjects(projectIds: string[]): Promise<{ data: IssueEmbedding[] } | null> {
    const params = new URLSearchParams();
    if (projectIds.length > 0) {
        params.append('project_ids', projectIds.join(','));
    }

    const queryString = params.toString();
    const url = queryString ? `/api/v1/embeddings?${queryString}` : '/api/v1/embeddings';

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
  const data: Paginated<Organization> = await response.json();
  return data.items;
}

// Add interfaces for the issue duplicates endpoint
export interface Issue {
  project_id: string;
  id: string;
  title: string;
  description: string;
  key: string;
  status: string;
  created_at: string;
  updated_at: string;
  url: string;
  meta_data?: { [key: string]: any };
}

export interface DuplicatePair {
  issue1: Issue;
  issue2: Issue;
  similarity: number;
}

export interface DuplicatesResponse {
  project_ids: string[];
  model_id_used: string;
  threshold_used: number;
  duplicates: DuplicatePair[];
}

export async function listIssueDuplicates(
  options: {
    limit?: number;
    skip?: number;
    project_ids?: string[];
    similarity_threshold?: number;
  } = {}
): Promise<DuplicatesResponse> {
  const params = new URLSearchParams();
  if (options.limit) params.append('limit', options.limit.toString());
  if (options.skip) params.append('skip', options.skip.toString());
  if (options.project_ids) {
    options.project_ids.forEach(id => params.append('project_ids', id));
  }
  if (options.similarity_threshold) {
    params.append(
      'similarity_threshold',
      options.similarity_threshold.toString()
    );
  }
  const response = await fetchWithAuth(
    `/api/v1/issue-duplicates?${params.toString()}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch duplicate issues');
  }
  return response.json();
}

export async function checkLlmVerdict(issue1_id: string, issue2_id: string) {
  const response = await fetchWithAuth(
    `/api/v1/issue-duplicates/check?issue1_id=${issue1_id}&issue2_id=${issue2_id}`
  );
  if (!response.ok) {
    throw new Error('Failed to fetch LLM verdict');
  }
  return response.json();
}
