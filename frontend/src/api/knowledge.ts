import { api } from './client'
import type {
  AIConfig,
  ChatAskResponse,
  ChatMessage,
  DashboardOverview,
  ChatSession,
  KnowledgeDocument,
  KnowledgeDocumentListItem,
  LoginResponse,
  ModelConfig,
  ModelTestResponse,
  ParseJob,
  QualityIssue,
  SearchResult
} from './types'

export async function listDocuments(params: {
  keyword?: string
  project?: string
  module?: string
  tag?: string
  status?: string
} = {}) {
  const { data } = await api.get<KnowledgeDocumentListItem[]>('/documents', { params })
  return data
}

export async function getDocument(id: number) {
  const { data } = await api.get<KnowledgeDocument>(`/documents/${id}`)
  return data
}

export async function uploadDocument(payload: FormData) {
  const { data } = await api.post<KnowledgeDocument>('/documents/upload', payload)
  return data
}

export async function reindexDocument(documentId: number) {
  const { data } = await api.post<KnowledgeDocument>(`/documents/${documentId}/reindex`)
  return data
}

export async function getAIConfig() {
  const { data } = await api.get<AIConfig | null>('/ai-config')
  return data
}

export async function saveAIConfig(payload: {
  provider: string
  base_url: string
  api_key: string
  model: string
  enabled: boolean
}) {
  const { data } = await api.put<AIConfig>('/ai-config', payload)
  return data
}

export async function listModelConfigs() {
  const { data } = await api.get<ModelConfig[]>('/model-configs')
  return data
}

export async function saveModelConfig(
  kind: ModelConfig['kind'],
  payload: {
    provider: string
    base_url: string
    api_key: string
    model: string
    dimension?: number | null
    enabled: boolean
  }
) {
  const { data } = await api.put<ModelConfig>(`/model-configs/${kind}`, payload)
  return data
}

export async function testModelConfig(kind: ModelConfig['kind'], text: string) {
  const { data } = await api.post<ModelTestResponse>(`/model-configs/${kind}/test`, { text })
  return data
}

export async function searchKnowledge(q: string, limit = 10) {
  const { data } = await api.get<SearchResult[]>('/knowledge/search', { params: { q, limit } })
  return data
}

export async function createChatSession(payload: { title: string; scope: string; document_id?: number | null }) {
  const { data } = await api.post<ChatSession>('/chat/sessions', payload)
  return data
}

export async function listChatMessages(sessionId: number) {
  const { data } = await api.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`)
  return data
}

export async function askKnowledge(payload: {
  question: string
  session_id?: number | null
  document_id?: number | null
  scope: string
  top_k?: number
}) {
  const { data } = await api.post<ChatAskResponse>('/chat/ask', payload)
  return data
}

export async function saveChatFeedback(messageId: number, payload: { rating: string; comment?: string }) {
  const { data } = await api.post(`/chat/messages/${messageId}/feedback`, payload)
  return data
}

export async function login(username: string, password: string) {
  const { data } = await api.post<LoginResponse>('/auth/login', { username, password })
  return data
}

export async function getDashboardOverview() {
  const { data } = await api.get<DashboardOverview>('/dashboard/overview')
  return data
}

export async function listAdminJobs(status?: string) {
  const { data } = await api.get<ParseJob[]>('/admin/jobs', { params: { status: status || undefined } })
  return data
}

export async function retryAdminJob(jobId: number) {
  const { data } = await api.post<ParseJob>(`/admin/jobs/${jobId}/retry`)
  return data
}

export async function listQualityIssues() {
  const { data } = await api.get<QualityIssue[]>('/admin/quality/issues')
  return data
}
