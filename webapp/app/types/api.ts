/**
 * Backend API Response Types
 *
 * This file contains ALL TypeScript interfaces that match the backend Python schemas exactly.
 * NO any types allowed - 100% type safety for production use.
 *
 * Backend Schema Reference:
 * - app/schemas/documents.py
 * - app/schemas/auth.py
 * - app/schemas/chat.py
 * - app/api/routes/health.py
 */

// ============================================================================
// DOCUMENT API TYPES
// ============================================================================

/**
 * Upload accepted response - matches UploadAcceptedResponse
 * POST /upload returns 202 Accepted
 */
export interface UploadAcceptedResponse {
  task_id: string
  status: string
  document_id: string
}

/**
 * Task progress info - matches TaskProgressInfo
 */
export interface TaskProgressInfo {
  step: string
  percent: number
}

/**
 * Task status response - matches TaskStatusResponse
 * GET /status/{task_id}
 */
export interface TaskStatusResponse {
  task_id: string
  status: string
  stage: string | null
  progress: TaskProgressInfo
  document_id: string | null
  status_message: string | null
  error: string | null
  result: Record<string, unknown> | null
}

/**
 * Document delete response - matches DocumentDeleteResponse
 * DELETE /documents/{id}
 */
export interface DocumentDeleteResponse {
  status: string
  document_id: string
}

/**
 * Document summary response - matches DocumentSummaryResponse
 * Used in document list items
 */
export interface DocumentSummaryResponse {
  document_id: string
  title: string
  file_name: string
  file_type: string
  file_size: number
  version: number
  status: string
  stage: string
  progress_percent: number
  status_message: string | null
  created_at: string
  updated_at: string
}

/**
 * Document list response - matches DocumentListResponse
 * GET /documents returns {items: [...], total: number}
 */
export interface DocumentListResponse {
  items: DocumentSummaryResponse[]
  total: number
}

/**
 * Document detail response - matches DocumentDetailResponse
 * GET /documents/{id}
 */
export interface DocumentDetailResponse {
  document_id: string
  title: string
  file_name: string
  file_path: string
  sha256: string
  file_type: string
  file_size: number
  version: number
  status: string
  stage: string
  progress_percent: number
  status_message: string | null
  parse_error: string | null
  metadata: Record<string, unknown>
  deleted_at: string | null
  created_at: string
  updated_at: string
}

// ============================================================================
// TREE API TYPES
// ============================================================================

/**
 * Tree node - hierarchical document structure
 * Used in tree viewer endpoints
 */
export interface TreeNode {
  id: string
  header: string
  content: string
  parent_id: string | null
  children: TreeNode[] | null
  level: number
  page_number: number
  metadata: {
    document_id: string
    file_name: string
    node_type: string
    [key: string]: unknown
  }
}

/**
 * Tree data response
 * GET /documents/{id}/tree
 */
export interface TreeDataResponse {
  nodes: TreeNode[]
  root_id: string
  document_id: string
  file_name: string
  total_nodes: number
}

// ============================================================================
// CHAT API TYPES
// ============================================================================

/**
 * Chat request - matches ChatRequest
 * POST /chat
 */
export interface ChatRequest {
  query: string
  session_id: string | null
}

/**
 * Citation reference
 */
export interface Citation {
  file_name: string
  node_header: string
  content: string
  page_number: number | null
}

/**
 * Chat response
 * POST /chat returns {session_id, answer, citations}
 */
export interface ChatResponse {
  session_id: string
  answer: string
  citations: Citation[]
}

/**
 * Chat session
 */
export interface ChatSession {
  session_id: string
  created_at: string
  message_count: number
  title: string
}

// ============================================================================
// AUTH API TYPES
// ============================================================================

/**
 * Login request - matches LoginRequest
 * POST /auth/login
 */
export interface LoginRequest {
  username: string
  password: string
}

/**
 * Token response - matches TokenResponse
 * POST /auth/login returns this
 */
export interface TokenResponse {
  access_token: string
  token_type: string
  role: string
}

/**
 * Logout response - matches LogoutResponse
 * POST /auth/logout
 */
export interface LogoutResponse {
  status: string
}

/**
 * Create user request - matches CreateUserRequest
 * POST /auth/users
 */
export interface CreateUserRequest {
  username: string
  password: string
  role: string
}

/**
 * Create user response - matches CreateUserResponse
 */
export interface CreateUserResponse {
  id: string
  username: string
  role: string
}

/**
 * User list item
 */
export interface UserResponse {
  id: string
  username: string
  role: string
  created_at: string
}

// ============================================================================
// HEALTH API TYPES
// ============================================================================

/**
 * Service health check
 */
export interface ServiceHealth {
  status: string
  message: string | null
  response_time_ms: number | null
}

/**
 * Health check response
 * GET /health or /health/data
 */
export interface HealthResponse {
  status: string
  timestamp: string
  active_docs: number
  total_docs: number
  latest_document_id: string
  target_document_id: string
  checks: Record<string, ServiceHealth>
  services_html: string
}

/**
 * Database statistics
 */
export interface DatabaseStats {
  total_documents: number
  processing: number
  failed: number
  completed: number
}

/**
 * Vector store statistics
 */
export interface VectorStoreStats {
  total_vectors: number
  collections: number
}

/**
 * Service health check
 */
export interface ServiceHealth {
  status: 'up' | 'down' | 'degraded'
  message?: string
  latency_ms?: number
  [key: string]: unknown
}

/**
 * Health check response
 * GET /health or /health/data
 */
export interface HealthResponse {
  status: 'healthy' | 'unhealthy' | 'degraded'
  timestamp: string
  active_docs: number
  total_docs: number
  latest_document_id: string
  target_document_id: string
  checks: Record<string, { status: string }>
  services_html: string
}

/**
 * Database statistics
 */
export interface DatabaseStats {
  total_documents: number
  processing: number
  failed: number
  completed: number
}

/**
 * Vector store statistics
 */
export interface VectorStoreStats {
  total_vectors: number
  collections: number
}

/**
 * Detailed health data response (custom format for frontend)
 */
export interface DetailedHealthResponse {
  checks: Record<string, { status: string }>
  database: DatabaseStats
  vector_store: VectorStoreStats
  timestamp: string
}

// ============================================================================
// ERROR TYPES
// ============================================================================

/**
 * API error response format
 */
export interface ApiErrorResponse {
  detail: string
  status_code?: number
  error_code?: string
}

/**
 * Axios error wrapper
 */
export interface ApiError {
  response?: {
    data?: ApiErrorResponse
    status?: number
    statusText?: string
  }
  code?: string
  message?: string
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

/**
 * Paginated response wrapper
 */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page?: number
  page_size?: number
  has_next?: boolean
  has_prev?: boolean
}

/**
 * Standard API response wrapper
 */
export interface ApiResponse<T> {
  data: T
  status: string
  message?: string
  timestamp?: string
}
