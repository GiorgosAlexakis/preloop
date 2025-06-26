export interface LlmModel {
  id: string;
  name: string;
  provider_name: string;
  api_key: string;
  api_url: string;
  model_name: string;
  model_version?: string;
  is_default?: boolean;
  created_at: string;
  updated_at: string;
  account_id: string;
}
