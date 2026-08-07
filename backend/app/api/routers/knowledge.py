import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatMessage, ChatSession, DocumentChunk, KnowledgeDocument
from app.schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    ChatSourceOut,
    SearchResultOut,
)
from app.services.llm import llm_service
from app.services.interface_answer import augment_interface_hits, build_interface_answer
from app.services.search import knowledge_search

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("/search", response_model=list[SearchResultOut])
def search_knowledge(
    q: str,
    document_id: int | None = None,
    project: str | None = None,
    module: str | None = None,
    tags: str | None = None,
    limit: int = 10,
    db: Session = Depends(get_db),
) -> list[SearchResultOut]:
    hits = knowledge_search.search(db, q, document_id=document_id, project=project, module=module, tags=tags, limit=min(limit, 30))
    return [
        SearchResultOut(
            document_id=hit.document.id,
            chunk_id=hit.chunk_id,
            title=hit.document.title,
            original_filename=hit.document.original_filename,
            project=hit.document.project,
            module=hit.document.module,
            tags=hit.document.tags,
            snippet=hit.snippet,
            score=hit.score,
            source=hit.source,
            match_reason=hit.match_reason,
            created_at=hit.document.created_at,
        )
        for hit in hits
    ]


@router.get("/similar", response_model=list[SearchResultOut])
def similar_knowledge(
    q: str | None = None,
    document_id: int | None = None,
    project: str | None = None,
    limit: int = 6,
    db: Session = Depends(get_db),
) -> list[SearchResultOut]:
    query_text = (q or "").strip()
    source_project = project
    if document_id:
        document = db.get(KnowledgeDocument, document_id)
        if not document:
            raise HTTPException(status_code=404, detail="document not found")
        source_project = source_project or document.project
        query_text = query_text or " ".join(
            item
            for item in [document.title, document.keywords, document.summary, document.module, document.tags]
            if item
        )
    if not query_text:
        raise HTTPException(status_code=400, detail="q or document_id is required.")

    hits = knowledge_search.search(db, query_text, exclude_project=source_project, limit=min(limit * 3, 30))
    if document_id:
        hits = [hit for hit in hits if hit.document.id != document_id]
    hits = hits[: min(limit, 20)]
    return [
        SearchResultOut(
            document_id=hit.document.id,
            chunk_id=hit.chunk_id,
            title=hit.document.title,
            original_filename=hit.document.original_filename,
            project=hit.document.project,
            module=hit.document.module,
            tags=hit.document.tags,
            snippet=hit.snippet,
            score=hit.score,
            source=hit.source,
            match_reason=f"跨项目相似内容 / {hit.match_reason}",
            created_at=hit.document.created_at,
        )
        for hit in hits
    ]


@router.post("/chat/sessions", response_model=ChatSessionOut)
def create_chat_session(payload: ChatSessionCreate, db: Session = Depends(get_db)) -> ChatSession:
    session = ChatSession(title=payload.title, scope=payload.scope, document_id=payload.document_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
def list_chat_sessions(db: Session = Depends(get_db)) -> list[ChatSession]:
    return list(db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50)))


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_chat_messages(session_id: int, db: Session = Depends(get_db)) -> list[ChatMessageOut]:
    messages = list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())))
    return [_message_out(message) for message in messages]


@router.post("/chat/ask", response_model=ChatAskResponse)
def ask_knowledge(payload: ChatAskRequest, db: Session = Depends(get_db)) -> ChatAskResponse:
    session = _get_or_create_session(db, payload)
    target_document_id = payload.document_id or session.document_id
    target_project = payload.project
    target_module = payload.module
    if target_document_id and not target_project:
        document = db.get(KnowledgeDocument, target_document_id)
        if document:
            target_project = document.project
            target_module = target_module or document.module
    if payload.scope == "document" and not target_document_id:
        raise HTTPException(status_code=400, detail="document_id is required when scope is document.")

    hits = knowledge_search.search(
        db,
        payload.question,
        document_id=target_document_id if payload.scope in {"document", "auto"} and target_document_id else None,
        project=target_project if payload.scope == "project" else None,
        module=target_module if payload.scope == "project" and target_module else None,
        limit=payload.top_k,
    )
    if not hits and target_document_id:
        document = db.get(KnowledgeDocument, target_document_id)
        if document:
            hits = knowledge_search.search(db, document.title, document_id=target_document_id, limit=payload.top_k)
    hits = augment_interface_hits(db, payload.question, hits, document_id=target_document_id, limit=payload.top_k)

    sources = [
        ChatSourceOut(document_id=hit.document.id, chunk_id=hit.chunk_id, title=hit.document.title, snippet=hit.snippet)
        for hit in hits
    ]
    context_blocks = [_context_block(db, source) for source in sources]
    answer_text = build_interface_answer(db, payload.question, sources)
    answer_source = "structured" if answer_text else "ai"
    if not answer_text:
        answer_text, answer_source = llm_service.answer(db, payload.question, context_blocks)

    question = ChatMessage(session_id=session.id, role="user", content=payload.question, document_id=target_document_id, sources="[]")
    answer = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=answer_text,
        document_id=target_document_id,
        sources=json.dumps([source.model_dump() for source in sources], ensure_ascii=False),
    )
    if answer_source not in {"ai", "structured"}:
        answer.content = f"{answer.content}\n\nAnswer source: {answer_source}"
    db.add_all([question, answer])
    db.commit()
    db.refresh(session)
    db.refresh(question)
    db.refresh(answer)

    return ChatAskResponse(session=session, question=_message_out(question), answer=_message_out(answer), sources=sources)


def _context_block(db: Session, source: ChatSourceOut) -> str:
    content = source.snippet
    if source.chunk_id:
        chunk = db.get(DocumentChunk, source.chunk_id)
        if chunk and chunk.content:
            content = chunk.content
    return f"[{source.title}#{source.chunk_id or 'document'}]\n{content}"


def _get_or_create_session(db: Session, payload: ChatAskRequest) -> ChatSession:
    if payload.session_id:
        session = db.get(ChatSession, payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="chat session not found")
        return session
    session = ChatSession(
        title=payload.question[:60] or "Knowledge chat",
        scope=payload.scope,
        document_id=payload.document_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _message_out(message: ChatMessage) -> ChatMessageOut:
    try:
        sources = [ChatSourceOut(**item) for item in json.loads(message.sources or "[]")]
    except json.JSONDecodeError:
        sources = []
    return ChatMessageOut(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        document_id=message.document_id,
        sources=sources,
        created_at=message.created_at,
    )
