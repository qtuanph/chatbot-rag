import type {
  LoginRequest,
  TokenResponse,
  UserInfo,
  UserItem,
  CreateUserRequest,
  ChatRequest,
  ChatResponse,
  ChatSession,
  DocumentListResponse,
  DocumentDetail,
  UploadResponse,
  TaskStatus,
  TreeResponse,
  NodeDetail,
  HealthData,
} from "@/types/api";

// Client-side: browser needs localhost (outside Docker)
// Server-side: inside Docker needs internal hostname
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
const API_INTERNAL = process.env.API_INTERNAL_URL || API_BASE;

function getBaseUrl(): string {
  // On server (Node.js), use internal Docker URL; on client (browser), use public URL
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

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${getBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
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

  logout: (token: string): Promise<{ status: string }> =>
    apiFetch<{ status: string }>("/auth/logout", { method: "POST" }, token),

  getMe: (token: string): Promise<UserInfo> =>
    apiFetch<UserInfo>("/auth/me", {}, token),

  getUsers: (token: string): Promise<UserItem[]> =>
    apiFetch<UserItem[]>("/auth/users", {}, token),

  createUser: (data: CreateUserRequest, token: string): Promise<UserItem> =>
    apiFetch<UserItem>("/auth/users", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),

  deleteUser: (username: string, token: string): Promise<{ status: string }> =>
    apiFetch<{ status: string }>(`/auth/users/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }, token),
};

// --- Chat ---
export const chatApi = {
  send: (data: ChatRequest, token: string): Promise<ChatResponse> =>
    apiFetch<ChatResponse>("/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }, token),

  getSessions: (token: string): Promise<ChatSession[]> =>
    apiFetch<ChatSession[]>("/chat/sessions", {}, token),
};

// --- Documents ---
export const documentsApi = {
  list: (token: string): Promise<DocumentListResponse> =>
    apiFetch<DocumentListResponse>("/documents", {}, token),

  get: (id: string, token: string): Promise<DocumentDetail> =>
    apiFetch<DocumentDetail>(`/documents/${id}`, {}, token),

  upload: async (file: File, token: string): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);

    const res = await fetch(`${getBaseUrl()}/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      throw new ApiError(res.status, body.detail || res.statusText);
    }
    return res.json();
  },

  delete: (id: string, token: string): Promise<{ status: string; document_id: string }> =>
    apiFetch<{ status: string; document_id: string }>(`/documents/${id}`, {
      method: "DELETE",
    }, token),

  getStatus: (taskId: string, token: string): Promise<TaskStatus> =>
    apiFetch<TaskStatus>(`/status/${taskId}`, {}, token),
};

// --- Tree ---
export const treeApi = {
  get: (documentId: string, token: string): Promise<TreeResponse> =>
    apiFetch<TreeResponse>(`/tree/${documentId}`, {}, token),

  getNode: (documentId: string, nodeId: string, token: string): Promise<NodeDetail> =>
    apiFetch<NodeDetail>(`/tree/${documentId}/nodes/${nodeId}`, {}, token),

  search: (documentId: string, query: string, token: string) =>
    apiFetch<{ results: unknown[] }>(`/tree/${documentId}/search?query=${encodeURIComponent(query)}`, {}, token),
};

// --- Health ---
export const healthApi = {
  get: (): Promise<{ status: string }> =>
    apiFetch<{ status: string }>("/health"),

  getData: (token: string): Promise<HealthData> =>
    apiFetch<HealthData>("/health/data", {}, token),
};

export { ApiError };
export { API_BASE };
