import re

from app.models import DocumentChunk, KnowledgeDocument


class Chunker:
    def split(self, document: KnowledgeDocument, version_id: int | None) -> list[DocumentChunk]:
        text = re.sub(r"\r\n?", "\n", document.content_text or "").strip()
        if not text:
            return []

        sections = self._sections(text)
        chunks: list[DocumentChunk] = []
        index = 0
        for title_path, content in sections:
            for piece in self._window(content):
                keywords = ",".join(self.keywords(piece))
                chunks.append(
                    DocumentChunk(
                        document_id=document.id,
                        version_id=version_id,
                        chunk_index=index,
                        title_path=title_path,
                        content=piece,
                        keywords=keywords,
                    )
                )
                index += 1
        return chunks

    def summarize(self, text: str, limit: int = 220) -> str:
        clean = re.sub(r"\s+", " ", text or "").strip()
        return clean[:limit]

    def keywords(self, text: str, limit: int = 12) -> list[str]:
        tokens = re.findall(r"[A-Za-z0-9_/-]{2,}|[\u4e00-\u9fff]{2,}", text or "")
        scores: dict[str, int] = {}
        for token in tokens:
            token = token.strip().lower()
            if len(token) < 2:
                continue
            scores[token] = scores.get(token, 0) + 1
        return [item for item, _ in sorted(scores.items(), key=lambda pair: pair[1], reverse=True)[:limit]]

    def _sections(self, text: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        current_title = "正文"
        buffer: list[str] = []
        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if self._looks_like_heading(stripped):
                if buffer:
                    sections.append((current_title, "\n".join(buffer)))
                    buffer = []
                current_title = stripped[:120]
            else:
                buffer.append(stripped)
        if buffer:
            sections.append((current_title, "\n".join(buffer)))
        return sections or [("正文", text)]

    def _window(self, text: str, max_chars: int = 900, overlap: int = 120) -> list[str]:
        clean = text.strip()
        if len(clean) <= max_chars:
            return [clean]
        pieces: list[str] = []
        start = 0
        while start < len(clean):
            end = min(start + max_chars, len(clean))
            pieces.append(clean[start:end].strip())
            if end == len(clean):
                break
            start = max(end - overlap, start + 1)
        return pieces

    def _looks_like_heading(self, line: str) -> bool:
        return bool(re.match(r"^(#{1,6}\s+|[一二三四五六七八九十]+[、.．]|[0-9]+[.．、]\s*)", line)) and len(line) <= 80


chunker = Chunker()

