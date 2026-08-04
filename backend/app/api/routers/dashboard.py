import json

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatFeedback, ChatMessage, DocumentChunk, DocumentImage, DocumentParseJob, KnowledgeDocument, TestCaseDraft
from app.schemas import (
    ChatMessageOut,
    DashboardOverviewOut,
    KnowledgeDocumentListItem,
    ParseJobOut,
    SpaceSummaryOut,
    TagSummaryOut,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverviewOut)
def overview(db: Session = Depends(get_db)) -> DashboardOverviewOut:
    document_count = db.scalar(select(func.count(KnowledgeDocument.id))) or 0
    indexed_count = db.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.status == "indexed")) or 0
    failed_count = db.scalar(select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.status == "failed")) or 0
    chunk_count = db.scalar(select(func.count(DocumentChunk.id))) or 0
    chat_count = db.scalar(select(func.count(ChatMessage.id)).where(ChatMessage.role == "user")) or 0
    feedback_count = db.scalar(select(func.count(ChatFeedback.id))) or 0

    recent_documents = [_document_item(db, document) for document in db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(6))]
    failed_jobs = list(
        db.scalars(
            select(DocumentParseJob)
            .where(DocumentParseJob.status.in_(["failed", "error"]))
            .order_by(DocumentParseJob.created_at.desc())
            .limit(8)
        )
    )
    popular_questions = []
    for message in db.scalars(select(ChatMessage).where(ChatMessage.role == "user").order_by(ChatMessage.created_at.desc()).limit(6)):
        popular_questions.append(
            ChatMessageOut(
                id=message.id,
                session_id=message.session_id,
                role=message.role,
                content=message.content,
                document_id=message.document_id,
                sources=[],
                created_at=message.created_at,
            )
        )

    return DashboardOverviewOut(
        document_count=document_count,
        indexed_count=indexed_count,
        failed_count=failed_count,
        chunk_count=chunk_count,
        chat_count=chat_count,
        feedback_count=feedback_count,
        recent_documents=recent_documents,
        failed_jobs=[ParseJobOut.model_validate(job) for job in failed_jobs],
        popular_questions=popular_questions,
        spaces=_spaces(db),
        tags=_tags(db),
    )


def _document_item(db: Session, document: KnowledgeDocument) -> KnowledgeDocumentListItem:
    image_count = db.scalar(select(func.count(DocumentImage.id)).where(DocumentImage.document_id == document.id)) or 0
    chunk_count = db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)) or 0
    case_count = db.scalar(select(func.count(TestCaseDraft.id)).where(TestCaseDraft.document_id == document.id)) or 0
    return KnowledgeDocumentListItem(
        id=document.id,
        title=document.title,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        summary=document.summary,
        keywords=document.keywords,
        tags=document.tags,
        project=document.project,
        module=document.module,
        created_at=document.created_at,
        image_count=image_count,
        chunk_count=chunk_count,
        test_case_count=case_count,
    )


def _spaces(db: Session) -> list[SpaceSummaryOut]:
    rows = db.execute(
        select(KnowledgeDocument.project, KnowledgeDocument.module, func.count(KnowledgeDocument.id))
        .where(KnowledgeDocument.project.is_not(None))
        .group_by(KnowledgeDocument.project, KnowledgeDocument.module)
        .order_by(func.count(KnowledgeDocument.id).desc())
        .limit(20)
    )
    result: list[SpaceSummaryOut] = []
    for project, module, count in rows:
        chunk_count = db.scalar(
            select(func.count(DocumentChunk.id))
            .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
            .where(KnowledgeDocument.project == project, KnowledgeDocument.module == module)
        ) or 0
        result.append(SpaceSummaryOut(project=project or "未绑定项目", module=module, document_count=count, chunk_count=chunk_count))
    return result


def _tags(db: Session) -> list[TagSummaryOut]:
    counts: dict[str, int] = {}
    for tags in db.scalars(select(KnowledgeDocument.tags).where(KnowledgeDocument.tags != "")):
        for tag in [item.strip() for item in (tags or "").split(",") if item.strip()]:
            counts[tag] = counts.get(tag, 0) + 1
    return [TagSummaryOut(tag=tag, document_count=count) for tag, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:30]]

