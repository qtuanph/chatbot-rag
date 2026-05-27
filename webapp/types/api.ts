// Backend API type definitions

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
  role: string;
  is_active: boolean;
}

export interface UserItem {
  id: string;
  username: string;
  role: string;
}

export interface UserUsageSummaryItem {
  user_id: string;
  username: string;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  cost_usd: number;
  call_count: number;
  window_days?: number;
}

export interface UserUsageWindow {
  days: number;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  estimated_cost_usd: number;
  daily: Array<{
    date: string;
    tokens_in: number;
    tokens_out: number;
  }>;
}

export interface UserUsageDetail {
  user_id: string;
  window_30d: UserUsageWindow & {
    by_model_type: {
      llm: ModelTypeStats;
      embedding: ModelTypeStats;
      reranker: ModelTypeStats;
    };
  };
  pricing: {
    input_per_1m: number;
    output_per_1m: number;
  };
}

export interface CreateUserRequest {
  username: string;
  password: string;
  role?: string;
}

export interface RoleItem {
  id: string;
  name: string;
  description: string | null;
}

// Chat
export interface ChatRequest {
  query: string;
  session_id?: string | null;
}

export interface Citation {
  document_id: string;
  node_id: string;
  title: string;
  heading: string;
  page_range: string | null;
  index: number;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  citations: Citation[];
}

export interface ChatSession {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  title: string;
}

// Chat message from DB (for session restore)
export interface ChatMessageItem {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  feedback: number; // 1 for like, -1 for dislike, 0 for none
  created_at: string;
}

// SSE streaming events
export interface ChatStreamChunk {
  chunk: string;
  done: false;
}

export interface ChatStreamDone {
  chunk: string;
  done: true;
  session_id: string;
  message_id: string;
  citations: Citation[];
  stats?: {
    total_ms: number;
    ttft_ms: number | null;
    chunks: number;
    chars: number;
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated_cost_usd: number;
  };
}

export interface ChatStreamError {
  chunk: string;
  done: true;
  error: string;
}

export type ChatStreamEvent = ChatStreamChunk | ChatStreamDone | ChatStreamError;

// Documents
export interface DocumentSummary {
  document_id: string;
  title: string;
  file_name: string;
  file_type: string;
  file_size: number;
  version: number;
  status: string;
  stage: string;
  progress_percent: number;
  status_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  items: DocumentSummary[];
  total: number;
}

export interface DocumentDetail {
  document_id: string;
  title: string;
  file_name: string;
  file_path: string;
  sha256: string;
  file_type: string;
  file_size: number;
  version: number;
  status: string;
  stage: string;
  progress_percent: number;
  status_message: string | null;
  parse_error: string | null;
  metadata: Record<string, unknown>;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  task_id: string;
  status: string;
  document_id: string;
}

export interface TaskStatus {
  task_id: string;
  status: string;
  stage: string | null;
  progress: { step: string; percent: number };
  document_id: string | null;
  status_message: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
}

// Tree
export interface TreeNode {
  node_id: string;
  title: string;
  level: number;
  breadcrumb: string;
  parent_id: string | null;
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

// Analytics
export interface AnalyticsDailyStat {
  date: string;
  messages: number;
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
  cost_usd: number;
}

export interface ModelTypeStats {
  tokens_in: number;
  tokens_out: number;
  avg_latency_ms: number;
  call_count: number;
  cost_usd: number;
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
  created_at: string;
}

export interface AnalyticsStats {
  total_messages: number;
  total_sessions: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_tokens: number;
  avg_latency_ms: number;
  estimated_cost_usd: number;
  model_used: string;
  daily: AnalyticsDailyStat[];
  by_model_type: {
    llm: ModelTypeStats;
    embedding: ModelTypeStats;
    reranker: ModelTypeStats;
  };
  daily_by_model_type: DailyByModelType[];
  recent_requests: RecentRequest[];
  pricing: {
    input_per_1m: number;
    output_per_1m: number;
    model: string;
    note: string;
  };
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
        estimated_cost_usd: number;
      };
      by_model_type: {
        llm: ModelTypeStats;
        embedding: ModelTypeStats;
        reranker: ModelTypeStats;
      };
    }
  >;
  pricing: {
    input_per_1m: number;
    output_per_1m: number;
  };
}

// Health
export interface HealthCheck {
  status: "up" | "down" | "degraded";
  latency_ms?: number;
  [key: string]: unknown;
}

// Settings (AI provider management via SQLite)
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
}

export interface AIProviderUpdate {
  display_name?: string;
  url?: string;
  model?: string;
  api_key?: string;
  priority?: number;
}

export interface ApiKeyItem {
  id: number;
  provider_id: number;
  key_value: string;
  is_active: boolean;
  failure_count: number;
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

export interface HealthData {
  status: string;
  timestamp: string;
  active_docs: number;
  total_docs: number;
  latest_document_id: string;
  target_document_id: string;
  checks: Record<string, HealthCheck>;
}
