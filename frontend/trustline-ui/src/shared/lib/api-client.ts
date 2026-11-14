import { useAuthStore } from '@/features/auth/stores/auth-store';

const BASE_URL = '';

interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: Record<string, unknown> | FormData;
}

class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { token, isDemo } = useAuthStore.getState();
  const url = `${BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (isDemo) {
    headers['X-Trustline-Mode'] = 'demo';
  }

  let fetchBody: BodyInit | undefined;
  if (options.body instanceof FormData) {
    fetchBody = options.body;
  } else if (options.body) {
    headers['Content-Type'] = 'application/json';
    fetchBody = JSON.stringify(options.body);
  }

  const response = await fetch(url, {
    ...options,
    headers,
    body: fetchBody,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    if (response.status === 401) {
      useAuthStore.getState().logout();
    }
    throw new ApiError(response.status, data.detail || `HTTP ${response.status}`);
  }

  return data as T;
}

export const api = {
  // Auth
  register: (body: { username: string; password: string; role?: string; astronaut_id?: string | null }) =>
    request<{ id: string; username: string; role: string; astronaut_id: string | null }>('/auth/register', { method: 'POST', body: body as Record<string, unknown> }),

  login: (body: { username: string; password: string }) =>
    request<{ access_token: string; token_type: string; user: { sub: string; username: string; role: string; astronaut_id: string | null; is_demo: boolean } }>('/auth/login', { method: 'POST', body: body as Record<string, unknown> }),

  getMe: () =>
    request<{ sub: string; username: string; role: string; astronaut_id: string | null; is_demo: boolean }>('/auth/me'),

  // Chat Sessions
  listSessions: (params?: { q?: string; session_status?: string; limit?: number }) => {
    const searchParams = new URLSearchParams();
    if (params?.q) searchParams.set('q', params.q);
    if (params?.session_status) searchParams.set('session_status', params.session_status);
    if (params?.limit) searchParams.set('limit', String(params.limit));
    const qs = searchParams.toString();
    return request<Array<Record<string, unknown>>>(`/chat/sessions${qs ? `?${qs}` : ''}`);
  },

  createSession: (title = 'New Chat') =>
    request<Record<string, unknown>>('/chat/sessions', { method: 'POST', body: { title } }),

  getSession: (sessionId: string) =>
    request<Record<string, unknown>>(`/chat/sessions/${sessionId}`),

  patchSession: (sessionId: string, body: { title?: string; status?: string }) =>
    request<Record<string, unknown>>(`/chat/sessions/${sessionId}`, { method: 'PATCH', body: body as Record<string, unknown> }),

  deleteSession: (sessionId: string) =>
    request<void>(`/chat/sessions/${sessionId}`, { method: 'DELETE' }),

  getMessages: (sessionId: string) =>
    request<Array<{ id: string; session_id: string; sender: string; content: string; agent: string | null; processing_status: string; citations: unknown[]; created_at: string }>>(`/chat/sessions/${sessionId}/messages`),

  sendMessage: (sessionId: string, content: string | FormData) =>
    request<{ user_message: Record<string, unknown>; agent_message: Record<string, unknown>; provider_status: string; assessment?: Record<string, unknown> }>(`/chat/sessions/${sessionId}/messages`, { method: 'POST', body: typeof content === 'string' ? { content } : content }),

  // Assessments
  runAssessment: (body: { astronaut_id: string; text_query: string; session_id?: string; mission_context?: Record<string, unknown> }) =>
    request<Record<string, unknown>>('/assessments', { method: 'POST', body: body as Record<string, unknown> }),

  listAssessments: (astronautId?: string, limit = 50) => {
    const params = new URLSearchParams();
    if (astronautId) params.set('astronaut_id', astronautId);
    params.set('limit', String(limit));
    return request<Array<Record<string, unknown>>>(`/assessments?${params}`);
  },

  getAssessment: (assessmentId: string) =>
    request<Record<string, unknown>>(`/assessments/${assessmentId}`),

  // Telemetry
  getLatestTelemetry: (astronautId: string, sensorType?: string) => {
    const params = new URLSearchParams();
    if (sensorType) params.set('sensor_type', sensorType);
    return request<Array<Record<string, unknown>>>(`/telemetry/latest/${astronautId}${params.toString() ? `?${params}` : ''}`);
  },

  getTelemetryHistory: (astronautId: string, sensorType?: string, limit = 100) => {
    const params = new URLSearchParams();
    if (sensorType) params.set('sensor_type', sensorType);
    params.set('limit', String(limit));
    return request<Array<Record<string, unknown>>>(`/telemetry/history/${astronautId}?${params}`);
  },

  // Memory
  getMemories: (astronautId: string, namespace: string) =>
    request<Array<Record<string, unknown>>>(`/memory/${astronautId}/${namespace}`),

  // Documents
  uploadDocument: (file: File, astronautId: string) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('astronaut_id', astronautId);
    return request<Record<string, unknown>>('/documents/upload', { method: 'POST', body: formData });
  },

  getPendingRecords: (astronautId: string) =>
    request<Array<Record<string, unknown>>>(`/documents/pending/${astronautId}`),

  reviewRecord: (recordId: string, action: 'CONFIRMED' | 'REJECTED' | 'EDITED', reviewNotes?: string, editedFields?: Record<string, string>) =>
    request<Record<string, unknown>>(`/documents/records/${recordId}/review`, {
      method: 'POST',
      body: {
        record_id: recordId,
        action,
        review_notes: reviewNotes,
        ...editedFields,
      },
    }),

  processDocument: (documentId: string, forceOcr = false) =>
    request<Record<string, unknown>>(`/documents/${documentId}/process?force_ocr=${forceOcr}`, { method: 'POST' }),

  getDocumentRecords: (documentId: string) =>
    request<Array<Record<string, unknown>>>(`/documents/${documentId}/records`),

  // Radiation
  getRadiationLatest: () =>
    request<{ packet: Record<string, unknown> | null; limits: Record<string, unknown> }>('/radiation/latest'),

  getRadiationLimits: () =>
    request<Record<string, unknown>>('/radiation/limits'),

  // Admin
  getConnectivity: () =>
    request<Record<string, unknown>>('/admin/connectivity'),

  getAiProviders: () =>
    request<{ router_mode: string; providers: Array<any> }>('/ai/providers/status'),

  getSyncStatus: () =>
    request<{ counts: Record<string, number>; is_demo: boolean }>('/admin/sync/status'),

  runSync: (limit = 25) =>
    request<Record<string, unknown>>('/admin/sync/run', { method: 'POST', body: { limit } }),

  getUsers: () =>
    request<Array<Record<string, unknown>>>('/admin/users'),

  getAuditLogs: (limit = 100) =>
    request<Array<Record<string, unknown>>>(`/admin/audit?limit=${limit}`),

  getTransitions: (kind?: string, limit = 100) => {
    const params = new URLSearchParams({ limit: String(limit) });
    if (kind) params.set('kind', kind);
    return request<Array<Record<string, unknown>>>(`/admin/transitions?${params}`);
  },

  // Health
  getHealth: () =>
    request<{ status: string; service: string; database: string; timestamp: string }>('/health'),
};

export { ApiError };
export type { RequestOptions };
