from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import DocumentChunk
from app.services.model_clients import embedding_client, local_hash_embedding


@dataclass
class VectorHit:
    chunk_id: int
    score: float


class VectorStore:
    def embed(self, text: str, db: Session | None = None) -> list[float]:
        return embedding_client.embed(db, text)

    def upsert_chunks(self, chunks: list[DocumentChunk], db: Session | None = None) -> None:
        if not settings.qdrant_url or not chunks:
            return
        sample_vector = self.embed(chunks[0].content, db)
        self._ensure_collection(len(sample_vector))
        points = []
        for chunk in chunks:
            vector_id = chunk.id
            chunk.vector_id = str(vector_id)
            points.append(
                {
                    "id": vector_id,
                    "vector": self.embed(chunk.content, db),
                    "payload": {
                        "chunk_id": chunk.id,
                        "document_id": chunk.document_id,
                        "version_id": chunk.version_id,
                        "title_path": chunk.title_path,
                    },
                }
            )
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points?wait=true"
        with httpx.Client(timeout=20) as client:
            client.put(url, json={"points": points}).raise_for_status()

    def search(self, query: str, limit: int = 8, db: Session | None = None) -> list[VectorHit]:
        if not settings.qdrant_url:
            return []
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/search"
        try:
            vector = self.embed(query, db)
            with httpx.Client(timeout=15) as client:
                response = client.post(url, json={"vector": vector, "limit": limit, "with_payload": True})
                response.raise_for_status()
        except httpx.HTTPError:
            return []
        hits: list[VectorHit] = []
        for item in response.json().get("result", []):
            payload = item.get("payload") or {}
            if payload.get("chunk_id"):
                hits.append(VectorHit(chunk_id=int(payload["chunk_id"]), score=float(item.get("score", 0))))
        return hits

    def _ensure_collection(self, dimension: int | None = None) -> None:
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}"
        payload = {"vectors": {"size": dimension or settings.embedding_dimension, "distance": "Cosine"}}
        with httpx.Client(timeout=15) as client:
            exists = client.get(url)
            if exists.status_code == 404:
                client.put(url, json=payload).raise_for_status()
            else:
                exists.raise_for_status()

    def local_embed(self, text: str) -> list[float]:
        return local_hash_embedding(text, settings.embedding_dimension)


vector_store = VectorStore()
