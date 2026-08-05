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
        table_sections = self._table_sections(text)
        if table_sections:
            return table_sections
        return self._plain_sections(text) or [("正文", text)]

    def _table_sections(self, text: str) -> list[tuple[str, str]]:
        sections: list[tuple[str, str]] = []
        cursor = 0
        for match in re.finditer(r"(?s)\[TABLE:(\d+)\].*?\[/TABLE:\1\]", text):
            prefix = text[cursor : match.start()].strip()
            if prefix:
                sections.extend(self._plain_sections(prefix))
            block = match.group(0).strip()
            sections.append((self._table_title_path(block), block))
            cursor = match.end()
        suffix = text[cursor:].strip()
        if suffix:
            sections.extend(self._plain_sections(suffix))
        return sections

    def _plain_sections(self, text: str) -> list[tuple[str, str]]:
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
        return sections

    def _table_title_path(self, block: str) -> str:
        first_line = block.splitlines()[0].replace("[", "").replace("]", "")
        interface = self._extract_marker(block, "Interface name")
        direction = self._extract_marker(block, "Transaction direction")
        interface_type = self._extract_marker(block, "Interface type")
        section = self._extract_marker(block, "Interface section")
        parts = [first_line]
        if interface:
            parts.append(interface)
        if direction:
            parts.append(direction)
        if interface_type:
            parts.append(interface_type)
        if section:
            parts.append(section)
        return " / ".join(parts)[:500]

    def _extract_marker(self, block: str, name: str) -> str:
        match = re.search(rf"^{re.escape(name)}:\s*(.+)$", block, flags=re.MULTILINE)
        return match.group(1).strip() if match else ""

    def _window(self, text: str, max_chars: int = 1200, overlap: int = 160) -> list[str]:
        clean = text.strip()
        if clean.startswith("[TABLE:"):
            return [clean]
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
        return bool(re.match(r"^(#{1,6}\s+|[一二三四五六七八九十]+[、.．]\s*|[0-9]+[.．、]\s*)", line)) and len(line) <= 100


chunker = Chunker()
