export interface AIModel {
  id: string;
  name: string;
  description?: string | null;
  provider_name: string;
  api_key?: string;
  has_api_key?: boolean;
  credentials_secret_id?: string | null;
  credentials_backend_type?: string | null;
  api_endpoint?: string;
  model_identifier: string;
  meta_data?: Record<string, unknown> | null;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
  account_id?: string;
}

export interface FlowGatewayConversationPreviewMessage {
  source?: string | null;
  role?: string | null;
  text?: string | null;
  redacted?: boolean;
  truncated?: boolean;
  original_length?: number | null;
}

export interface FlowGatewayConversationPreview {
  messages?: FlowGatewayConversationPreviewMessage[];
  metadata?: {
    message_count?: number | null;
    request_message_count?: number | null;
    response_message_count?: number | null;
    has_redacted_content?: boolean;
    has_truncated_content?: boolean;
  } | null;
}

export interface FlowGatewayCapturePolicy {
  content_capture_enabled?: boolean;
  max_preview_chars?: number | null;
  sensitive_fields_redacted?: boolean;
  content_redacted?: boolean;
  content_truncated?: boolean;
  conversation_preview_available?: boolean;
}

export interface FlowGatewayEventPayload {
  api_usage_id?: string | null;
  endpoint?: string | null;
  endpoint_kind?: string | null;
  method?: string | null;
  status_code?: number | null;
  outcome?: string | null;
  duration_ms?: number | null;
  user_id?: string | null;
  auth_subject_type?: string | null;
  api_key_id?: string | null;
  ai_model_id?: string | null;
  model_alias?: string | null;
  provider_name?: string | null;
  gateway_provider?: string | null;
  requested_model?: string | null;
  upstream_request_id?: string | null;
  finish_reason?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
  estimated_cost?: number | null;
  runtime_principal?: {
    type?: string | null;
    id?: string | null;
    name?: string | null;
  } | null;
  budget?: Record<string, unknown> | null;
  error_detail?: string | null;
  capture_policy?: FlowGatewayCapturePolicy | null;
  conversation_preview?: FlowGatewayConversationPreview | null;
  request?: unknown;
  response?: unknown;
  message?: string | null;
  [key: string]: unknown;
}

export interface FlowGatewayEvent {
  id: string;
  execution_id: string;
  timestamp: string | null;
  type: string;
  payload: FlowGatewayEventPayload;
}

export interface FlowGatewayEventsResponse {
  logs: FlowGatewayEvent[];
  source: 'container' | 'database';
}

export interface GatewayTokenUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface GatewayBudgetSummary {
  monthly_limit_usd: number | null;
  soft_limit_usd: number | null;
  current_spend_usd: number;
  soft_limit_exceeded: boolean;
  hard_limit_exceeded: boolean;
}

export interface GatewayUsageByDay {
  date: string;
  request_count: number;
  estimated_cost: number;
  total_tokens: number;
}

export interface GatewayUsageByModel {
  ai_model_id: string | null;
  model_alias: string | null;
  provider_name: string | null;
  request_count: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  last_request_at?: string | null;
}

export interface GatewayUsageByFlow {
  flow_id: string | null;
  flow_name: string | null;
  request_count: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
}

export interface GatewayUsageByExecution {
  flow_execution_id: string | null;
  request_count: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  last_request_at: string | null;
}

export interface GatewayUsageBySession {
  ai_model_id?: string | null;
  runtime_session_id?: string | null;
  runtime_session_name?: string | null;
  session_source_type?: string | null;
  session_source_id?: string | null;
  runtime_principal_type?: string | null;
  runtime_principal_id?: string | null;
  runtime_principal_name?: string | null;
  flow_execution_id: string | null;
  flow_id: string | null;
  flow_name: string | null;
  session_reference: string | null;
  model_alias: string | null;
  provider_name: string | null;
  request_count: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  started_at?: string | null;
  last_activity_at?: string | null;
  last_request_at: string | null;
  ended_at?: string | null;
}

export interface GatewayUsageSearchResultItem {
  api_usage_id: string;
  timestamp: string;
  status_code: number;
  outcome: 'success' | 'error';
  endpoint: string;
  method: string;
  provider_name: string | null;
  model_alias: string | null;
  flow_id: string | null;
  flow_name: string | null;
  flow_execution_id: string | null;
  runtime_session_id: string | null;
  session_source_type: string | null;
  session_source_id: string | null;
  session_reference: string | null;
  runtime_principal_type: string | null;
  runtime_principal_id: string | null;
  runtime_principal_name: string | null;
  auth_subject_type: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  estimated_cost: number;
  token_usage: GatewayTokenUsage;
  excerpt: string;
  meta_data: Record<string, unknown>;
}

export interface AccountGatewayUsageSearchResponse {
  period_start: string;
  period_end: string;
  query: string | null;
  total: number;
  limit: number;
  offset: number;
  items: GatewayUsageSearchResultItem[];
}

export interface RuntimeSessionSummary {
  id: string;
  session_source_type: string;
  session_source_id: string;
  session_reference: string | null;
  runtime_principal_type: string | null;
  runtime_principal_id: string | null;
  runtime_principal_name: string | null;
  started_at: string;
  last_activity_at: string | null;
  ended_at: string | null;
  flow_id: string | null;
  flow_name: string | null;
  flow_execution_id: string | null;
  latest_model_alias: string | null;
  latest_provider_name: string | null;
  is_active_now: boolean;
  activity_status: 'active_now' | 'idle' | 'ended' | string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  last_request_at: string | null;
}

export interface AccountRuntimeSessionListResponse {
  period_start: string;
  period_end: string;
  query: string | null;
  session_source_type: string | null;
  status: 'all' | 'active' | 'ended';
  total: number;
  limit: number;
  offset: number;
  items: RuntimeSessionSummary[];
}

export interface AccountRuntimeSessionDetailResponse {
  period_start: string;
  period_end: string;
  session: RuntimeSessionSummary;
  usage_by_model: GatewayUsageByModel[];
  interactions: AccountGatewayUsageSearchResponse;
  activity_timeline: RuntimeSessionActivityItem[];
}

export interface ManagedAgentSummary {
  id: string;
  runtime_session_id: string | null;
  owner_user_id: string | null;
  owner_username: string | null;
  owner_email: string | null;
  agent_kind?: string | null;
  display_name: string;
  session_source_type: string;
  session_source_id: string;
  session_reference: string | null;
  enrolled_via: string;
  tags?: Record<string, string>;
  managed_mcp_servers: string[];
  lifecycle_state: 'active' | 'suspended' | 'decommissioned' | string;
  lifecycle_reason: string | null;
  lifecycle_updated_at: string | null;
  is_active_now: boolean;
  activity_status:
    | 'active_now'
    | 'recently_active'
    | 'idle'
    | 'ended'
    | 'suspended'
    | 'decommissioned'
    | string;
  last_seen_at: string;
  started_at: string | null;
  last_activity_at: string | null;
  ended_at: string | null;
  total_requests: number;
  estimated_cost: number;
  configured_model_alias: string | null;
  configured_model_id?: string | null;
  configured_models?: ManagedAgentModelBindingSummary[];
  latest_model_alias: string | null;
  latest_provider_name: string | null;
  last_request_at: string | null;
  mcp_proxy_configured: boolean;
  model_gateway_configured: boolean;
  onboarding_state:
    | 'fully_onboarded'
    | 'mcp_proxy_only'
    | 'gateway_only'
    | 'incomplete'
    | string;
  live_validation_supported: boolean;
  live_validation_passed: boolean | null;
  live_validation_status:
    | 'unsupported'
    | 'not_run'
    | 'passed'
    | 'failed'
    | string;
  last_validated_at: string | null;
}

export interface ManagedAgentModelBindingSummary {
  id: string;
  ai_model_id: string | null;
  binding_type: string;
  config_key: string;
  gateway_alias: string;
  is_primary: boolean;
  status: string;
  provider_name?: string | null;
  model_identifier?: string | null;
  ai_model_name?: string | null;
  first_seen_at?: string | null;
  last_seen_at?: string | null;
}

export interface ManagedAgentUsageAggregate {
  session_count: number;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  latest_model_alias: string | null;
  latest_provider_name: string | null;
  last_request_at: string | null;
}

export interface ManagedAgentServerActivitySummary {
  server_name: string | null;
  call_count: number;
  successful_calls: number;
  failed_calls: number;
  last_activity_at: string | null;
}

export interface ManagedAgentToolActivitySummary {
  server_name: string | null;
  tool_name: string | null;
  call_count: number;
  successful_calls: number;
  failed_calls: number;
  last_activity_at: string | null;
}

export interface AccountManagedAgentListResponse {
  query: string | null;
  agent_kind: string | null;
  last_seen_after: string | null;
  status: 'all' | 'active' | 'ended';
  total: number;
  limit: number;
  offset: number;
  items: ManagedAgentSummary[];
}

export interface ManagedAgentDetailResponse {
  agent: ManagedAgentSummary;
  aggregate: ManagedAgentUsageAggregate;
  usage_by_model: GatewayUsageByModel[];
  activity_by_server: ManagedAgentServerActivitySummary[];
  activity_by_tool: ManagedAgentToolActivitySummary[];
  sessions: RuntimeSessionSummary[];
}

export interface ManagedAgentUpdateRequest {
  owner_user_id?: string | null;
  display_name?: string | null;
  tags?: Record<string, string> | null;
  lifecycle_action?: 'suspend' | 'resume' | 'decommission' | 'reenroll';
  reason?: string | null;
}

export interface SubjectGovernanceConfig {
  allowed_models: string[];
  model_budgets: Record<
    string,
    {
      monthly_usd_limit?: number | null;
      soft_limit_usd?: number | null;
    }
  >;
  tool_rules: Record<string, Array<Record<string, unknown>>>;
  tool_enabled_overrides?: Record<string, boolean>;
}

export interface SubjectGovernanceResponse {
  subject_type: string;
  subject_id: string;
  config: SubjectGovernanceConfig;
}

export interface RuntimeSessionUpdateRequest {
  action: 'end';
  reason?: string | null;
}

export interface RuntimeSessionActivityItem {
  activity_type: 'model_interaction' | 'tool_call' | string;
  timestamp: string;
  title: string;
  summary: string | null;
  status: string | null;
  api_usage_id: string | null;
  tool_name: string | null;
  server_name: string | null;
  auth_subject_type: string | null;
  api_key_id: string | null;
  api_key_name: string | null;
  estimated_cost: number | null;
  total_tokens: number | null;
}

export interface RuntimeSessionActivityListResponse {
  items: RuntimeSessionActivityItem[];
}

export interface AccountGatewayUsageSummaryResponse {
  period_start: string;
  period_end: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  budget: GatewayBudgetSummary;
  requests_by_day: GatewayUsageByDay[];
  usage_by_model: GatewayUsageByModel[];
  usage_by_flow: GatewayUsageByFlow[];
  usage_by_session: GatewayUsageBySession[];
}

export interface FlowGatewayUsageSummaryResponse {
  flow_id: string;
  flow_name: string | null;
  period_start: string;
  period_end: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  budget: GatewayBudgetSummary;
  usage_by_model: GatewayUsageByModel[];
  usage_by_execution: GatewayUsageByExecution[];
}

export interface AIModelGatewayUsageSummaryResponse {
  ai_model_id: string;
  model_name: string;
  provider_name: string;
  model_identifier: string;
  period_start: string;
  period_end: string;
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  token_usage: GatewayTokenUsage;
  estimated_cost: number;
  requests_by_day: GatewayUsageByDay[];
  usage_by_session: GatewayUsageBySession[];
}

export type AIModelRuntimeSessionListResponse =
  AccountRuntimeSessionListResponse;

export type AIModelGatewayUsageSearchResponse =
  AccountGatewayUsageSearchResponse;

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
  managed_agent_id?: string | null;
  runtime_principal_type?: string | null;
  runtime_principal_id?: string | null;
  runtime_principal_name?: string | null;
  last_activity_at?: string | null;
  activity_status?:
    | 'active_now'
    | 'recently_active'
    | 'idle'
    | 'revoked'
    | string;
  recent_model_calls?: number;
  recent_tool_calls?: number;
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
  team_ids?: string[];
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

export interface DashboardTelemetryResponse {
  active_agents: number;
  total_tool_calls: number;
  daily_cost: number;
  success_rate: number;
}
