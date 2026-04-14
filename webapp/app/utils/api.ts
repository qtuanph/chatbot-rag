import axios from 'axios'
import type {
  TokenResponse,
  DocumentListResponse,
  UploadAcceptedResponse,
  DocumentDeleteResponse,
  TreeDataResponse,
  ChatResponse,
  ChatSession,
  HealthResponse,
  DetailedHealthResponse,
  CreateUserResponse,
  CreateUserRequest,
  ApiError
} from '../types/api'

// Type-safe API interfaces
interface AuthApi {
  login: (username: string, password: string) => Promise<TokenResponse>
  logout: () => Promise<void>
  isAuthenticated: () => boolean
  getUserRole: () => string | null
}

interface DocumentsApi {
  list: () => Promise<DocumentListResponse>
  upload: (file: File) => Promise<UploadAcceptedResponse>
  delete: (documentId: string) => Promise<DocumentDeleteResponse>
  getTree: (documentId: string) => Promise<TreeDataResponse>
  searchNodes: (documentId: string, query: string) => Promise<TreeDataResponse>
}

interface ChatApi {
  sendMessage: (query: string, sessionId?: string) => Promise<ChatResponse>
  getSessions: () => Promise<ChatSession[]>
}

interface HealthApi {
  getSystemStatus: () => Promise<DetailedHealthResponse>
}

interface UsersApi {
  list: () => Promise<CreateUserResponse[]>
  create: (userData: CreateUserRequest) => Promise<CreateUserResponse>
  delete: (username: string) => Promise<void>
}

// Main API client interface
interface ApiClient {
  auth: AuthApi
  documents: DocumentsApi
  chat: ChatApi
  health: HealthApi
  users: UsersApi
}

let apiClientInstance: ApiClient | null = null

export function useApiClient(): ApiClient {
  const config = useRuntimeConfig()

  if (!apiClientInstance) {
    const api = axios.create({
      baseURL: `${config.public.apiBase}/api/v1`,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Request interceptor - add auth token
    api.interceptors.request.use(
      (config) => {
        if (import.meta.client) {
          const token = localStorage.getItem('token')
          if (token) {
            config.headers.Authorization = `Bearer ${token}`
          }
        }
        return config
      },
      error => Promise.reject(error)
    )

    // Response interceptor - handle 401
    api.interceptors.response.use(
      response => response,
      (error) => {
        if (error.response?.status === 401) {
          if (import.meta.client) {
            localStorage.removeItem('token')
            localStorage.removeItem('userRole')
            localStorage.removeItem('username')
            window.location.href = '/'
          }
        }
        return Promise.reject(error)
      }
    )

    apiClientInstance = {
      auth: {
        login: async (username: string, password: string): Promise<TokenResponse> => {
          const response = await api.post<TokenResponse>('/auth/login', { username, password })
          const { access_token, role } = response.data

          if (import.meta.client) {
            localStorage.setItem('token', access_token)
            localStorage.setItem('userRole', role)
            localStorage.setItem('username', username)
          }

          return response.data
        },

        logout: async (): Promise<void> => {
          try {
            await api.post('/auth/logout')
          } finally {
            if (import.meta.client) {
              localStorage.removeItem('token')
              localStorage.removeItem('userRole')
              localStorage.removeItem('username')
            }
          }
        },

        isAuthenticated: (): boolean => {
          if (import.meta.client) {
            return !!localStorage.getItem('token')
          }
          return false
        },

        getUserRole: (): string | null => {
          if (import.meta.client) {
            return localStorage.getItem('userRole')
          }
          return null
        }
      },

      documents: {
        list: async (): Promise<DocumentListResponse> => {
          const response = await api.get<DocumentListResponse>('/documents')
          return response.data
        },

        upload: async (file: File): Promise<UploadAcceptedResponse> => {
          const formData = new FormData()
          formData.append('file', file)

          const response = await api.post<UploadAcceptedResponse>('/upload', formData, {
            headers: {
              'Content-Type': 'multipart/form-data'
            }
          })
          return response.data
        },

        delete: async (documentId: string): Promise<DocumentDeleteResponse> => {
          const response = await api.delete<DocumentDeleteResponse>(`/documents/${documentId}`)
          return response.data
        },

        getTree: async (documentId: string): Promise<TreeDataResponse> => {
          const response = await api.get<TreeDataResponse>(`/documents/${documentId}/tree`)
          return response.data
        },

        searchNodes: async (documentId: string, query: string): Promise<TreeDataResponse> => {
          const response = await api.get<TreeDataResponse>(
            `/documents/${documentId}/search?q=${encodeURIComponent(query)}`
          )
          return response.data
        }
      },

      chat: {
        sendMessage: async (query: string, sessionId?: string): Promise<ChatResponse> => {
          const response = await api.post<ChatResponse>('/chat', {
            query,
            session_id: sessionId
          })
          return response.data
        },

        getSessions: async (): Promise<ChatSession[]> => {
          const response = await api.get<ChatSession[]>('/chat/sessions')
          return response.data
        }
      },

      health: {
        getSystemStatus: async (): Promise<DetailedHealthResponse> => {
          const response = await api.get<HealthResponse>('/health/data')
          const data = response.data

          // Transform backend response to frontend format
          return {
            checks: data.checks,
            database: {
              total_documents: data.total_docs,
              processing: 0, // Backend doesn't provide this
              failed: 0, // Backend doesn't provide this
              completed: data.active_docs
            },
            vector_store: {
              total_vectors: 0, // Backend doesn't provide this in health endpoint
              collections: 1
            },
            timestamp: data.timestamp
          }
        }
      },

      users: {
        list: async (): Promise<CreateUserResponse[]> => {
          const response = await api.get<CreateUserResponse[]>('/auth/users')
          return response.data
        },

        create: async (userData: CreateUserRequest): Promise<CreateUserResponse> => {
          const response = await api.post<CreateUserResponse>('/auth/users', userData)
          return response.data
        },

        delete: async (username: string): Promise<void> => {
          await api.delete(`/auth/users/${username}`)
        }
      }
    }
  }

  return apiClientInstance
}

// Backward compatibility export with proper types
export const apiClient: ApiClient = {
  auth: {
    login: (username: string, password: string) => useApiClient().auth.login(username, password),
    logout: () => useApiClient().auth.logout(),
    isAuthenticated: () => useApiClient().auth.isAuthenticated(),
    getUserRole: () => useApiClient().auth.getUserRole()
  },
  documents: {
    list: () => useApiClient().documents.list(),
    upload: (file: File) => useApiClient().documents.upload(file),
    delete: (documentId: string) => useApiClient().documents.delete(documentId),
    getTree: (documentId: string) => useApiClient().documents.getTree(documentId),
    searchNodes: (documentId: string, query: string) => useApiClient().documents.searchNodes(documentId, query)
  },
  chat: {
    sendMessage: (query: string, sessionId?: string) => useApiClient().chat.sendMessage(query, sessionId),
    getSessions: () => useApiClient().chat.getSessions()
  },
  health: {
    getSystemStatus: () => useApiClient().health.getSystemStatus()
  },
  users: {
    list: () => useApiClient().users.list(),
    create: (userData: CreateUserData) => useApiClient().users.create(userData),
    delete: (username: string) => useApiClient().users.delete(username)
  }
}
