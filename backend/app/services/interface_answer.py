import re
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, KnowledgeDocument
from app.schemas import ChatSourceOut
from app.services.search import SearchHit


FIELD_QUESTION_TERMS = ("\u5165\u53c2", "\u51fa\u53c2", "\u53c2\u6570", "\u5b57\u6bb5", "\u8bf7\u6c42", "\u54cd\u5e94", "\u8fd4\u56de", "\u62a5\u6587")
INTERFACE_TERM = "\u63a5\u53e3"
QCC_TERM = "\u4f01\u67e5\u67e5"


@dataclass
class InterfaceField:
    field_cn: str = ""
    field_code: str = ""
    length: str = ""
    required: str = ""
    description: str = ""


@dataclass
class InterfaceTable:
    chunk_id: int
    document_id: int
    document_title: str
    interface_name: str = ""
    transaction_direction: str = ""
    interface_type: str = ""
    section: str = ""
    fields: list[InterfaceField] = field(default_factory=list)


def is_interface_field_question(question: str) -> bool:
    return INTERFACE_TERM in question and any(term in question for term in FIELD_QUESTION_TERMS)


def augment_interface_hits(
    db: Session,
    question: str,
    hits: list[SearchHit],
    *,
    document_id: int | None,
    limit: int,
) -> list[SearchHit]:
    if not is_interface_field_question(question):
        return hits

    query = (
        select(DocumentChunk, KnowledgeDocument)
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .where(
            or_(
                DocumentChunk.content.like("%Interface request fields%"),
                DocumentChunk.content.like("%Interface response fields%"),
                DocumentChunk.content.like("%Interface section: REQUEST%"),
                DocumentChunk.content.like("%Interface section: RESPONSE%"),
                DocumentChunk.content.like("%field_code:%"),
            )
        )
    )
    if document_id:
        query = query.where(KnowledgeDocument.id == document_id)
    if QCC_TERM in question:
        query = query.where(or_(KnowledgeDocument.title.like(f"%{QCC_TERM}%"), DocumentChunk.content.like(f"%{QCC_TERM}%"), DocumentChunk.title_path.like(f"%{QCC_TERM}%")))

    table_hits: list[SearchHit] = []
    for chunk, document in db.execute(query.order_by(DocumentChunk.chunk_index.asc()).limit(max(limit * 2, 12))):
        content = chunk.content or ""
        score = 10000.0
        if "REQUEST" in content and any(term in question for term in ("\u5165\u53c2", "\u8bf7\u6c42", "\u8bf7\u6c42\u53c2\u6570", "\u62a5\u6587")):
            score += 40
        if "RESPONSE" in content and any(term in question for term in ("\u51fa\u53c2", "\u54cd\u5e94", "\u8fd4\u56de")):
            score += 40
        table_hits.append(
            SearchHit(
                document=document,
                chunk_id=chunk.id,
                snippet=_snippet(content),
                score=score,
                source="structured-table",
                match_reason="Interface field table match",
            )
        )

    merged: dict[tuple[int, int | None], SearchHit] = {}
    for hit in table_hits + hits:
        key = (hit.document.id, hit.chunk_id)
        if key not in merged or merged[key].score < hit.score:
            merged[key] = hit
    return sorted(merged.values(), key=lambda item: item.score, reverse=True)[:limit]


def build_interface_answer(db: Session, question: str, sources: list[ChatSourceOut]) -> str | None:
    if not is_interface_field_question(question):
        return None

    tables: list[InterfaceTable] = []
    for source in sources:
        if not source.chunk_id:
            continue
        chunk = db.get(DocumentChunk, source.chunk_id)
        if not chunk or "Interface section:" not in (chunk.content or ""):
            continue
        if not _matches_question_scope(question, source, chunk):
            continue
        table = _parse_table(chunk, source)
        if table and (table.fields or table.section):
            tables.append(table)

    if not tables:
        return None

    wants_request = any(term in question for term in ("\u5165\u53c2", "\u8bf7\u6c42", "\u8bf7\u6c42\u53c2\u6570", "\u62a5\u6587"))
    wants_response = any(term in question for term in ("\u51fa\u53c2", "\u54cd\u5e94", "\u8fd4\u56de"))
    if not wants_request and not wants_response:
        wants_request = wants_response = True

    grouped = _filter_groups_by_question(_group_tables(tables), question)
    relevant: list[InterfaceTable] = []
    lines = ["\u6839\u636e\u6587\u6863\u4e2d\u7684\u63a5\u53e3\u5b57\u6bb5\u8868\uff0c\u627e\u5230\u4ee5\u4e0b\u7ed3\u6784\u5316\u4fe1\u606f\uff1a", ""]
    for index, group in enumerate(grouped, start=1):
        info_table = group[0]
        request_tables = [table for table in group if table.section.upper() == "REQUEST"]
        response_tables = [table for table in group if table.section.upper() == "RESPONSE"]
        section_tables: list[InterfaceTable] = []
        if wants_request:
            section_tables.extend(request_tables)
        if wants_response:
            section_tables.extend(response_tables)
        if not section_tables:
            section_tables = group
        relevant.extend(section_tables)

        if len(grouped) > 1:
            lines.append(f"{index}. {info_table.interface_name or '\u6587\u6863\u7247\u6bb5\u672a\u6807\u660e'}")
        else:
            lines.append(f"\u63a5\u53e3\u540d\u79f0\uff1a{info_table.interface_name or '\u6587\u6863\u7247\u6bb5\u672a\u6807\u660e'}")
        if info_table.transaction_direction:
            lines.append(f"\u4ea4\u6613\u65b9\u5411\uff1a{info_table.transaction_direction}")
        if info_table.interface_type:
            lines.append(f"\u63a5\u53e3\u7c7b\u578b\uff1a{info_table.interface_type}")

        if wants_request:
            lines.extend(["\u5165\u53c2\u5b57\u6bb5\uff08REQUEST\uff09\uff1a"])
            lines.extend(_format_section(request_tables))
        if wants_response:
            lines.extend(["\u51fa\u53c2\u5b57\u6bb5\uff08RESPONSE\uff09\uff1a"])
            lines.extend(_format_section(response_tables))
        lines.append("")

    lines.append("\u6765\u6e90\uff1a")
    seen_sources = set()
    for table in relevant:
        key = (table.document_title, table.chunk_id)
        if key in seen_sources:
            continue
        seen_sources.add(key)
        lines.append(f"- {table.document_title} #{table.chunk_id}")

    return "\n".join(lines)


def _matches_question_scope(question: str, source: ChatSourceOut, chunk: DocumentChunk) -> bool:
    explicit_terms = [QCC_TERM, "\u53cd\u6d17\u94b1", "\u9ed1\u540d\u5355", "\u6863\u6848", "\u5f81\u4fe1", "\u6388\u4fe1", "\u5408\u540c"]
    terms = [term for term in explicit_terms if term in question]
    if not terms:
        return True
    haystack = "\n".join([source.title or "", chunk.title_path or "", chunk.content or ""])
    return any(term in haystack for term in terms)


def _group_tables(tables: list[InterfaceTable]) -> list[list[InterfaceTable]]:
    grouped: dict[str, list[InterfaceTable]] = {}
    ordered_keys: list[str] = []
    for table in tables:
        key = table.interface_name or f"chunk-{table.chunk_id}"
        if key not in grouped:
            grouped[key] = []
            ordered_keys.append(key)
        grouped[key].append(table)
    return [grouped[key] for key in ordered_keys]


def _filter_groups_by_question(groups: list[list[InterfaceTable]], question: str) -> list[list[InterfaceTable]]:
    exact_patterns = [
        ("\u62a5\u544a\u7533\u8bf7\u63a5\u53e3", "\u62a5\u544a\u7533\u8bf7"),
        ("\u7533\u8bf7\u63a5\u53e3", "\u62a5\u544a\u7533\u8bf7"),
        ("\u7ed3\u679c\u5f02\u6b65\u63a8\u9001\u63a5\u53e3", "\u7ed3\u679c\u5f02\u6b65\u63a8\u9001"),
        ("\u5f02\u6b65\u63a8\u9001\u63a5\u53e3", "\u5f02\u6b65\u63a8\u9001"),
        ("WFS704", "WFS704"),
    ]
    target_terms = [target for pattern, target in exact_patterns if pattern in question]
    if not target_terms or len(groups) <= 1:
        return groups

    matched = []
    for group in groups:
        names = " ".join(table.interface_name for table in group)
        if any(term in names for term in target_terms):
            matched.append(group)
    return matched or groups


def _parse_table(chunk: DocumentChunk, source: ChatSourceOut) -> InterfaceTable | None:
    content = chunk.content or ""
    table = InterfaceTable(chunk_id=chunk.id, document_id=source.document_id, document_title=source.title)
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if line.startswith("Interface name:"):
            table.interface_name = line.split(":", 1)[1].strip()
        elif line.startswith("Transaction direction:"):
            table.transaction_direction = line.split(":", 1)[1].strip()
        elif line.startswith("Interface type:"):
            table.interface_type = line.split(":", 1)[1].strip()
        elif line.startswith("Interface section:"):
            table.section = line.split(":", 1)[1].strip()
        elif line.startswith("Row "):
            parsed = _parse_field_row(line)
            if parsed and not _is_loop_marker(parsed):
                table.fields.append(parsed)
    return table if table.section or table.fields else None


def _parse_field_row(line: str) -> InterfaceField | None:
    _, _, body = line.partition(":")
    if not body:
        return None
    data: dict[str, str] = {}
    for part in body.split(" | "):
        key, sep, value = part.partition(":")
        if sep:
            data[key.strip()] = value.strip()
    if not data:
        return None
    return InterfaceField(
        field_cn=data.get("field_cn", ""),
        field_code=data.get("field_code", ""),
        length=data.get("length", ""),
        required=data.get("required", ""),
        description=data.get("description", ""),
    )


def _is_loop_marker(field_item: InterfaceField) -> bool:
    marker = f"{field_item.field_cn} {field_item.field_code}".upper()
    return ("REQUEST" in marker and "\u5faa\u73af" in marker) or ("RESPONSE" in marker and "\u5faa\u73af" in marker)


def _format_section(tables: list[InterfaceTable]) -> list[str]:
    fields: list[InterfaceField] = []
    seen = set()
    has_table = bool(tables)
    for table in tables:
        for field_item in table.fields:
            key = (field_item.field_cn, field_item.field_code)
            if key in seen:
                continue
            seen.add(key)
            fields.append(field_item)

    if not fields:
        if has_table:
            return ["- \u6587\u6863\u4e2d\u5b58\u5728\u8be5\u65b9\u5411\u7684\u5b57\u6bb5\u8868\uff0c\u4f46\u5f53\u524d\u7247\u6bb5\u672a\u5217\u51fa\u5177\u4f53\u5b57\u6bb5\u3002"]
        return ["- \u5f53\u524d\u68c0\u7d22\u5230\u7684\u4e0a\u4e0b\u6587\u4e2d\u672a\u53d1\u73b0\u8be5\u65b9\u5411\u5b57\u6bb5\u8868\u3002"]

    return [
        "- "
        + "\uff1b".join(
            item
            for item in [
                f"{field_item.field_cn}\uff08{field_item.field_code}\uff09" if field_item.field_code else field_item.field_cn,
                f"\u957f\u5ea6\uff1a{field_item.length}" if field_item.length else "",
                f"\u5fc5\u8f93\uff1a{field_item.required}" if field_item.required else "",
                f"\u8bf4\u660e\uff1a{field_item.description}" if field_item.description else "",
            ]
            if item
        )
        for field_item in fields
    ]


def _snippet(text: str, length: int = 500) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    return clean[:length]
