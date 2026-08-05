from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.models import DocumentChunk, DocumentImage, DocumentParseJob, DocumentVersion, KnowledgeDocument, TestCaseDraft, User
from app.schemas import KnowledgeDocumentListItem, KnowledgeDocumentOut
from app.services.auth import get_current_user
from app.services.document_parser import document_parser
from app.services.indexing import indexing_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=KnowledgeDocumentOut)
async def upload_document(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    project: str | None = Form(None),
    module: str | None = Form(None),
    tags: str | None = Form(None),
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeDocument:
    parsed = await document_parser.save_and_parse(file)
    document = KnowledgeDocument(
        title=title or file.filename or parsed.stored_filename,
        original_filename=file.filename or parsed.stored_filename,
        file_path=parsed.file_path,
        file_type=parsed.file_type,
        file_hash=parsed.file_hash,
        file_size=parsed.file_size,
        status="parsing",
        content_text=parsed.content_text,
        project=project,
        module=module,
        tags=tags or "",
        uploaded_by=current_user.id if current_user else None,
    )
    db.add(document)
    db.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_no=1,
        file_path=parsed.file_path,
        file_hash=parsed.file_hash,
        file_size=parsed.file_size,
        content_text=parsed.content_text,
    )
    db.add(version)
    db.flush()
    document.current_version_id = version.id
    for image in parsed.images:
        document.images.append(
            DocumentImage(
                version_id=version.id,
                filename=image.filename,
                file_path=image.file_path,
                ocr_text=image.ocr_text,
            )
        )

    parse_job = DocumentParseJob(
        document_id=document.id,
        version_id=version.id,
        stage="parse",
        status="success",
        message="Document parsed.",
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(parse_job)
    indexing_service.index_document(db, document, version)

    db.commit()
    document = _load_document(db, document.id)
    return document


@router.post("", response_model=KnowledgeDocumentOut)
async def upload_document_compat(
    file: UploadFile = File(...),
    title: str | None = Form(None),
    project: str | None = Form(None),
    module: str | None = Form(None),
    tags: str | None = Form(None),
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> KnowledgeDocument:
    return await upload_document(file, title, project, module, tags, current_user, db)


@router.get("", response_model=list[KnowledgeDocumentListItem])
def list_documents(
    keyword: str | None = None,
    project: str | None = None,
    module: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[KnowledgeDocumentListItem]:
    image_counts = (
        select(DocumentImage.document_id, func.count(DocumentImage.id).label("image_count"))
        .group_by(DocumentImage.document_id)
        .subquery()
    )
    chunk_counts = (
        select(DocumentChunk.document_id, func.count(DocumentChunk.id).label("chunk_count"))
        .group_by(DocumentChunk.document_id)
        .subquery()
    )
    case_counts = (
        select(TestCaseDraft.document_id, func.count(TestCaseDraft.id).label("test_case_count"))
        .group_by(TestCaseDraft.document_id)
        .subquery()
    )
    stmt = (
        select(KnowledgeDocument, image_counts.c.image_count, chunk_counts.c.chunk_count, case_counts.c.test_case_count)
        .outerjoin(image_counts, KnowledgeDocument.id == image_counts.c.document_id)
        .outerjoin(chunk_counts, KnowledgeDocument.id == chunk_counts.c.document_id)
        .outerjoin(case_counts, KnowledgeDocument.id == case_counts.c.document_id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    if project:
        stmt = stmt.where(KnowledgeDocument.project == project)
    if module:
        stmt = stmt.where(KnowledgeDocument.module == module)
    if status:
        stmt = stmt.where(KnowledgeDocument.status == status)
    if tag:
        stmt = stmt.where(KnowledgeDocument.tags.like(f"%{tag}%"))
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(
            KnowledgeDocument.title.like(like)
            | KnowledgeDocument.original_filename.like(like)
            | KnowledgeDocument.content_text.like(like)
            | KnowledgeDocument.tags.like(like)
            | KnowledgeDocument.keywords.like(like)
        )

    rows = db.execute(stmt).all()
    return [
        KnowledgeDocumentListItem(
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
            image_count=image_count or 0,
            chunk_count=chunk_count or 0,
            test_case_count=test_case_count or 0,
        )
        for document, image_count, chunk_count, test_case_count in rows
    ]


@router.get("/{document_id}", response_model=KnowledgeDocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocument:
    document = _load_document(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.post("/{document_id}/reindex", response_model=KnowledgeDocumentOut)
def reindex_document(document_id: int, db: Session = Depends(get_db)) -> KnowledgeDocument:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    version = db.get(DocumentVersion, document.current_version_id) if document.current_version_id else None
    reparsed_text = document_parser.reparse_existing(document.file_path, document.file_type)
    if reparsed_text:
        document.content_text = reparsed_text
        if version:
            version.content_text = reparsed_text
    indexing_service.index_document(db, document, version)
    db.commit()
    return _load_document(db, document_id)


def _load_document(db: Session, document_id: int) -> KnowledgeDocument:
    return db.scalar(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.id == document_id)
        .options(
            selectinload(KnowledgeDocument.images),
            selectinload(KnowledgeDocument.versions),
            selectinload(KnowledgeDocument.chunks),
            selectinload(KnowledgeDocument.parse_jobs),
        )
    )
