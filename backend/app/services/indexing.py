from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import DocumentChunk, DocumentParseJob, DocumentVersion, KnowledgeDocument
from app.services.chunker import chunker
from app.services.vector_store import vector_store


class IndexingService:
    def index_document(self, db: Session, document: KnowledgeDocument, version: DocumentVersion | None) -> list[DocumentChunk]:
        job = DocumentParseJob(
            document_id=document.id,
            version_id=version.id if version else None,
            stage="index",
            status="running",
            started_at=datetime.utcnow(),
        )
        db.add(job)
        document.status = "chunking"
        db.flush()

        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        chunks = chunker.split(document, version.id if version else None)
        for item in chunks:
            db.add(item)
        document.summary = chunker.summarize(document.content_text)
        document.keywords = ",".join(chunker.keywords(document.content_text))
        document.status = "indexed"
        job.status = "success"
        job.finished_at = datetime.utcnow()
        job.message = f"Indexed {len(chunks)} chunks."
        db.flush()

        try:
            vector_store.upsert_chunks(chunks, db)
            db.flush()
        except Exception as exc:
            job.message = f"Indexed {len(chunks)} chunks. Qdrant skipped: {exc}"
        return chunks


indexing_service = IndexingService()
