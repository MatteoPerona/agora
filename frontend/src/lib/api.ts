import type {
  CreatePersonaPayload,
  PanelRecommendationResponse,
  Persona,
  UploadedDocument,
  SessionSnapshot,
  UserReasoningProfile,
} from '../types/models'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!(init?.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers,
    ...init,
  })

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message = typeof body.detail === 'string' ? body.detail : 'Request failed'
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export const api = {
  listPersonas() {
    return request<Persona[]>('/api/personas')
  },
  getProfile() {
    return request<UserReasoningProfile>('/api/profile')
  },
  uploadDocument(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return request<UploadedDocument>('/api/documents', {
      method: 'POST',
      body: formData,
    })
  },
  deleteDocument(documentId: string) {
    return request<UploadedDocument>(`/api/documents/${documentId}`, {
      method: 'DELETE',
    })
  },
  recommendPanel(payload: { decision: string; panel_size: number; manual_ids: string[]; document_ids: string[] }) {
    return request<PanelRecommendationResponse>('/api/panel/recommend', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  expandPersona(description: string) {
    return request<CreatePersonaPayload>('/api/personas/expand', {
      method: 'POST',
      body: JSON.stringify({ description }),
    })
  },
  createPersona(payload: CreatePersonaPayload) {
    return request<Persona>('/api/personas', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  createSession(payload: { decision: string; document_ids: string[]; persona_ids: string[]; round_goal: number }) {
    return request<SessionSnapshot>('/api/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },
  getSession(sessionId: string) {
    return request<SessionSnapshot>(`/api/sessions/${sessionId}`)
  },
  addInterjection(sessionId: string, content: string) {
    return request<SessionSnapshot>(`/api/sessions/${sessionId}/interjections`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    })
  },
  advanceSession(sessionId: string) {
    return request<SessionSnapshot>(`/api/sessions/${sessionId}/advance`, {
      method: 'POST',
    })
  },
  finishSession(sessionId: string) {
    return request<SessionSnapshot>(`/api/sessions/${sessionId}/finish`, {
      method: 'POST',
    })
  },
}
