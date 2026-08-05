import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatFeedback, ChatMessage, ChatSession, DocumentChunk, KnowledgeDocument
from app.schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatFeedbackIn,
    ChatFeedbackOut,
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    ChatSourceOut,
)
from app.services.llm import llm_service
from app.services.interface_answer import augment_interface_hits, build_interface_answer
from app.services.search import knowledge_search

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sessions", response_model=ChatSessionOut)
def create_chat_session(payload: ChatSessionCreate, db: Session = Depends(get_db)) -> ChatSession:
    session = ChatSession(title=payload.title, scope=payload.scope, document_id=payload.document_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions", response_model=list[ChatSessionOut])
def list_chat_sessions(db: Session = Depends(get_db)) -> list[ChatSession]:
    return list(db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(50)))


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_chat_messages(session_id: int, db: Session = Depends(get_db)) -> list[ChatMessageOut]:
    messages = list(db.scalars(select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc())))
    return [_message_out(message) for message in messages]


@router.post("/ask", response_model=ChatAskResponse)
def ask_knowledge(payload: ChatAskRequest, db: Session = Depends(get_db)) -> ChatAskResponse:
    session = _get_or_create_session(db, payload)
    target_document_id = payload.document_id or session.document_id
    if payload.scope == "document" and not target_document_id:
        raise HTTPException(status_code=400, detail="document_id is required when scope is document.")

    hits = knowledge_search.search(
        db,
        payload.question,
        document_id=target_document_id if payload.scope in {"document", "auto"} and target_document_id else None,
        limit=payload.top_k,
    )
    if not hits and target_document_id:
        hits = knowledge_search.search(db, payload.question, limit=payload.top_k)
    if not hits and target_document_id:
        document = db.get(KnowledgeDocument, target_document_id)
        if document:
            hits = knowledge_search.search(db, document.title, limit=payload.top_k)
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


@router.post("/messages/{message_id}/feedback", response_model=ChatFeedbackOut)
def save_feedback(message_id: int, payload: ChatFeedbackIn, db: Session = Depends(get_db)) -> ChatFeedback:
    message = db.get(ChatMessage, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="chat message not found")
    feedback = db.scalar(select(ChatFeedback).where(ChatFeedback.message_id == message_id))
    if not feedback:
        feedback = ChatFeedback(message_id=message_id, rating=payload.rating, comment=payload.comment)
        db.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment
    db.commit()
    db.refresh(feedback)
    return feedback


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
