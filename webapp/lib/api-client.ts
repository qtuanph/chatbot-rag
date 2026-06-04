import type {
  AIProvider,
  AIProviderCreate,
  AIProviderUpdate,
  ApiKeyItem,
  AnalyticsStats,
  CreateUserRequest,
  DocumentDetail,
  DocumentListResponse,
  HealthData,
  LoginRequest,
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

const API_INTERNAL = process.env.API_INTERNAL_URL!;
const BROWSER_PROXY_BASE = "/api/bep";

function getBaseUrl(): string {
  return typeof window === "undefined" ? API_INTERNAL : BROWSER_PROXY_BASE;
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

export const authApi = {
  login: (data: LoginRequest): Promise<TokenResponse> =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  logout: (): Promise<{ status: string }> =>
    apiFetch<{ status: string }>("/auth/logout", { method: "POST" }),

  getMe: (token: string): Promise<UserInfo> => apiFetch<UserInfo>("/auth/me", {}, token),

  getUsers: (): Promise<UserItem[]> => apiFetch<UserItem[]>("/auth/users"),

  getRoles: (): Promise<RoleItem[]> => apiFetch<RoleItem[]>("/auth/roles"),

  createUser: (data: CreateUserRequest): Promise<UserItem> =>
    apiFetch<UserItem>("/auth/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteUser: (username: string): Promise<{ status: string }> =>
    apiFetch<{ status: string }>(`/auth/users/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }),

  getUsersUsageSummary: (): Promise<{ items: UserUsageSummaryItem[] }> =>
    apiFetch<{ items: UserUsageSummaryItem[] }>("/admin/users/usage"),

  getUserUsageDetail: (userId: string): Promise<UserUsageDetail> =>
    apiFetch<UserUsageDetail>(`/admin/users/${encodeURIComponent(userId)}/usage`),
};

export const tenantsApi = {
  list: (): Promise<TenantItem[]> => apiFetch<TenantItem[]>("/admin/tenants"),

  create: (data: TenantCreateRequest): Promise<TenantItem> =>
    apiFetch<TenantItem>("/admin/tenants", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  get: (tenantId: string): Promise<TenantItem> =>
    apiFetch<TenantItem>(`/admin/tenants/${encodeURIComponent(tenantId)}`),

  update: (tenantId: string, data: TenantUpdateRequest): Promise<TenantItem> =>
    apiFetch<TenantItem>(`/admin/tenants/${encodeURIComponent(tenantId)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  getSettings: (tenantId: string): Promise<TenantSetting> =>
    apiFetch<TenantSetting>(`/admin/tenants/${encodeURIComponent(tenantId)}/settings`),

  updateSettings: (tenantId: string, data: TenantSettingUpdateRequest): Promise<TenantSetting> =>
    apiFetch<TenantSetting>(`/admin/tenants/${encodeURIComponent(tenantId)}/settings`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  listApiKeys: (tenantId: string): Promise<TenantApiKeyItem[]> =>
    apiFetch<TenantApiKeyItem[]>(`/admin/tenants/${encodeURIComponent(tenantId)}/api-keys`),

  createApiKey: (tenantId: string, data: TenantApiKeyCreateRequest): Promise<TenantApiKeyCreateResponse> =>
    apiFetch<TenantApiKeyCreateResponse>(`/admin/tenants/${encodeURIComponent(tenantId)}/api-keys`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  revokeApiKey: (tenantId: string, keyId: string): Promise<TenantApiKeyItem> =>
    apiFetch<TenantApiKeyItem>(
      `/admin/tenants/${encodeURIComponent(tenantId)}/api-keys/${encodeURIComponent(keyId)}`,
      { method: "DELETE" },
    ),

  getMyTenant: (): Promise<TenantItem> => apiFetch<TenantItem>("/tenants/me"),

  getMySettings: (): Promise<TenantSetting> => apiFetch<TenantSetting>("/tenants/me/settings"),

  updateMySettings: (data: TenantSettingUpdateRequest): Promise<TenantSetting> =>
    apiFetch<TenantSetting>("/tenants/me/settings", {
      method: "PUT",
      body: JSON.stringify(data),
    }),
};

export const documentsApi = {
  list: (tenantId?: string): Promise<DocumentListResponse> => {
    const query = tenantId ? `?tenant_id=${encodeURIComponent(tenantId)}` : "";
    return apiFetch<DocumentListResponse>(`/documents${query}`);
  },

  get: (documentId: string): Promise<DocumentDetail> =>
    apiFetch<DocumentDetail>(`/documents/${encodeURIComponent(documentId)}`),

  upload: async (file: File, tenantId: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("tenant_id", tenantId);
    formData.append("file", file);

    return apiFetch<UploadResponse>("/upload", {
      method: "POST",
      body: formData,
    });
  },

  delete: (documentId: string): Promise<{ status: string; document_id: string }> =>
    apiFetch<{ status: string; document_id: string }>(`/documents/${encodeURIComponent(documentId)}`, {
      method: "DELETE",
    }),

  retry: (documentId: string): Promise<{ task_id: string; document_id: string; status: string }> =>
    apiFetch<{ task_id: string; document_id: string; status: string }>(
      `/documents/${encodeURIComponent(documentId)}/retry`,
      { method: "POST" },
    ),

  rechunk: (documentId: string): Promise<{ task_id: string; document_id: string; status: string }> =>
    apiFetch<{ task_id: string; document_id: string; status: string }>(
      `/documents/${encodeURIComponent(documentId)}/rechunk`,
      { method: "POST" },
    ),

  getStatus: (taskId: string): Promise<TaskStatus> =>
    apiFetch<TaskStatus>(`/status/${encodeURIComponent(taskId)}`),
};

export const treeApi = {
  get: (documentId: string, offset = 0, limit = 100): Promise<TreeResponse> => {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
    });
    return apiFetch<TreeResponse>(`/tree/${encodeURIComponent(documentId)}?${params.toString()}`);
  },

  getNode: (documentId: string, nodeId: string): Promise<NodeDetail> =>
    apiFetch<NodeDetail>(`/tree/${encodeURIComponent(documentId)}/nodes/${encodeURIComponent(nodeId)}`),

  search: (documentId: string, query: string): Promise<{ results: TreeSearchResult[] }> => {
    const params = new URLSearchParams({ query });
    return apiFetch<{ results: TreeSearchResult[] }>(
      `/tree/${encodeURIComponent(documentId)}/search?${params.toString()}`,
    );
  },
};

export const chatApi = {
  chatStream: (
    query: string,
    messages: Array<{ role: string; content: string }>,
    options?: { tenantId?: string | null; thinkingMode?: boolean },
  ) => {
    const controller = new AbortController();
    const payload = {
      query,
      messages,
      tenant_id: options?.tenantId ?? null,
      thinking_mode: Boolean(options?.thinkingMode),
    };

    const fetchStream = fetch("/api/bep/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    return { controller, fetchStream };
  },
};

export const analyticsApi = {
  getStats: (days = 30): Promise<AnalyticsStats> =>
    apiFetch<AnalyticsStats>(`/analytics/stats?days=${days}`),

  getMyUsageWindows: (): Promise<UserUsageWindows> =>
    apiFetch<UserUsageWindows>("/analytics/me/usage"),

  clearStats: (): Promise<{ status: string; deleted_records: number }> =>
    apiFetch<{ status: string; deleted_records: number }>("/analytics/stats", { method: "DELETE" }),

  getTenantsUsage: (days = 30): Promise<TenantUsageSummaryResponse> =>
    apiFetch<TenantUsageSummaryResponse>(`/admin/tenants/usage?days=${days}`),
};

export const healthApi = {
  get: (): Promise<{ status: string }> => apiFetch<{ status: string }>("/health"),
  getData: (): Promise<HealthData> => apiFetch<HealthData>("/health/data"),
};

export const settingsApi = {
  listProviders: (serviceType?: string): Promise<AIProvider[]> =>
    apiFetch<AIProvider[]>(`/settings/providers${serviceType ? `?service_type=${serviceType}` : ""}`),

  getProvider: (id: number): Promise<AIProvider> =>
    apiFetch<AIProvider>(`/settings/providers/${id}`),

  createProvider: (data: AIProviderCreate): Promise<AIProvider> =>
    apiFetch<AIProvider>("/settings/providers", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateProvider: (id: number, data: AIProviderUpdate): Promise<AIProvider> =>
    apiFetch<AIProvider>(`/settings/providers/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  deleteProvider: (id: number): Promise<{ status: string }> =>
    apiFetch<{ status: string }>(`/settings/providers/${id}`, { method: "DELETE" }),

  activateProvider: (id: number): Promise<AIProvider> =>
    apiFetch<AIProvider>(`/settings/providers/${id}/activate`, { method: "POST" }),

  testProvider: (id: number): Promise<{ success: boolean; message: string }> =>
    apiFetch<{ success: boolean; message: string }>(`/settings/providers/${id}/test`, { method: "POST" }),

  listKeys: (providerId: number): Promise<ApiKeyItem[]> =>
    apiFetch<ApiKeyItem[]>(`/settings/providers/${providerId}/keys`),

  addKey: (providerId: number, keyValue: string): Promise<ApiKeyItem> =>
    apiFetch<ApiKeyItem>(`/settings/providers/${providerId}/keys`, {
      method: "POST",
      body: JSON.stringify({ key_value: keyValue }),
    }),

  deleteKey: (providerId: number, keyId: number): Promise<{ status: string }> =>
    apiFetch<{ status: string }>(`/settings/providers/${providerId}/keys/${keyId}`, {
      method: "DELETE",
    }),

  getTemplates: (): Promise<ProviderTemplate[]> => apiFetch<ProviderTemplate[]>("/settings/templates"),
};

export { API_INTERNAL, BROWSER_PROXY_BASE };
