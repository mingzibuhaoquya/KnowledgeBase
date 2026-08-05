import re
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import DocumentChunk, KnowledgeDocument
from app.schemas import ChatSourceOut
from app.services.search import SearchHit


FIELD_QUESTION_TERMS = ("入参", "出参", "参数", "字段", "请求", "响应", "返回", "报文")


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
    return "接口" in question and any(term in question for term in FIELD_QUESTION_TERMS)


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
    if "企查查" in question:
        query = query.where(or_(KnowledgeDocument.title.like("%企查查%"), DocumentChunk.content.like("%企查查%"), DocumentChunk.title_path.like("%企查查%")))

    table_hits: list[SearchHit] = []
    for chunk, document in db.execute(query.order_by(DocumentChunk.chunk_index.asc()).limit(max(limit, 12))):
        content = chunk.content or ""
        score = 10000.0
        if "REQUEST" in content and any(term in question for term in ("入参", "请求", "请求参数", "报文")):
            score += 40
        if "RESPONSE" in content and any(term in question for term in ("出参", "响应", "返回")):
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

    wants_request = any(term in question for term in ("入参", "请求", "请求参数", "报文"))
    wants_response = any(term in question for term in ("出参", "响应", "返回"))
    if not wants_request and not wants_response:
        wants_request = wants_response = True

    lines = ["根据文档中的接口字段表，找到以下结构化信息：", ""]
    grouped = _filter_groups_by_question(_group_tables(tables), question)
    relevant: list[InterfaceTable] = []
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
            lines.append(f"{index}. {info_table.interface_name or '文档片段未标明'}")
        else:
            lines.append(f"接口名称：{info_table.interface_name or '文档片段未标明'}")
        if info_table.transaction_direction:
            lines.append(f"交易方向：{info_table.transaction_direction}")
        if info_table.interface_type:
            lines.append(f"接口类型：{info_table.interface_type}")

        if wants_request:
            lines.extend(["入参字段（REQUEST）："])
            lines.extend(_format_section(request_tables))
        if wants_response:
            lines.extend(["出参字段（RESPONSE）："])
            lines.extend(_format_section(response_tables))
        lines.append("")

    lines.append("来源：")
    seen_sources = set()
    for table in relevant:
        key = (table.document_title, table.chunk_id)
        if key in seen_sources:
            continue
        seen_sources.add(key)
        lines.append(f"- {table.document_title} #{table.chunk_id}")

    return "\n".join(lines)


def _matches_question_scope(question: str, source: ChatSourceOut, chunk: DocumentChunk) -> bool:
    explicit_terms = ["企查查", "反洗钱", "黑名单", "档案", "征信", "授信", "合同"]
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
    discriminators = ["报告申请", "报告结果", "异步推送", "申请", "结果", "异步", "推送", "新增", "WFS704"]
    terms = [term for term in discriminators if term in question]
    if not terms or len(groups) <= 1:
        return groups

    scored: list[tuple[int, list[InterfaceTable]]] = []
    for group in groups:
        names = " ".join(table.interface_name for table in group)
        score = 0
        for term in terms:
            score += 3 if len(term) >= 4 and term in names else 0
            score += 1 if len(term) < 4 and term in names else 0
        scored.append((score, group))

    max_score = max(score for score, _ in scored)
    second_score = max((score for score, _ in scored if score < max_score), default=0)
    if max_score <= 0 or max_score == second_score:
        return groups
    return [group for score, group in scored if score == max_score]


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
    return "REQUEST" in marker and "循环" in marker or "RESPONSE" in marker and "循环" in marker


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
            return ["- 文档中存在该方向的字段表，但当前片段未列出具体字段。"]
        return ["- 当前检索到的上下文中未发现该方向字段表。"]

    return [
        "- "
        + "；".join(
            item
            for item in [
                f"{field_item.field_cn}（{field_item.field_code}）" if field_item.field_code else field_item.field_cn,
                f"长度：{field_item.length}" if field_item.length else "",
                f"必输：{field_item.required}" if field_item.required else "",
                f"说明：{field_item.description}" if field_item.description else "",
            ]
            if item
        )
        for field_item in fields
    ]


def _snippet(text: str, length: int = 500) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    return clean[:length]
