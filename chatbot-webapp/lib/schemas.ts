import { z } from "zod/v4";

// ── Shared / Money ─────────────────────────────────────────────────────

export const MoneyPayloadSchema = z.object({
  currency_code: z.string(),
  cost_micros_vnd: z.number(),
  cost_vnd: z.string(),
  cost_vnd_rounded: z.number(),
});

// ── Auth ─────────────────────────────────────────────────────────────────

export const LoginRequestSchema = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
});

export const TokenResponseSchema = z.object({
  access_token: z.string(),
  token_type: z.string().default("bearer"),
  role: z.string(),
  tenant_id: z.string().nullable().optional(),
});

export const LogoutResponseSchema = z.object({
  status: z.string(),
});

export const CreateUserRequestSchema = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
  role: z.string().optional(),
  tenant_id: z.string().nullable().optional(),
});

export const UserItemSchema = z.object({
  id: z.string(),
  username: z.string(),
  role: z.string(),
  tenant_id: z.string().nullable().optional(),
});

export const UserInfoSchema = z.object({
  user_id: z.string(),
  username: z.string(),
  role: z.string(),
  tenant_id: z.string().nullable().optional(),
  is_active: z.boolean(),
});

export const RoleItemSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string().nullable(),
});

export const UpdateProfileRequestSchema = z.object({
  username: z.string().optional(),
  current_password: z.string().optional(),
  new_password: z.string().optional(),
});

// ── Tenant ───────────────────────────────────────────────────────────────

export const TenantItemSchema = z.object({
  id: z.string(),
  slug: z.string(),
  name: z.string(),
  status: z.string(),
  description: z.string().nullable().optional(),
  monthly_token_quota: z.number(),
  monthly_request_quota: z.number(),
  rate_limit_rpm: z.number(),
  allowed_origins: z.array(z.string()),
  created_at: z.string(),
  updated_at: z.string(),
});

export const TenantCreateRequestSchema = z.object({
  name: z.string().min(1),
  slug: z.string().min(1),
  description: z.string().nullable().optional(),
  monthly_token_quota: z.number().optional(),
  monthly_request_quota: z.number().optional(),
  rate_limit_rpm: z.number().optional(),
  allowed_origins: z.array(z.string()).optional(),
  admin_username: z.string().optional(),
  admin_password: z.string().optional(),
});

export const TenantUpdateRequestSchema = z.object({
  slug: z.string().optional(),
  name: z.string().optional(),
  description: z.string().nullable().optional(),
  status: z.string().optional(),
  monthly_token_quota: z.number().optional(),
  monthly_request_quota: z.number().optional(),
  rate_limit_rpm: z.number().optional(),
  allowed_origins: z.array(z.string()).optional(),
});

export const TenantSettingSchema = z.object({
  tenant_id: z.string(),
  system_instruction: z.string(),
  updated_at: z.string(),
});

export const TenantSettingUpdateRequestSchema = z.object({
  system_instruction: z.string().optional(),
});

export const TenantApiKeyItemSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  name: z.string(),
  key_prefix: z.string(),
  status: z.string(),
  expires_at: z.string().nullable().optional(),
  last_used_at: z.string().nullable().optional(),
  revoked_at: z.string().nullable().optional(),
  created_at: z.string(),
});

export const TenantApiKeyCreateRequestSchema = z.object({
  name: z.string().min(1),
  expires_at: z.string().nullable().optional(),
});

export const TenantApiKeyCreateResponseSchema = TenantApiKeyItemSchema.extend({
  raw_api_key: z.string(),
});

// ── Document ─────────────────────────────────────────────────────────────

export const UploadResponseSchema = z.object({
  task_id: z.string(),
  status: z.string(),
  document_id: z.string(),
});

export const TaskStatusSchema = z.object({
  task_id: z.string(),
  status: z.string(),
  stage: z.string().nullable().optional(),
  progress: z.object({
    step: z.string(),
    percent: z.number(),
  }),
  document_id: z.string().nullable().optional(),
  status_message: z.string().nullable().optional(),
  error: z.string().nullable().optional(),
  result: z.record(z.string(), z.unknown()).nullable().optional(),
});

export const DocumentSummarySchema = z.object({
  document_id: z.string(),
  tenant_id: z.string(),
  title: z.string(),
  file_name: z.string(),
  file_type: z.string(),
  file_size: z.number(),
  version: z.number(),
  status: z.string(),
  stage: z.string(),
  progress_percent: z.number(),
  status_message: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  node_count: z.number().optional(),
});

export const DocumentListResponseSchema = z.object({
  items: z.array(DocumentSummarySchema),
  total: z.number(),
  offset: z.number().optional(),
  limit: z.number().optional(),
});

export const DocumentDetailSchema = z.object({
  document_id: z.string(),
  tenant_id: z.string(),
  title: z.string(),
  file_name: z.string(),
  sha256: z.string(),
  file_type: z.string(),
  file_size: z.number(),
  version: z.number(),
  status: z.string(),
  stage: z.string(),
  progress_percent: z.number(),
  status_message: z.string().nullable().optional(),
  parse_error: z.string().nullable().optional(),
  artifact_metadata: z.record(z.string(), z.unknown()),
  deleted_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
  node_count: z.number().optional(),
});

export const DocumentDeleteResponseSchema = z.object({
  status: z.string(),
  document_id: z.string(),
});

export const DocumentRetryResponseSchema = z.object({
  task_id: z.string(),
  document_id: z.string(),
  status: z.string(),
});

export const DocumentRechunkResponseSchema = z.object({
  task_id: z.string(),
  document_id: z.string(),
  status: z.string(),
});

// ── Tree ─────────────────────────────────────────────────────────────────

export const TreeNodeSchema = z.object({
  node_id: z.string(),
  title: z.string(),
  level: z.number(),
  breadcrumb: z.string(),
  parent_id: z.string().nullable().optional(),
  child_count: z.number(),
  text_length: z.number(),
  page_number: z.union([z.number(), z.string()]),
  page_range: z.string().nullable().optional(),
});

export const TreeResponseSchema = z.object({
  document_id: z.string(),
  document_title: z.string(),
  total_nodes: z.number(),
  max_depth: z.number(),
  nodes: z.array(TreeNodeSchema),
});

export const NodeDetailSchema = z.object({
  node_id: z.string(),
  title: z.string(),
  level: z.number(),
  breadcrumb: z.string(),
  text: z.string(),
  metadata: z.object({
    page_number: z.union([z.number(), z.string()]),
    page_range: z.string().nullable().optional(),
    node_type: z.string(),
    order: z.number(),
    char_count: z.number(),
    token_count: z.number(),
  }),
});

export const TreeSearchResultSchema = z.object({
  node_id: z.string(),
  title: z.string(),
  preview: z.string(),
  highlight: z.string(),
});

// ── Chat ──────────────────────────────────────────────────────────────────

export const CitationSchema = z.object({
  document_id: z.string(),
  section_id: z.string().nullable().optional(),
  file_name: z.string().nullable().optional(),
  title: z.string().nullable().optional(),
  heading: z.string().nullable().optional(),
  page_range: z.string().nullable().optional(),
  score: z.number().nullable().optional(),
});

export const ChatMessageItemSchema = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
  citations: z.array(CitationSchema).optional(),
});

export const ChatFeedbackRequestSchema = z.object({
  tenant_id: z.string().nullable().optional(),
  feedback_type: z.enum(["like", "dislike"]),
  query_text: z.string().min(1),
  assistant_answer: z.string().min(1),
  citations: z.array(CitationSchema).default([]),
  metadata: z.record(z.string(), z.unknown()).default({}),
});

export const ChatFeedbackResponseSchema = z.object({
  id: z.string(),
  tenant_id: z.string(),
  user_id: z.string().nullable().optional(),
  feedback_type: z.enum(["like", "dislike"]),
  created_at: z.string(),
});

// ── Analytics ─────────────────────────────────────────────────────────────

export const ModelTypeStatsSchema = z.object({
  tokens_in: z.number(),
  tokens_out: z.number(),
  avg_latency_ms: z.number(),
  call_count: z.number(),
  cost_micros_vnd: z.number(),
});

export const AnalyticsDailyStatSchema = MoneyPayloadSchema.extend({
  date: z.string(),
  messages: z.number(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  avg_latency_ms: z.number(),
});

export const DailyByModelTypeSchema = z.object({
  date: z.string(),
  llm: ModelTypeStatsSchema,
  embedding: ModelTypeStatsSchema,
  reranker: ModelTypeStatsSchema,
});

export const RecentRequestSchema = z.object({
  model_name: z.string(),
  model_type: z.string(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  latency_ms: z.number(),
  cost_micros_vnd: z.number(),
  created_at: z.string(),
});

export const AnalyticsStatsSchema = MoneyPayloadSchema.extend({
  total_messages: z.number(),
  total_tokens_in: z.number(),
  total_tokens_out: z.number(),
  total_tokens: z.number(),
  avg_latency_ms: z.number(),
  model_used: z.string(),
  daily: z.array(AnalyticsDailyStatSchema),
  by_model_type: z.object({
    llm: ModelTypeStatsSchema,
    embedding: ModelTypeStatsSchema,
    reranker: ModelTypeStatsSchema,
  }),
  daily_by_model_type: z.array(DailyByModelTypeSchema),
  recent_requests: z.array(RecentRequestSchema),
  feedback_summary: z.object({
    total: z.number(),
    like_count: z.number(),
    dislike_count: z.number(),
    dislike_rate: z.number(),
    top_disliked_documents: z.array(
      z.object({
        document_id: z.string(),
        title: z.string(),
        count: z.number(),
      })
    ),
    top_disliked_sections: z.array(
      z.object({
        document_id: z.string(),
        section_id: z.string(),
        heading: z.string(),
        count: z.number(),
      })
    ),
  }),
  pricing: z.object({
    currency_code: z.string(),
    input_price_vnd_per_1m: z.number(),
    output_price_vnd_per_1m: z.number(),
    model: z.string().optional(),
    note: z.string().optional(),
  }),
});

export const UserUsageSummaryItemSchema = MoneyPayloadSchema.extend({
  user_id: z.string(),
  username: z.string(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  total_tokens: z.number(),
  call_count: z.number(),
  window_days: z.number().optional(),
});

export const UserUsageWindowsSchema = z.object({
  user_id: z.string(),
  windows: z.record(
    z.string(),
    z.object({
      days: z.number(),
      total: z.object({
        tokens_in: z.number(),
        tokens_out: z.number(),
        total_tokens: z.number(),
        currency_code: z.string(),
        cost_micros_vnd: z.number(),
        cost_vnd: z.string(),
        cost_vnd_rounded: z.number(),
      }),
      by_model_type: z.object({
        llm: ModelTypeStatsSchema,
        embedding: ModelTypeStatsSchema,
        reranker: ModelTypeStatsSchema,
      }),
    })
  ),
  pricing: z.object({
    currency_code: z.string(),
    input_price_vnd_per_1m: z.number(),
    output_price_vnd_per_1m: z.number(),
  }),
});

export const UserUsageDetailSchema = z.object({
  user_id: z.string(),
  window_30d: MoneyPayloadSchema.extend({
    days: z.number(),
    tokens_in: z.number(),
    tokens_out: z.number(),
    total_tokens: z.number(),
    daily: z.array(
      z.object({
        date: z.string(),
        tokens_in: z.number(),
        tokens_out: z.number(),
      })
    ),
    by_model_type: z.object({
      llm: ModelTypeStatsSchema,
      embedding: ModelTypeStatsSchema,
      reranker: ModelTypeStatsSchema,
    }),
  }),
  pricing: z.object({
    currency_code: z.string(),
    input_price_vnd_per_1m: z.number(),
    output_price_vnd_per_1m: z.number(),
  }),
});

export const TenantUsageSummaryItemSchema = MoneyPayloadSchema.extend({
  tenant_id: z.string(),
  tenant_slug: z.string(),
  tenant_name: z.string(),
  tokens_in: z.number(),
  tokens_out: z.number(),
  total_tokens: z.number(),
  call_count: z.number(),
  avg_latency_ms: z.number(),
  window_days: z.number(),
});

export const TenantUsageSummaryResponseSchema = z.object({
  items: z.array(TenantUsageSummaryItemSchema),
  window_days: z.number(),
  pricing: z.object({
    currency_code: z.string(),
    input_price_vnd_per_1m: z.number(),
    output_price_vnd_per_1m: z.number(),
  }),
});

// ── Settings / AI Providers ───────────────────────────────────────────────

export const AIProviderSchema = z.object({
  id: z.number(),
  service_type: z.enum(["embedding", "reranker", "llm", "parser"]),
  provider_name: z.string(),
  display_name: z.string(),
  url: z.string(),
  model: z.string(),
  api_key: z.string(),
  is_active: z.boolean(),
  is_builtin: z.boolean(),
  priority: z.number(),
  config: z.record(z.string(), z.unknown()).default({}),
  last_test_status: z.enum(["unknown", "success", "failed"]).default("unknown"),
  last_test_at: z.string().nullable().optional(),
  last_error: z.string().default(""),
  last_error_at: z.string().nullable().optional(),
  created_at: z.string(),
  updated_at: z.string(),
});

export const AIProviderCreateSchema = z.object({
  service_type: z.string(),
  provider_name: z.string(),
  display_name: z.string(),
  url: z.string(),
  model: z.string(),
  api_key: z.string(),
  priority: z.number().optional(),
  config: z.record(z.string(), z.unknown()).optional(),
});

export const AIProviderUpdateSchema = z.object({
  display_name: z.string().optional(),
  url: z.string().optional(),
  model: z.string().optional(),
  api_key: z.string().optional(),
  priority: z.number().optional(),
  config: z.record(z.string(), z.unknown()).optional(),
});

export const ApiKeyItemSchema = z.object({
  id: z.number(),
  provider_id: z.number(),
  key_value: z.string(),
  is_active: z.boolean(),
  failure_count: z.number(),
  rate_limited_until: z.string().nullable().optional(),
  backoff_level: z.number().default(0),
  last_error: z.string().default(""),
  last_error_at: z.string().nullable().optional(),
  last_used_at: z.string().nullable().optional(),
  created_at: z.string(),
});

export const ProviderTemplateSchema = z.object({
  service_type: z.string(),
  provider_name: z.string(),
  display_name: z.string(),
  url: z.string(),
  model: z.string(),
});

export const TestResultSchema = z.object({
  success: z.boolean(),
  message: z.string(),
});

// ── Health ────────────────────────────────────────────────────────────────

export const HealthCheckSchema = z.object({
  configured: z.boolean().optional(),
  status: z.enum(["up", "down", "degraded"]).optional(),
  latency_ms: z.number().optional(),
  provider: z.string().optional(),
  model: z.string().optional(),
  broker: z.string().optional(),
}).catchall(z.unknown());

export const HealthDataSchema = z.object({
  status: z.string(),
  timestamp: z.string(),
  active_docs: z.number().optional(),
  total_docs: z.number().optional(),
  latest_document_id: z.string().optional(),
  target_document_id: z.string().optional(),
  checks: z.record(z.string(), HealthCheckSchema).optional(),
  services: z.record(z.string(), HealthCheckSchema).optional(),
});
