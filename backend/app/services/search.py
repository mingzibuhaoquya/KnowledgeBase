import re
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, KnowledgeDocument
from app.services.vector_store import vector_store


@dataclass
class SearchHit:
    document: KnowledgeDocument
    snippet: str
    score: float
    chunk_id: int | None = None
    source: str = "mysql"
    match_reason: str = ""


class KnowledgeSearchService:
    def search(
        self,
        db: Session,
        query: str,
        *,
        document_id: int | None = None,
        project: str | None = None,
        module: str | None = None,
        tags: str | None = None,
        limit: int = 10,
    ) -> list[SearchHit]:
        keywords = self._keywords(query)
        hits = self._mysql_hits(db, keywords, query, document_id, project, module, tags, limit * 2)
        hits.extend(self._vector_hits(db, query, document_id, project, module, tags, limit))

        merged: dict[tuple[int, int | None], SearchHit] = {}
        for hit in hits:
            key = (hit.document.id, hit.chunk_id)
            if key not in merged or merged[key].score < hit.score:
                merged[key] = hit
        ordered = sorted(merged.values(), key=lambda item: item.score, reverse=True)
        return ordered[:limit]

    def _mysql_hits(
        self,
        db: Session,
        keywords: list[str],
        query: str,
        document_id: int | None,
        project: str | None,
        module: str | None,
        tags: str | None,
        limit: int,
    ) -> list[SearchHit]:
        doc_stmt = select(KnowledgeDocument)
        chunk_stmt = select(DocumentChunk, KnowledgeDocument).join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)

        filters = []
        if document_id:
            filters.append(KnowledgeDocument.id == document_id)
        if project:
            filters.append(KnowledgeDocument.project == project)
        if module:
            filters.append(KnowledgeDocument.module == module)
        if tags:
            for tag in [item.strip() for item in tags.split(",") if item.strip()]:
                filters.append(KnowledgeDocument.tags.like(f"%{tag}%"))
        for item in filters:
            doc_stmt = doc_stmt.where(item)
            chunk_stmt = chunk_stmt.where(item)

        if keywords:
            doc_conditions = []
            chunk_conditions = []
            for keyword in keywords:
                like = f"%{keyword}%"
                doc_conditions.extend(
                    [
                        KnowledgeDocument.title.like(like),
                        KnowledgeDocument.original_filename.like(like),
                        KnowledgeDocument.content_text.like(like),
                        KnowledgeDocument.summary.like(like),
                        KnowledgeDocument.keywords.like(like),
                        KnowledgeDocument.tags.like(like),
                    ]
                )
                chunk_conditions.extend([DocumentChunk.content.like(like), DocumentChunk.keywords.like(like), DocumentChunk.title_path.like(like)])
            if not document_id:
                doc_stmt = doc_stmt.where(or_(*doc_conditions))
            chunk_stmt = chunk_stmt.where(or_(*chunk_conditions))

        hits: list[SearchHit] = []
        for document in db.scalars(doc_stmt.order_by(KnowledgeDocument.updated_at.desc()).limit(limit)):
            hits.append(self._rank_document(document, keywords, query))
        for chunk, document in db.execute(chunk_stmt.order_by(DocumentChunk.created_at.desc()).limit(limit)):
            hits.append(self._rank_chunk(document, chunk, keywords, query))
        return hits

    def _vector_hits(
        self,
        db: Session,
        query: str,
        document_id: int | None,
        project: str | None,
        module: str | None,
        tags: str | None,
        limit: int,
    ) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for vector_hit in vector_store.search(query, limit=limit):
            row = db.execute(
                select(DocumentChunk, KnowledgeDocument)
                .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
                .where(DocumentChunk.id == vector_hit.chunk_id)
            ).first()
            if not row:
                continue
            chunk, document = row
            if document_id and document.id != document_id:
                continue
            if project and document.project != project:
                continue
            if module and document.module != module:
                continue
            if tags and not all(tag.strip() in (document.tags or "") for tag in tags.split(",") if tag.strip()):
                continue
            hits.append(
                SearchHit(
                    document=document,
                    chunk_id=chunk.id,
                    snippet=self._snippet(chunk.content, [query]),
                    score=80.0 + vector_hit.score * 20.0,
                    source="qdrant",
                    match_reason="语义相似命中",
                )
            )
        return hits

    def _rank_document(self, document: KnowledgeDocument, keywords: list[str], query: str) -> SearchHit:
        haystack = "\n".join(
            [
                document.title or "",
                document.original_filename or "",
                document.project or "",
                document.module or "",
                document.summary or "",
                document.keywords or "",
                document.tags or "",
                document.content_text or "",
            ]
        ).lower()
        score = 1.0
        for keyword in keywords:
            score += haystack.count(keyword.lower()) * 5
            if keyword.lower() in (document.title or "").lower():
                score += 20
        reason = "标题/摘要/正文关键词命中" if keywords else "最近更新文档"
        return SearchHit(
            document=document,
            snippet=self._snippet(document.summary or document.content_text or document.title, keywords or [query]),
            score=score,
            match_reason=reason,
        )

    def _rank_chunk(self, document: KnowledgeDocument, chunk: DocumentChunk, keywords: list[str], query: str) -> SearchHit:
        haystack = "\n".join([chunk.title_path or "", chunk.keywords or "", chunk.content or ""]).lower()
        score = 10.0
        for keyword in keywords:
            score += haystack.count(keyword.lower()) * 8
            if keyword.lower() in (chunk.title_path or "").lower():
                score += 12
        return SearchHit(
            document=document,
            chunk_id=chunk.id,
            snippet=self._snippet(chunk.content, keywords or [query]),
            score=score,
            source="chunk",
            match_reason="知识切片关键词命中",
        )

    def _snippet(self, text: str, keywords: list[str], radius: int = 120) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        if not clean:
            return ""
        lower = clean.lower()
        positions = [lower.find(keyword.lower()) for keyword in keywords if keyword and lower.find(keyword.lower()) >= 0]
        start = max(min(positions) - radius, 0) if positions else 0
        end = min(start + radius * 2, len(clean))
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(clean) else ""
        return f"{prefix}{clean[start:end]}{suffix}"

    def _keywords(self, query: str) -> list[str]:
        words = re.findall(r"[\w\u4e00-\u9fff]+", query or "")
        seen: set[str] = set()
        keywords: list[str] = []
        for word in words:
            normalized = word.strip().lower()
            if len(normalized) < 2 or normalized in seen:
                continue
            seen.add(normalized)
            keywords.append(word.strip())
        return keywords[:8]


knowledge_search = KnowledgeSearchService()
