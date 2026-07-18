import { z } from "zod/v4";

import type {
  AIProvider,
  AIProviderCreate,
  AIProviderUpdate,
  ApiKeyItem,
  AnalyticsStats,
  ChatFeedbackRequest,
  ChatFeedbackResponse,
  CreateUserRequest,
  DocumentDetail,
  DocumentListResponse,
  HealthData,
  LoginRequest,
  UpdateProfileRequest,
  ProviderTemplate,
  RoleItem,
  TaskStatus,
  TenantApiKeyCreateRequest,
  TenantApiKeyCreateResponse,
  TenantApiKeyItem,
  TenantCreateRequest,
  TenantItem,
  TenantSetting,
  TenantSettingUpdateRequest,
  TenantUpdateRequest,
  TenantUsageSummaryResponse,
  TreeResponse,
  NodeDetail,
  TreeSearchResult,
  TokenResponse,
  UploadResponse,
  UserInfo,
  UserItem,
  UserUsageDetail,
  UserUsageSummaryItem,
  UserUsageWindows,
} from "@/types/api";

import * as s from "@/lib/schemas";

const API_INTERNAL = process.env.API_INTERNAL_URL!;

function getBaseUrl(): string {
  return typeof window === "undefined" ? API_INTERNAL : "/api/bep";
}

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

function formatZodIssues(error: z.ZodError): string {
  if (!error.issues.length) {
    return "Payload không hợp lệ";
  }

  return error.issues
    .map((issue) => {
      const path = issue.path.length ? issue.path.join(".") : "payload";
      return `${path}: ${issue.message}`;
    })
    .join("; ");
}

function parseRequest<T>(schema: z.ZodType<T>, payload: unknown): T {
  const result = schema.safeParse(payload);
  if (!result.success) {
    throw new ApiError(400, formatZodIssues(result.error));
  }

  return result.data;
}

function extractErrorMessage(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") {
    return fallback;
  }

  const record = body as Record<string, unknown>;
  const detail = record.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as Record<string, unknown>;
    const msg = typeof first?.msg === "string" ? first.msg : "";
    const loc = Array.isArray(first?.loc) ? first.loc.map(String).join(".") : "";
    if (msg) {
      return loc ? `${loc}: ${msg}` : msg;
    }
  }

  return fallback;
}

async function apiFetch<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(options.headers || {});
  const hasFormDataBody = typeof FormData !== "undefined" && options.body instanceof FormData;

  if (!hasFormDataBody && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, extractErrorMessage(body, response.statusText));
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// Type-safe variant: parse response through Zod schema
async function apiFetchParse<T>(schema: z.ZodType<T>, path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const raw = await apiFetch<unknown>(path, options, token);
  return schema.parse(raw);
}

export const authApi = {
  login: (data: LoginRequest): Promise<TokenResponse> =>
    apiFetchParse(s.TokenResponseSchema, "/auth/login", {
      method: "POST",
      body: JSON.stringify(parseRequest(s.LoginRequestSchema, data)),
    }),

  logout: (): Promise<{ status: string }> =>
    apiFetchParse(s.LogoutResponseSchema, "/auth/logout", { method: "POST" }),

  getMe: (token: string): Promise<UserInfo> =>
    apiFetchParse(s.UserInfoSchema, "/auth/me", {}, token),

  updateProfile: (data: UpdateProfileRequest): Promise<UserInfo> =>
    apiFetchParse(s.UserInfoSchema, "/auth/me", {
      method: "PATCH",
      body: JSON.stringify(parseRequest(s.UpdateProfileRequestSchema, data)),
    }),

  getUsers: (): Promise<UserItem[]> =>
    apiFetchParse(z.array(s.UserItemSchema), "/auth/users"),

  getRoles: (): Promise<RoleItem[]> =>
    apiFetchParse(z.array(s.RoleItemSchema), "/auth/roles"),

  createUser: (data: CreateUserRequest): Promise<UserItem> =>
    apiFetchParse(s.UserItemSchema, "/auth/users", {
      method: "POST",
      body: JSON.stringify(parseRequest(s.CreateUserRequestSchema, data)),
    }),

  deleteUser: (username: string): Promise<{ status: string }> =>
    apiFetchParse(s.LogoutResponseSchema, `/auth/users/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }),

  getUsersUsageSummary: (): Promise<{ items: UserUsageSummaryItem[] }> =>
    apiFetchParse(
      z.object({ items: z.array(s.UserUsageSummaryItemSchema) }),
      "/admin/users/usage",
    ),

  getUserUsageDetail: (userId: string): Promise<UserUsageDetail> =>
    apiFetchParse(s.UserUsageDetailSchema, `/admin/users/${encodeURIComponent(userId)}/usage`),
};

export const tenantsApi = {
  list: (): Promise<TenantItem[]> =>
    apiFetchParse(z.array(s.TenantItemSchema), "/admin/tenants"),

  create: (data: TenantCreateRequest): Promise<TenantItem> =>
    apiFetchParse(s.TenantItemSchema, "/admin/tenants", {
      method: "POST",
      body: JSON.stringify(parseRequest(s.TenantCreateRequestSchema, data)),
    }),

  get: (tenantId: string): Promise<TenantItem> =>
    apiFetchParse(s.TenantItemSchema, `/admin/tenants/${encodeURIComponent(tenantId)}`),

  update: (tenantId: string, data: TenantUpdateRequest): Promise<TenantItem> =>
    apiFetchParse(s.TenantItemSchema, `/admin/tenants/${encodeURIComponent(tenantId)}`, {
      method: "PATCH",
      body: JSON.stringify(parseRequest(s.TenantUpdateRequestSchema, data)),
    }),

  getSettings: (tenantId: string): Promise<TenantSetting> =>
    apiFetchParse(s.TenantSettingSchema, `/admin/tenants/${encodeURIComponent(tenantId)}/settings`),

  updateSettings: (tenantId: string, data: TenantSettingUpdateRequest): Promise<TenantSetting> =>
    apiFetchParse(s.TenantSettingSchema, `/admin/tenants/${encodeURIComponent(tenantId)}/settings`, {
      method: "PUT",
      body: JSON.stringify(parseRequest(s.TenantSettingUpdateRequestSchema, data)),
    }),

  listApiKeys: (tenantId: string): Promise<TenantApiKeyItem[]> =>
    apiFetchParse(z.array(s.TenantApiKeyItemSchema), `/admin/tenants/${encodeURIComponent(tenantId)}/api-keys`),

  createApiKey: (tenantId: string, data: TenantApiKeyCreateRequest): Promise<TenantApiKeyCreateResponse> =>
    apiFetchParse(s.TenantApiKeyCreateResponseSchema, `/admin/tenants/${encodeURIComponent(tenantId)}/api-keys`, {
      method: "POST",
      body: JSON.stringify(parseRequest(s.TenantApiKeyCreateRequestSchema, data)),
    }),

  revokeApiKey: (tenantId: string, keyId: string): Promise<TenantApiKeyItem> =>
    apiFetchParse(s.TenantApiKeyItemSchema,
      `/admin/tenants/${encodeURIComponent(tenantId)}/api-keys/${encodeURIComponent(keyId)}`,
      { method: "DELETE" },
    ),

  getMyTenant: (): Promise<TenantItem> =>
    apiFetchParse(s.TenantItemSchema, "/tenants/me"),

  getMySettings: (): Promise<TenantSetting> =>
    apiFetchParse(s.TenantSettingSchema, "/tenants/me/settings"),

  updateMySettings: (data: TenantSettingUpdateRequest): Promise<TenantSetting> =>
    apiFetchParse(s.TenantSettingSchema, "/tenants/me/settings", {
      method: "PUT",
      body: JSON.stringify(parseRequest(s.TenantSettingUpdateRequestSchema, data)),
    }),
};

export const documentsApi = {
  list: (tenantId?: string): Promise<DocumentListResponse> => {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
    return apiFetchParse(s.DocumentListResponseSchema, `/documents${query}`);
  },

  get: (documentId: string): Promise<DocumentDetail> =>
    apiFetchParse(s.DocumentDetailSchema, `/documents/${encodeURIComponent(documentId)}`),

  upload: async (file: File, tenantId: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("tenant_id", tenantId);
    formData.append("file", file);

    return apiFetchParse(s.UploadResponseSchema, "/upload", {
      method: "POST",
      body: formData,
    });
  },

  delete: (documentId: string): Promise<{ status: string; document_id: string }> =>
    apiFetchParse(s.DocumentDeleteResponseSchema, `/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    }),

  retry: (documentId: string): Promise<{ task_id: string; document_id: string; status: string }> =>
    apiFetchParse(s.DocumentRetryResponseSchema, `/documents/${encodeURIComponent(documentId)}/retry`, {
      method: "POST",
    }),

  rechunk: (documentId: string): Promise<{ task_id: string; document_id: string; status: string }> =>
    apiFetchParse(s.DocumentRechunkResponseSchema, `/documents/${encodeURIComponent(documentId)}/rechunk`, {
      method: "POST",
    }),

  getStatus: (taskId: string): Promise<TaskStatus> =>
    apiFetchParse(s.TaskStatusSchema, `/status/${encodeURIComponent(taskId)}`),

  streamList: (tenantId?: string) => {
    const params = new URLSearchParams();
    if (tenantId) {
      params.set("tenant_id", tenantId);
    }
    const query = params.toString();
    return new EventSource(`/api/bep/documents/stream${query ? `?${query}` : ""}`);
  },
};

export const treeApi = {
  get: (documentId: string, offset = 0, limit = 100): Promise<TreeResponse> => {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
    });
    return apiFetchParse(s.TreeResponseSchema, `/tree/${encodeURIComponent(documentId)}?${params.toString()}`);
  },

  getNode: (documentId: string, nodeId: string): Promise<NodeDetail> =>
    apiFetchParse(s.NodeDetailSchema, `/tree/${encodeURIComponent(documentId)}/nodes/${encodeURIComponent(nodeId)}`),

  search: (documentId: string, query: string): Promise<{ results: TreeSearchResult[] }> => {
    const params = new URLSearchParams({ query });
    return apiFetchParse(
      z.object({ results: z.array(s.TreeSearchResultSchema) }),
      `/tree/${encodeURIComponent(documentId)}/search?${params.toString()}`,
    );
  },
};



export const analyticsApi = {
  getStats: (days = 30): Promise<AnalyticsStats> =>
    apiFetchParse(s.AnalyticsStatsSchema, `/analytics/stats?days=${days}`),

  getMyUsageWindows: (): Promise<UserUsageWindows> =>
    apiFetchParse(s.UserUsageWindowsSchema, "/analytics/me/usage"),

  clearStats: (): Promise<{ status: string; deleted_records: number }> =>
    apiFetchParse(
      z.object({ status: z.string(), deleted_records: z.number() }),
      "/analytics/stats",
      { method: "DELETE" },
    ),

  getTenantsUsage: (days = 30): Promise<TenantUsageSummaryResponse> =>
    apiFetchParse(s.TenantUsageSummaryResponseSchema, `/admin/tenants/usage?days=${days}`),
};

export const healthApi = {
  get: () =>
    apiFetchParse(s.HealthCheckSchema, "/health"),

  getData: (): Promise<HealthData> =>
    apiFetchParse(s.HealthDataSchema, "/health/data"),
};

export const settingsApi = {
  listProviders: (serviceType?: string): Promise<AIProvider[]> =>
    apiFetchParse(z.array(s.AIProviderSchema), `/settings/providers${serviceType ? `?service_type=${serviceType}` : ""}`),

  getProvider: (id: number): Promise<AIProvider> =>
    apiFetchParse(s.AIProviderSchema, `/settings/providers/${id}`),

  createProvider: (data: AIProviderCreate): Promise<AIProvider> =>
    apiFetchParse(s.AIProviderSchema, "/settings/providers", {
      method: "POST",
      body: JSON.stringify(parseRequest(s.AIProviderCreateSchema, data)),
    }),

  updateProvider: (id: number, data: AIProviderUpdate): Promise<AIProvider> =>
    apiFetchParse(s.AIProviderSchema, `/settings/providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(parseRequest(s.AIProviderUpdateSchema, data)),
    }),

  deleteProvider: (id: number): Promise<{ status: string }> =>
    apiFetchParse(s.LogoutResponseSchema, `/settings/providers/${id}`, { method: "DELETE" }),

  activateProvider: (id: number): Promise<AIProvider> =>
    apiFetchParse(s.AIProviderSchema, `/settings/providers/${id}/activate`, { method: "POST" }),

  testProvider: (id: number): Promise<{ success: boolean; message: string }> =>
    apiFetchParse(s.TestResultSchema, `/settings/providers/${id}/test`, { method: "POST" }),

  listKeys: (providerId: number): Promise<ApiKeyItem[]> =>
    apiFetchParse(z.array(s.ApiKeyItemSchema), `/settings/providers/${providerId}/keys`),

  addKey: (providerId: number, keyValue: string): Promise<ApiKeyItem> =>
    apiFetchParse(s.ApiKeyItemSchema, `/settings/providers/${providerId}/keys`, {
      method: "POST",
      body: JSON.stringify(parseRequest(s.ProviderApiKeyCreateRequestSchema, { key_value: keyValue })),
    }),

  deleteKey: (providerId: number, keyId: number): Promise<{ status: string }> =>
    apiFetchParse(s.LogoutResponseSchema, `/settings/providers/${providerId}/keys/${keyId}`, {
      method: "DELETE",
    }),

  getTemplates: (): Promise<ProviderTemplate[]> =>
    apiFetchParse(z.array(s.ProviderTemplateSchema), "/settings/templates"),
};

export { API_INTERNAL };
