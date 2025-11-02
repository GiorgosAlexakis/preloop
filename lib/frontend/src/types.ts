export interface AIModel {
  id: string;
  name: string;
  provider_name: string;
  api_key: string;
  api_url: string;
  model_identifier: string;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
  account_id: string;
}

export interface FetchIssuesListParams {
  query?: string;
  project_ids?: string[];
  status?: 'opened' | 'closed' | 'all';
  limit?: number;
  skip?: number;
  sort_by?: string;
  sort_order?: string;
}

export interface SearchIssuesParams {
  query: string;
  search_type: 'similarity' | 'fulltext';
  embedding_type: 'issue' | 'comment';
  project_ids?: string[];
  limit?: number;
}

export interface SearchResultItem {
  item_type: 'issue' | 'comment';
  item: any; // Using 'any' for comment for now
  similarity: number;
}

export interface SearchIssuesResponse {
  results: SearchResultItem[];
}

export type IssueStatus = 'opened' | 'closed' | 'all';

export interface ApiKey {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
  key?: string;
}

export interface Project {
  id: string;
  name: string;
  key: string;
  description: string;
  url: string;
  organization_id: string;
  tracker_id: string;
}

export interface Organization {
  id: string;
  name: string;
  key: string;
  tracker_id: string;
}

export interface Issue {
  id: string;
  title: string;
  description: string;
  status: string;
  status_id: string;
  priority: string;
  priority_id: string;
  project_id: string;
  project_name: string;
  organization_id: string;
  organization_name: string;
  created_at: string;
  updated_at: string;
  key: string;
  source: string;
  url: string;
}

export interface DuplicatePair {
  issue1: Issue;
  issue2: Issue;
  similarity: number;
  verified_as_duplicate: boolean | null;
}

export interface DuplicatesResponse {
  duplicates: DuplicatePair[];
}

export interface IssueComplianceResult {
  id: string;
  prompt_id: string;
  name: string;
  short_name: string;
  compliance_factor: number;
  reason: string;
  suggestion: string;
  annotated_description?: string;
  issue_id: string;
  created_at: string;
  updated_at: string;
}

export interface CompliancePromptMetadata {
  id: string;
  name: string;
  short_name: string;
}

export interface IssueEmbedding {
  issue_id: string;
  project_id: string;
  issue_key: string;
  issue_title: string;
  issue_created_at: string;
  embedding: number[];
}

export interface ComplianceSuggestion {
  title: string;
  description: string;
  changes: string;
}

export interface DependencyPair {
  source_issue_id: string;
  dependent_issue_id: string;
  reason: string;
  confidence_score: number;
  issue_key?: string;
  dependency_key?: string;
  is_committed: boolean;
  comes_from_tracker: boolean;
}

export interface DependencyResponse {
  dependencies: DependencyPair[];
}

// User Management Types
export interface User {
  id: string;
  account_id: string;
  username: string;
  email: string;
  email_verified: boolean;
  full_name: string | null;
  is_active: boolean;
  user_source: string;
  oauth_provider: string | null;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  username: string;
  email: string;
  full_name?: string;
  password: string;
  user_source?: string;
  is_active?: boolean;
}

export interface UserUpdate {
  email?: string;
  full_name?: string;
  is_active?: boolean;
}

export interface UserListResponse {
  users: User[];
  total: number;
  skip: number;
  limit: number;
}

// Team Management Types
export interface Team {
  id: string;
  account_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeamMember {
  id: string;
  team_id: string;
  user_id: string;
  role_id: string | null;
  joined_at: string;
  user?: User;
}

export interface TeamCreate {
  name: string;
  description?: string;
}

export interface TeamUpdate {
  name?: string;
  description?: string;
}

export interface TeamListResponse {
  teams: Team[];
  total: number;
  skip: number;
  limit: number;
}

// Invitation Management Types
export interface UserInvitation {
  id: string;
  account_id: string;
  email: string;
  invited_by_user_id: string;
  token: string;
  status: 'pending' | 'accepted' | 'expired' | 'cancelled';
  expires_at: string;
  accepted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface InvitationCreate {
  email: string;
  role_ids?: string[];
}

export interface InvitationListResponse {
  invitations: UserInvitation[];
  total: number;
  skip: number;
  limit: number;
}

// Role Management Types
export interface Role {
  id: string;
  name: string;
  description: string | null;
  is_system_role: boolean;
  permissions: string[];
}

export interface RoleListResponse {
  roles: Role[];
  total: number;
}
