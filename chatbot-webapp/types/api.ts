export interface MoneyPayload {
  currency_code: string;
  cost_micros_vnd: number;
  cost_vnd: string;
  cost_vnd_rounded: number;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  tenant_id?: string | null;
}

export interface UserInfo {
  user_id: string;
  username: string;
  role: string;
  tenant_id?: string | null;
  is_active: boolean;
}

export interface UserItem {
  id: string;
  username: string;
  role: string;
  tenant_id?: string | null;
}

export interface CreateUserRequest {
  username: string;
  password: string;
  role?: string;
  tenant_id?: string | null;
}

export interface RoleItem {
  id: string;
  name: string;
  description: string | null;
}

export interface TenantItem {
  id: string;
  slug: string;
  name: string;
  status: string;
  description?: string | null;
  monthly_token_quota: number;
  monthly_request_quota: number;
  rate_limit_rpm: number;
  allowed_origins: string[];
  created_at: string;
  updated_at: string;
}

export interface TenantCreateRequest {
  name: string;
  slug: string;
  description?: string | null;
  monthly_token_quota?: number;
  monthly_request_quota?: number;
  rate_limit_rpm?: number;
  allowed_origins?: string[];
  admin_username?: string;
  admin_password?: string;
}

export interface TenantUpdateRequest {
  slug?: string;
  name?: string;
  description?: string | null;
  status?: string;
  monthly_token_quota?: number;
  monthly_request_quota?: number;
  rate_limit_rpm?: number;
  allowed_origins?: string[];
}

export interface TenantSetting {
  tenant_id: string;
  chatbot_display_name: string;
  welcome_message: string;
  system_instruction: string;
  updated_at: string;
}

export interface TenantSettingUpdateRequest {
  chatbot_display_name?: string;
  welcome_message?: string;
  system_instruction?: string;
}

export interface TenantApiKeyItem {
  id: string;
  tenant_id: string;
  name: string;
  key_prefix: string;
  status: string;
  expires_at?: string | null;
  last_used_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
}

export interface TenantApiKeyCreateRequest {
  name: string;
  expires_at?: string | null;
}

export interface TenantApiKeyCreateResponse extends TenantApiKeyItem {
  raw_api_key: string;
}

export interface TenantUsageSummaryItem extends MoneyPayload {
  tenant_id: string;
  tenant_slug: string;
  tenant_name: string;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  call_count: number;
  avg_latency_ms: number;
  window_days: number;
}

export interface TenantUsageSummaryResponse {
  items: TenantUsageSummaryItem[];
  window_days: number;
  pricing: {
    currency_code: string;
    input_price_vnd_per_1m: number;
    output_price_vnd_per_1m: number;
  };
}

export interface Citation {
  document_id: string;
  section_id: string;
  file_name: string;
  title: string;
  heading: string;
  page_range?: string | null;
  score?: number | null;
}

export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  citations?: Citation[];
}

export interface ChatUsage extends MoneyPayload {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model?: string;
}

export interface ChatFeedbackRequest {
  tenant_id?: string | null;
  feedback_type: "like" | "dislike";
  query_text: string;
  assistant_answer: string;
  citations: Citation[];
  metadata?: Record<string, unknown>;
}

export interface ChatFeedbackResponse {
  id: string;
  tenant_id: string;
  user_id?: string | null;
  feedback_type: "like" | "dislike";
  created_at: string;
}

export interface ChatStreamChunk {
  chunk: string;
  done: false;
  thinking?: boolean;
}

export interface ChatStreamDone {
  chunk: string;
  done: true;
  citations: Citation[];
  stats?: ChatUsage | null;
  error?: string;
}

export type ChatStreamEvent = ChatStreamChunk | ChatStreamDone;

export interface DocumentSummary {
  document_id: string;
  tenant_id: string;
  title: string;
  file_name: string;
  file_type: string;
  file_size: number;
  version: number;
  status: string;
  stage: string;
  progress_percent: number;
  status_message?: string | null;
  created_at: string;
  updated_at: string;
  node_count?: number;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
  offset?: number;
  limit?: number;
}

export interface DocumentDetail {
  document_id: string;
  tenant_id: string;
  title: string;
  file_name: string;
  sha256: string;
  file_type: string;
  file_size: number;
  version: number;
  status: string;
  stage: string;
  progress_percent: number;
  status_message?: string | null;
  parse_error?: string | null;
  artifact_metadata: Record<string, unknown>;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
  node_count?: number;
}

export interface UploadResponse {
  task_id: string;
  status: string;
  document_id: string;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  stage?: string | null;
  progress: { step: string; percent: number };
  document_id?: string | null;
  status_message?: string | null;
  error?: string | null;
  result?: Record<string, unknown> | null;
}

export interface TreeNode {
  node_id: string;
  title: string;
  level: number;
  breadcrumb: string;
  parent_id?: string | null;
  child_count: number;
  text_length: number;
  page_number: number | string;
  page_range?: string | null;
}

export interface TreeResponse {
  document_id: string;
  document_title: string;
  total_nodes: number;
  max_depth: number;
  nodes: TreeNode[];
}

export interface NodeDetail {
  node_id: string;
  title: string;
  level: number;
  breadcrumb: string;
  text: string;
  metadata: {
    page_number: number | string;
    page_range?: string | null;
    node_type: string;
    order: number;
    char_count: number;
    token_count: number;
  };
}

export interface TreeSearchResult {
  node_id: string;
  title: string;
  preview: string;
  highlight: string;
}

export interface ModelTypeStats {
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
  call_count: number;
  cost_micros_vnd: number;
}

export interface AnalyticsDailyStat extends MoneyPayload {
  date: string;
  messages: number;
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
}

export interface DailyByModelType {
  date: string;
  llm: ModelTypeStats;
  embedding: ModelTypeStats;
  reranker: ModelTypeStats;
}

export interface RecentRequest {
  model_name: string;
  model_type: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_micros_vnd: number;
  created_at: string;
}

export interface AnalyticsStats extends MoneyPayload {
  total_messages: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_tokens: number;
  avg_latency_ms: number;
  model_used: string;
  daily: AnalyticsDailyStat[];
  by_model_type: {
    llm: ModelTypeStats;
    embedding: ModelTypeStats;
    reranker: ModelTypeStats;
  };
  daily_by_model_type: DailyByModelType[];
  recent_requests: RecentRequest[];
  feedback_summary: {
    total: number;
    like_count: number;
    dislike_count: number;
    dislike_rate: number;
    top_disliked_documents: Array<{
      document_id: string;
      title: string;
      count: number;
    }>;
    top_disliked_sections: Array<{
      document_id: string;
      section_id: string;
      heading: string;
      count: number;
    }>;
  };
  pricing: {
    currency_code: string;
    input_price_vnd_per_1m: number;
    output_price_vnd_per_1m: number;
    model?: string;
    note?: string;
  };
}

export interface UserUsageSummaryItem extends MoneyPayload {
  user_id: string;
  username: string;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  call_count: number;
  window_days?: number;
}

export interface UserUsageWindows {
  user_id: string;
  windows: Record<
    string,
    {
      days: number;
      total: {
        tokens_in: number;
        tokens_out: number;
        total_tokens: number;
        currency_code: string;
        cost_micros_vnd: number;
        cost_vnd: string;
        cost_vnd_rounded: number;
      };
      by_model_type: {
        llm: ModelTypeStats;
        embedding: ModelTypeStats;
        reranker: ModelTypeStats;
      };
    }
  >;
  pricing: {
    currency_code: string;
    input_price_vnd_per_1m: number;
    output_price_vnd_per_1m: number;
  };
}

export interface UserUsageDetail {
  user_id: string;
  window_30d: {
    days: number;
    tokens_in: number;
    tokens_out: number;
    total_tokens: number;
    daily: Array<{
      date: string;
      tokens_in: number;
      tokens_out: number;
    }>;
    by_model_type: {
      llm: ModelTypeStats;
      embedding: ModelTypeStats;
      reranker: ModelTypeStats;
    };
  } & MoneyPayload;
  pricing: {
    currency_code: string;
    input_price_vnd_per_1m: number;
    output_price_vnd_per_1m: number;
  };
}

export interface HealthCheck {
  status: "up" | "down" | "degraded";
  latency_ms?: number;
  configured?: boolean;
  provider?: string;
  model?: string;
  broker?: string;
  [key: string]: unknown;
}

export interface HealthData {
  status: string;
  timestamp: string;
  active_docs?: number;
  total_docs?: number;
  latest_document_id?: string;
  target_document_id?: string;
  checks?: Record<string, HealthCheck>;
  services?: Record<string, HealthCheck>;
}

export interface AIProvider {
  id: number;
  service_type: "embedding" | "reranker" | "llm";
  provider_name: string;
  display_name: string;
  url: string;
  model: string;
  api_key: string;
  is_active: boolean;
  is_builtin: boolean;
  priority: number;
  config: Record<string, unknown>;
  last_test_status: "unknown" | "success" | "failed";
  last_test_at: string | null;
  last_error: string;
  last_error_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIProviderCreate {
  service_type: string;
  provider_name: string;
  display_name: string;
  url: string;
  model: string;
  api_key: string;
  priority?: number;
  config?: Record<string, unknown>;
}

export interface AIProviderUpdate {
  display_name?: string;
  url?: string;
  model?: string;
  api_key?: string;
  priority?: number;
  config?: Record<string, unknown>;
}

export interface ApiKeyItem {
  id: number;
  provider_id: number;
  key_value: string;
  is_active: boolean;
  failure_count: number;
  rate_limited_until: string | null;
  backoff_level: number;
  last_error: string;
  last_error_at: string | null;
  last_used_at: string | null;
  created_at: string;
}

export interface ProviderTemplate {
  service_type: string;
  provider_name: string;
  display_name: string;
  url: string;
  model: string;
}
