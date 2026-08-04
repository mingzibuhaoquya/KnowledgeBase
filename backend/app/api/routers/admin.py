from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatFeedback, DocumentChunk, DocumentParseJob, DocumentVersion, KnowledgeDocument
from app.schemas import ParseJobOut, QualityIssueOut
from app.services.indexing import indexing_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/jobs", response_model=list[ParseJobOut])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)) -> list[DocumentParseJob]:
    stmt = select(DocumentParseJob).order_by(DocumentParseJob.created_at.desc()).limit(100)
    if status:
        stmt = stmt.where(DocumentParseJob.status == status)
    return list(db.scalars(stmt))


@router.post("/jobs/{job_id}/retry", response_model=ParseJobOut)
def retry_job(job_id: int, db: Session = Depends(get_db)) -> DocumentParseJob:
    job = db.get(DocumentParseJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    document = db.get(KnowledgeDocument, job.document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    version = db.get(DocumentVersion, document.current_version_id) if document.current_version_id else None
    indexing_service.index_document(db, document, version)
    job.status = "success"
    job.message = "Retried by admin."
    db.commit()
    db.refresh(job)
    return job


@router.get("/quality/issues", response_model=list[QualityIssueOut])
def quality_issues(db: Session = Depends(get_db)) -> list[QualityIssueOut]:
    issues: list[QualityIssueOut] = []
    for document in db.scalars(select(KnowledgeDocument).order_by(KnowledgeDocument.updated_at.desc()).limit(200)):
        chunk_count = db.scalar(select(func.count(DocumentChunk.id)).where(DocumentChunk.document_id == document.id)) or 0
        if document.status != "indexed":
            issues.append(
                QualityIssueOut(
                    type="document_status",
                    severity="high",
                    title="文档未完成索引",
                    detail=f"{document.title} 当前状态为 {document.status}",
                    document_id=document.id,
                    created_at=document.updated_at,
                )
            )
        if not document.summary:
            issues.append(
                QualityIssueOut(
                    type="missing_summary",
                    severity="medium",
                    title="缺少摘要",
                    detail=f"{document.title} 尚未生成摘要",
                    document_id=document.id,
                    created_at=document.updated_at,
                )
            )
        if chunk_count == 0:
            issues.append(
                QualityIssueOut(
                    type="missing_chunks",
                    severity="high",
                    title="缺少知识切片",
                    detail=f"{document.title} 无法被稳定检索或问答引用",
                    document_id=document.id,
                    created_at=document.updated_at,
                )
            )
        if not document.project or not document.module:
            issues.append(
                QualityIssueOut(
                    type="missing_metadata",
                    severity="low",
                    title="缺少项目或模块",
                    detail=f"{document.title} 建议补充项目和模块，便于过滤检索",
                    document_id=document.id,
                    created_at=document.updated_at,
                )
            )
    for feedback in db.scalars(select(ChatFeedback).where(ChatFeedback.rating == "wrong").order_by(ChatFeedback.created_at.desc()).limit(50)):
        issues.append(
            QualityIssueOut(
                type="wrong_answer",
                severity="high",
                title="用户标记回答错误",
                detail=feedback.comment or "需要检查回答来源和检索上下文",
                created_at=feedback.created_at,
            )
        )
    return issues[:100]

