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
  message_count: number;
  title: string;
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
  citations: Citation[];
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

// Health
export interface HealthCheck {
  status: "up" | "down" | "degraded";
  latency_ms?: number;
  [key: string]: unknown;
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
