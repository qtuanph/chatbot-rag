import type {
  LoginRequest,
  TokenResponse,
  UserInfo,
  UserItem,
  CreateUserRequest,
  RoleItem,
  ChatRequest,
  ChatResponse,
  ChatSession,
  DocumentListResponse,
  DocumentDetail,
  UploadResponse,
  TaskStatus,
  TreeResponse,
  TreeSearchResult,
  NodeDetail,
  HealthData,
} from "@/types/api";

// Browser: calls go through Next.js Route Handler proxy (/api/bep/...)
// The proxy reads JWT from session cookie and forwards with Bearer token.
// Token is NEVER exposed to browser JavaScript.
// All URLs must be configured via environment variables — no localhost fallbacks.
const API_BASE = process.env.NEXT_PUBLIC_API_URL!;
const API_INTERNAL = process.env.API_INTERNAL_URL!;

function getBaseUrl(): string {
  // On server (Node.js), use internal Docker URL; on client (browser), use proxy
  return typeof window === "undefined" ? API_INTERNAL : API_BASE;
}

class ApiError extends Error {
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
  if (typeof detail === "string" && detail.trim().length > 0) {
    return detail;
  }

  const error = record.error;
  if (error && typeof error === "object") {
    const message = (error as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim().length > 0) {
      return message;
    }
  }

  return fallback;
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  // Token only used for server-side calls (auth.ts authorize flow)
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, extractErrorMessage(body, res.statusText));
  }

  return res.json();
}

// --- Auth ---
export const authApi = {
  login: (data: LoginRequest): Promise<TokenResponse> =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  logout: (): Promise<{ status: string }> =>
    apiFetch<{ status: string }>("/auth/logout", { method: "POST" }),

  getMe: (token: string): Promise<UserInfo> =>
    apiFetch<UserInfo>("/auth/me", {}, token),

  getUsers: (): Promise<UserItem[]> =>
    apiFetch<UserItem[]>("/auth/users"),

  getRoles: (): Promise<RoleItem[]> =>
    apiFetch<RoleItem[]>("/auth/roles"),

  createUser: (data: CreateUserRequest): Promise<UserItem> =>
    apiFetch<UserItem>("/auth/users", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  deleteUser: (username: string): Promise<{ status: string }> =>
    apiFetch<{ status: string }>(`/auth/users/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }),
};

// --- Chat ---
export const chatApi = {
  send: (data: ChatRequest): Promise<ChatResponse> =>
    apiFetch<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getSessions: (): Promise<ChatSession[]> =>
    apiFetch<ChatSession[]>("/chat/sessions"),
};

// --- Documents ---
export const documentsApi = {
  list: (): Promise<DocumentListResponse> =>
    apiFetch<DocumentListResponse>("/documents"),

  get: (id: string): Promise<DocumentDetail> =>
    apiFetch<DocumentDetail>(`/documents/${id}`),

  upload: async (file: File): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${getBaseUrl()}/upload`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, extractErrorMessage(body, res.statusText));
    }
    return res.json();
  },

  delete: (id: string): Promise<{ status: string; document_id: string }> =>
    apiFetch<{ status: string; document_id: string }>(`/documents/${id}`, {
      method: "DELETE",
    }),

  retry: (id: string): Promise<{ task_id: string; document_id: string; status: string }> =>
    apiFetch<{ task_id: string; document_id: string; status: string }>(`/documents/${id}/retry`, {
      method: "POST",
    }),

  getStatus: (taskId: string): Promise<TaskStatus> =>
    apiFetch<TaskStatus>(`/status/${taskId}`),
};

// --- Tree ---
export const treeApi = {
  get: (documentId: string, offset: number = 0, limit: number = 20): Promise<TreeResponse> => {
    const params = new URLSearchParams({
      offset: String(offset),
      limit: String(limit),
    });
    return apiFetch<TreeResponse>(`/tree/${documentId}?${params.toString()}`);
  },

  getNode: (documentId: string, nodeId: string): Promise<NodeDetail> =>
    apiFetch<NodeDetail>(`/tree/${documentId}/nodes/${nodeId}`),

  search: (documentId: string, query: string): Promise<{ results: TreeSearchResult[] }> => {
    const params = new URLSearchParams({ query });
    return apiFetch<{ results: TreeSearchResult[] }>(`/tree/${documentId}/search?${params.toString()}`);
  },
};

// --- Health ---
export const healthApi = {
  get: (): Promise<{ status: string }> =>
    apiFetch<{ status: string }>("/health"),

  getData: (): Promise<HealthData> =>
    apiFetch<HealthData>("/health/data"),
};

// --- Memories ---
export interface MemoryItem {
  id: string;
  memory_type: string;
  content: string;
  is_active: boolean;
  created_at: string;
}

export const memoriesApi = {
  list: (): Promise<{ items: MemoryItem[] }> =>
    apiFetch<{ items: MemoryItem[] }>("/memories"),

  create: (data: { memory_type: string; content: string }): Promise<MemoryItem> =>
    apiFetch<MemoryItem>("/memories", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  update: (id: string, data: { content?: string; memory_type?: string; is_active?: boolean }): Promise<MemoryItem> =>
    apiFetch<MemoryItem>(`/memories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  delete: (id: string): Promise<void> =>
    apiFetch<void>(`/memories/${id}`, { method: "DELETE" }),
};

export { ApiError };
export { API_BASE };
