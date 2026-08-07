from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=6, max_length=80)
    email: str | None = None
    role: str = "user"


class DocumentImageOut(BaseModel):
    id: int
    filename: str
    file_path: str
    ocr_text: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionOut(BaseModel):
    id: int
    document_id: int
    version_no: int
    file_path: str
    file_hash: str
    file_size: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentChunkOut(BaseModel):
    id: int
    document_id: int
    version_id: int | None
    chunk_index: int
    title_path: str
    page_no: int | None
    content: str
    keywords: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ParseJobOut(BaseModel):
    id: int
    document_id: int
    version_id: int | None
    stage: str
    status: str
    message: str
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentOut(BaseModel):
    id: int
    title: str
    original_filename: str
    file_path: str
    file_type: str
    file_hash: str
    file_size: int
    status: str
    content_text: str
    summary: str
    keywords: str
    tags: str
    project: str | None
    module: str | None
    current_version_id: int | None
    created_at: datetime
    updated_at: datetime
    images: list[DocumentImageOut] = []
    versions: list[DocumentVersionOut] = []
    chunks: list[DocumentChunkOut] = []
    parse_jobs: list[ParseJobOut] = []

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentListItem(BaseModel):
    id: int
    title: str
    original_filename: str
    file_type: str
    file_size: int
    status: str
    summary: str
    keywords: str
    tags: str
    project: str | None
    module: str | None
    created_at: datetime
    image_count: int = 0
    chunk_count: int = 0
    test_case_count: int = 0


class ProjectSummaryOut(BaseModel):
    project: str
    document_count: int
    module_count: int
    updated_at: datetime | None = None


class TestCaseDraftBase(BaseModel):
    title: str
    priority: str = "P2"
    precondition: str = ""
    steps: str = ""
    expected_result: str = ""
    project: str | None = None
    module: str | None = None
    api_path: str | None = None
    method: str | None = None
    status: str = "draft"


class TestCaseDraftCreate(TestCaseDraftBase):
    document_id: int


class TestCaseDraftUpdate(TestCaseDraftBase):
    pass


class TestCaseDraftOut(TestCaseDraftBase):
    id: int
    document_id: int
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenerateCasesRequest(BaseModel):
    max_cases: int = 8


class AIConfigIn(BaseModel):
    provider: str = "mock"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = False


class AIConfigOut(BaseModel):
    id: int
    provider: str
    base_url: str
    api_key_masked: str
    model: str
    enabled: bool
    updated_at: datetime


class ModelConfigIn(BaseModel):
    provider: str = "openai_compatible"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    dimension: int | None = None
    enabled: bool = False


class ModelConfigOut(BaseModel):
    id: int
    kind: str
    provider: str
    base_url: str
    api_key_masked: str
    model: str
    dimension: int | None
    enabled: bool
    updated_at: datetime


class ModelTestRequest(BaseModel):
    text: str = "用一句话说明知识库连接测试成功。"


class ModelTestResponse(BaseModel):
    ok: bool
    kind: str
    message: str
    detail: str = ""


class SearchResultOut(BaseModel):
    document_id: int
    chunk_id: int | None = None
    title: str
    original_filename: str
    project: str | None
    module: str | None
    tags: str
    snippet: str
    score: float
    source: str = "mysql"
    match_reason: str = ""
    created_at: datetime


class ChatSourceOut(BaseModel):
    document_id: int
    chunk_id: int | None = None
    title: str
    snippet: str


class ChatMessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    document_id: int | None
    sources: list[ChatSourceOut] = []
    created_at: datetime


class ChatSessionCreate(BaseModel):
    title: str = "Knowledge chat"
    scope: str = "all"
    document_id: int | None = None


class ChatSessionOut(BaseModel):
    id: int
    title: str
    scope: str
    document_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatAskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    session_id: int | None = None
    document_id: int | None = None
    project: str | None = None
    module: str | None = None
    scope: str = "auto"
    top_k: int = Field(default=5, ge=1, le=12)


class ChatAskResponse(BaseModel):
    session: ChatSessionOut
    answer: ChatMessageOut
    question: ChatMessageOut
    sources: list[ChatSourceOut]


class ChatFeedbackIn(BaseModel):
    rating: str = Field(pattern="^(useful|not_useful|wrong)$")
    comment: str = ""


class ChatFeedbackOut(BaseModel):
    id: int
    message_id: int
    rating: str
    comment: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SpaceSummaryOut(BaseModel):
    project: str
    module: str | None = None
    document_count: int
    chunk_count: int


class TagSummaryOut(BaseModel):
    tag: str
    document_count: int


class DashboardOverviewOut(BaseModel):
    document_count: int
    indexed_count: int
    failed_count: int
    chunk_count: int
    chat_count: int
    feedback_count: int
    recent_documents: list[KnowledgeDocumentListItem]
    failed_jobs: list[ParseJobOut]
    popular_questions: list[ChatMessageOut]
    spaces: list[SpaceSummaryOut]
    tags: list[TagSummaryOut]


class QualityIssueOut(BaseModel):
    type: str
    severity: str
    title: str
    detail: str
    document_id: int | None = None
    job_id: int | None = None
    created_at: datetime | None = None
