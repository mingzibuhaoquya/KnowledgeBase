import hashlib
import math
from dataclasses import dataclass

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ModelConfig
from app.services.model_config import model_config_service


@dataclass
class RerankItem:
    index: int
    score: float


def local_hash_embedding(text: str, dimension: int | None = None) -> list[float]:
    size = dimension or settings.embedding_dimension
    vector = [0.0] * size
    for token in text.split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % size
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class OpenAICompatibleClient:
    def _headers(self, config: ModelConfig) -> dict[str, str]:
        api_key = model_config_service.api_key(config)
        return {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def _url(self, config: ModelConfig, suffix: str) -> str:
        base_url = config.base_url.rstrip("/")
        return base_url if base_url.endswith(suffix) else f"{base_url}{suffix}"


class ChatModelClient(OpenAICompatibleClient):
    def answer(self, config: ModelConfig, question: str, context_blocks: list[str]) -> str:
        url = self._url(config, "/chat/completions")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a Chinese knowledge-base assistant for R&D and testing teams. "
                    "Answer only from the provided context. If the context is insufficient, say so clearly. "
                    "Prefer structured answers, include test concerns when supported by the context, and do not invent facts."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Knowledge context:\n"
                    + "\n\n".join(context_blocks)
                    + f"\n\nUser question:\n{question}"
                ),
            },
        ]
        payload = {"model": config.model, "messages": messages, "temperature": 0.2}
        with httpx.Client(timeout=300) as client:
            response = client.post(url, headers=self._headers(config), json=payload)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def test(self, config: ModelConfig, text: str) -> str:
        return self.answer(config, text, ["Connection test context: KnowledgeBase is testing chat model connectivity."])


class EmbeddingClient(OpenAICompatibleClient):
    def embed(self, db: Session | None, text: str) -> list[float]:
        config = model_config_service.get(db, "embedding") if db else None
        if not self._usable(config):
            return local_hash_embedding(text, settings.embedding_dimension)
        try:
            return self._remote_embed(config, text)
        except Exception:
            return local_hash_embedding(text, config.dimension or settings.embedding_dimension)

    def embed_strict(self, config: ModelConfig, text: str) -> list[float]:
        return self._remote_embed(config, text)

    def _usable(self, config: ModelConfig | None) -> bool:
        return bool(config and config.enabled and config.base_url and config.model and config.provider != "mock")

    def _remote_embed(self, config: ModelConfig, text: str) -> list[float]:
        url = self._url(config, "/embeddings")
        payload = {"model": config.model, "input": text}
        with httpx.Client(timeout=45) as client:
            response = client.post(url, headers=self._headers(config), json=payload)
            response.raise_for_status()
            data = response.json()
        vector = data["data"][0]["embedding"]
        return [float(item) for item in vector]


class RerankClient(OpenAICompatibleClient):
    def rerank(self, db: Session, query: str, documents: list[str]) -> list[RerankItem]:
        config = model_config_service.get(db, "rerank")
        if not self._usable(config) or not documents:
            return []
        try:
            return self._remote_rerank(config, query, documents)
        except Exception:
            return []

    def test(self, config: ModelConfig, text: str) -> list[RerankItem]:
        return self._remote_rerank(config, text, ["KnowledgeBase model test document.", "Unrelated sample."])

    def _usable(self, config: ModelConfig | None) -> bool:
        return bool(config and config.enabled and config.base_url and config.model and config.provider != "mock")

    def _remote_rerank(self, config: ModelConfig, query: str, documents: list[str]) -> list[RerankItem]:
        url = self._url(config, "/rerank")
        payload = {"model": config.model, "query": query, "documents": documents}
        with httpx.Client(timeout=45) as client:
            response = client.post(url, headers=self._headers(config), json=payload)
            response.raise_for_status()
            data = response.json()
        raw_results = data.get("results") or data.get("data") or []
        items: list[RerankItem] = []
        for item in raw_results:
            index = item.get("index")
            if index is None:
                document = item.get("document")
                if isinstance(document, dict):
                    index = document.get("index")
            score = item.get("relevance_score", item.get("score", 0))
            if index is not None:
                items.append(RerankItem(index=int(index), score=float(score)))
        return items


chat_model_client = ChatModelClient()
embedding_client = EmbeddingClient()
rerank_client = RerankClient()
