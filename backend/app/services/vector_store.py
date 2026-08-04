import hashlib
import math
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.models import DocumentChunk


@dataclass
class VectorHit:
    chunk_id: int
    score: float


class VectorStore:
    def embed(self, text: str) -> list[float]:
        vector = [0.0] * settings.embedding_dimension
        for token in text.split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % settings.embedding_dimension
            vector[index] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not settings.qdrant_url or not chunks:
            return
        self._ensure_collection()
        points = []
        for chunk in chunks:
            vector_id = f"chunk-{chunk.id}"
            chunk.vector_id = vector_id
            points.append(
                {
                    "id": vector_id,
                    "vector": self.embed(chunk.content),
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

    def search(self, query: str, limit: int = 8) -> list[VectorHit]:
        if not settings.qdrant_url:
            return []
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}/points/search"
        try:
            with httpx.Client(timeout=15) as client:
                response = client.post(url, json={"vector": self.embed(query), "limit": limit, "with_payload": True})
                response.raise_for_status()
        except httpx.HTTPError:
            return []
        hits: list[VectorHit] = []
        for item in response.json().get("result", []):
            payload = item.get("payload") or {}
            if payload.get("chunk_id"):
                hits.append(VectorHit(chunk_id=int(payload["chunk_id"]), score=float(item.get("score", 0))))
        return hits

    def _ensure_collection(self) -> None:
        url = f"{settings.qdrant_url.rstrip('/')}/collections/{settings.qdrant_collection}"
        payload = {"vectors": {"size": settings.embedding_dimension, "distance": "Cosine"}}
        with httpx.Client(timeout=15) as client:
            exists = client.get(url)
            if exists.status_code == 404:
                client.put(url, json=payload).raise_for_status()
            else:
                exists.raise_for_status()


vector_store = VectorStore()

