export interface DocumentImage {
  id: number
  filename: string
  file_path: string
  ocr_text: string
  created_at: string
}

export interface DocumentVersion {
  id: number
  document_id: number
  version_no: number
  file_path: string
  file_hash: string
  file_size: number
  created_at: string
}

export interface DocumentChunk {
  id: number
  document_id: number
  version_id: number | null
  chunk_index: number
  title_path: string
  page_no: number | null
  content: string
  keywords: string
  created_at: string
}

export interface ParseJob {
  id: number
  document_id: number
  version_id: number | null
  stage: string
  status: string
  message: string
  started_at: string | null
  finished_at: string | null
  created_at: string
}

export interface KnowledgeDocumentListItem {
  id: number
  title: string
  original_filename: string
  file_type: string
  file_size: number
  status: string
  summary: string
  keywords: string
  tags: string
  project: string | null
  module: string | null
  created_at: string
  image_count: number
  chunk_count: number
  test_case_count: number
}

export interface KnowledgeDocument extends KnowledgeDocumentListItem {
  file_path: string
  file_hash: string
  content_text: string
  current_version_id: number | null
  updated_at: string
  images: DocumentImage[]
  versions: DocumentVersion[]
  chunks: DocumentChunk[]
  parse_jobs: ParseJob[]
}

export interface TestCaseDraft {
  id: number
  document_id: number
  title: string
  priority: string
  precondition: string
  steps: string
  expected_result: string
  project: string | null
  module: string | null
  api_path: string | null
  method: string | null
  source: string
  status: string
  created_at: string
  updated_at: string
}

export interface AIConfig {
  id: number
  provider: string
  base_url: string
  api_key_masked: string
  model: string
  enabled: boolean
  updated_at: string
}

export interface ModelConfig {
  id: number
  kind: 'chat' | 'embedding' | 'rerank'
  provider: string
  base_url: string
  api_key_masked: string
  model: string
  dimension: number | null
  enabled: boolean
  updated_at: string
}

export interface ModelTestResponse {
  ok: boolean
  kind: string
  message: string
  detail: string
}

export interface SearchResult {
  document_id: number
  chunk_id: number | null
  title: string
  original_filename: string
  project: string | null
  module: string | null
  tags: string
  snippet: string
  score: number
  source: string
  match_reason: string
  created_at: string
}

export interface ChatSource {
  document_id: number
  chunk_id: number | null
  title: string
  snippet: string
}

export interface ChatMessage {
  id: number
  session_id: number
  role: 'user' | 'assistant'
  content: string
  document_id: number | null
  sources: ChatSource[]
  created_at: string
}

export interface ChatSession {
  id: number
  title: string
  scope: string
  document_id: number | null
  created_at: string
  updated_at: string
}

export interface ChatAskResponse {
  session: ChatSession
  question: ChatMessage
  answer: ChatMessage
  sources: ChatSource[]
}

export interface User {
  id: number
  username: string
  email: string | null
  role: string
  is_active: boolean
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: User
}

export interface SpaceSummary {
  project: string
  module: string | null
  document_count: number
  chunk_count: number
}

export interface TagSummary {
  tag: string
  document_count: number
}

export interface DashboardOverview {
  document_count: number
  indexed_count: number
  failed_count: number
  chunk_count: number
  chat_count: number
  feedback_count: number
  recent_documents: KnowledgeDocumentListItem[]
  failed_jobs: ParseJob[]
  popular_questions: ChatMessage[]
  spaces: SpaceSummary[]
  tags: TagSummary[]
}

export interface QualityIssue {
  type: string
  severity: string
  title: string
  detail: string
  document_id: number | null
  job_id: number | null
  created_at: string | null
}
