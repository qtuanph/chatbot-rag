// Types inferred from Zod schemas in lib/schemas.ts
// Do NOT edit types here — edit schemas in lib/schemas.ts

import { z } from "zod/v4";
import * as s from "@/lib/schemas";

// ── Shared ──
export type MoneyPayload = z.infer<typeof s.MoneyPayloadSchema>;

// ── Auth ──
export type LoginRequest = z.infer<typeof s.LoginRequestSchema>;
export type TokenResponse = z.infer<typeof s.TokenResponseSchema>;
export type LogoutResponse = z.infer<typeof s.LogoutResponseSchema>;
export type CreateUserRequest = z.infer<typeof s.CreateUserRequestSchema>;
export type UserItem = z.infer<typeof s.UserItemSchema>;
export type UserInfo = z.infer<typeof s.UserInfoSchema>;
export type RoleItem = z.infer<typeof s.RoleItemSchema>;
export type UpdateProfileRequest = z.infer<typeof s.UpdateProfileRequestSchema>;

// ── Tenant ──
export type TenantItem = z.infer<typeof s.TenantItemSchema>;
export type TenantCreateRequest = z.infer<typeof s.TenantCreateRequestSchema>;
export type TenantUpdateRequest = z.infer<typeof s.TenantUpdateRequestSchema>;
export type TenantSetting = z.infer<typeof s.TenantSettingSchema>;
export type TenantSettingUpdateRequest = z.infer<typeof s.TenantSettingUpdateRequestSchema>;
export type TenantApiKeyItem = z.infer<typeof s.TenantApiKeyItemSchema>;
export type TenantApiKeyCreateRequest = z.infer<typeof s.TenantApiKeyCreateRequestSchema>;
export type TenantApiKeyCreateResponse = z.infer<typeof s.TenantApiKeyCreateResponseSchema>;
export type TenantUsageSummaryItem = z.infer<typeof s.TenantUsageSummaryItemSchema>;
export type TenantUsageSummaryResponse = z.infer<typeof s.TenantUsageSummaryResponseSchema>;

// ── Document ──
export type UploadResponse = z.infer<typeof s.UploadResponseSchema>;
export type TaskStatus = z.infer<typeof s.TaskStatusSchema>;
export type DocumentSummary = z.infer<typeof s.DocumentSummarySchema>;
export type DocumentListResponse = z.infer<typeof s.DocumentListResponseSchema>;
export type DocumentDetail = z.infer<typeof s.DocumentDetailSchema>;
export type DocumentDeleteResponse = z.infer<typeof s.DocumentDeleteResponseSchema>;
export type DocumentRetryResponse = z.infer<typeof s.DocumentRetryResponseSchema>;
export type DocumentRechunkResponse = z.infer<typeof s.DocumentRechunkResponseSchema>;

// ── Tree ──
export type TreeNode = z.infer<typeof s.TreeNodeSchema>;
export type TreeResponse = z.infer<typeof s.TreeResponseSchema>;
export type NodeDetail = z.infer<typeof s.NodeDetailSchema>;
export type TreeSearchResult = z.infer<typeof s.TreeSearchResultSchema>;

// ── Chat ──
export type Citation = z.infer<typeof s.CitationSchema>;
export type ChatMessageItem = z.infer<typeof s.ChatMessageItemSchema>;
export type ChatFeedbackRequest = z.infer<typeof s.ChatFeedbackRequestSchema>;
export type ChatFeedbackResponse = z.infer<typeof s.ChatFeedbackResponseSchema>;

// ── Analytics ──
export type ModelTypeStats = z.infer<typeof s.ModelTypeStatsSchema>;
export type AnalyticsDailyStat = z.infer<typeof s.AnalyticsDailyStatSchema>;
export type DailyByModelType = z.infer<typeof s.DailyByModelTypeSchema>;
export type RecentRequest = z.infer<typeof s.RecentRequestSchema>;
export type AnalyticsStats = z.infer<typeof s.AnalyticsStatsSchema>;
export type UserUsageSummaryItem = z.infer<typeof s.UserUsageSummaryItemSchema>;
export type UserUsageWindows = z.infer<typeof s.UserUsageWindowsSchema>;
export type UserUsageDetail = z.infer<typeof s.UserUsageDetailSchema>;

// ── Settings / AI Providers ──
export type AIProvider = z.infer<typeof s.AIProviderSchema>;
export type AIProviderCreate = z.infer<typeof s.AIProviderCreateSchema>;
export type AIProviderUpdate = z.infer<typeof s.AIProviderUpdateSchema>;
export type ApiKeyItem = z.infer<typeof s.ApiKeyItemSchema>;
export type ProviderTemplate = z.infer<typeof s.ProviderTemplateSchema>;

// ── Health ──
export type HealthCheck = z.infer<typeof s.HealthCheckSchema>;
export type HealthData = z.infer<typeof s.HealthDataSchema>;
