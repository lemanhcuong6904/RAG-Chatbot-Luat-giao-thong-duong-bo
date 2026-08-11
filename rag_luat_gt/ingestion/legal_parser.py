from __future__ import annotations

import re
from dataclasses import dataclass, field

from rag_luat_gt.schemas import Chunk, Document
from rag_luat_gt.text import normalize_text, strip_accents


CHAPTER_RE = re.compile(r"^(?:#{1,6}\s*)?Chương\s+([IVXLCDM\d]+)\b\.?\s*(.*)", re.IGNORECASE)
SECTION_RE = re.compile(r"^(?:#{1,6}\s*)?Mục\s+(\d+)\b\.?\s*(.*)", re.IGNORECASE)
ARTICLE_RE = re.compile(r"^(?:#{1,6}\s*)?Điều\s+(\d+[A-Za-z]?)\.\s*(.*)", re.IGNORECASE)
CLAUSE_RE = re.compile(r"^\s*(\d+)\.\s+(.+)")
POINT_RE = re.compile(r"^\s*([a-zđ])\)\s+(.+)", re.IGNORECASE)
HEADING_PREFIX_RE = re.compile(r"^#{1,6}\s*")
ISO_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")

MAX_CHUNK_CHARS = 2200
CHUNK_OVERLAP_LINES = 2


@dataclass
class _State:
    chapter: str | None = None
    section: str | None = None
    article: str | None = None
    article_title: str | None = None
    clause: str | None = None
    point: str | None = None
    lines: list[str] = field(default_factory=list)


def _clean_line(line: str) -> str:
    return HEADING_PREFIX_RE.sub("", line.strip()).strip()


def _heading_path(state: _State) -> list[str]:
    path: list[str] = []
    if state.chapter:
        path.append(f"Chương {state.chapter}")
    if state.section:
        path.append(f"Mục {state.section}")
    if state.article:
        item = f"Điều {state.article}"
        if state.article_title:
            item += f". {state.article_title}"
        path.append(item)
    if state.clause:
        path.append(f"Khoản {state.clause}")
    if state.point:
        path.append(f"Điểm {state.point}")
    return path


def _base_chunk_id(document: Document, state: _State, counter: int) -> str:
    parts = [document.document_id]
    if state.article:
        parts.append(f"DIEU_{state.article}")
    if state.clause:
        parts.append(f"KHOAN_{state.clause}")
    if state.point:
        parts.append(f"DIEM_{state.point.upper()}")
    parts.append(str(counter))
    return "__".join(parts)


def _chunk_type(state: _State) -> str:
    if state.point:
        return "POINT"
    if state.clause:
        return "CLAUSE"
    if state.article:
        return "ARTICLE"
    if state.section:
        return "SECTION"
    if state.chapter:
        return "CHAPTER"
    return "SPAN"


def _retrieval_text(document: Document, heading: str, text: str) -> str:
    return "\n".join(
        value
        for value in [
            f"Văn bản: {document.title or ''}",
            f"Số ký hiệu: {document.document_number or ''}",
            f"Loại văn bản: {document.document_type or ''}",
            heading,
            text,
            " ".join(document.keywords),
        ]
        if value.strip()
    )


def _matches_ref(note: str, state: _State) -> bool:
    normalized = strip_accents(normalize_text(note))
    if state.article and f"dieu {state.article}" not in normalized:
        return False
    if state.clause and f"khoan {state.clause}" not in normalized:
        return False
    if state.point and f"diem {state.point}" not in normalized:
        return False
    return bool(state.article or state.clause or state.point)


def _provision_effective_dates(document: Document, state: _State) -> tuple[str | None, str | None, str | None]:
    valid_from = document.effective_from
    valid_to = document.effective_to
    matched_note = None

    notes = document.metadata.get("ghi_chu_hieu_luc") or []
    if isinstance(notes, str):
        notes = [notes]

    for note in notes:
        if not _matches_ref(str(note), state):
            continue
        dates = ISO_DATE_RE.findall(str(note))
        if not dates:
            continue
        normalized = strip_accents(normalize_text(str(note)))
        matched_note = str(note)
        if any(term in normalized for term in ["het hieu luc", "den het ngay", "truoc ngay"]):
            valid_to = dates[-1]
        else:
            valid_from = dates[-1]

    return valid_from, valid_to, matched_note


def _split_long_line(line: str) -> list[str]:
    parts: list[str] = []
    start = 0
    while start < len(line):
        end = min(start + MAX_CHUNK_CHARS, len(line))
        if end < len(line):
            breakpoint = max(
                line.rfind("; ", start, end),
                line.rfind(". ", start, end),
                line.rfind(", ", start, end),
            )
            if breakpoint > start + MAX_CHUNK_CHARS // 2:
                end = breakpoint + 1
        parts.append(line[start:end].strip())
        start = end
    return parts


def _split_text_preserving_lines(lines: list[str]) -> list[str]:
    clean_lines = [line for line in lines if line.strip()]
    if not clean_lines:
        return []

    text = "\n".join(clean_lines).strip()
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    parts: list[str] = []
    current: list[str] = []

    for line in clean_lines:
        candidate = "\n".join([*current, line]).strip()
        if current and len(candidate) > MAX_CHUNK_CHARS:
            parts.append("\n".join(current).strip())
            current = current[-CHUNK_OVERLAP_LINES:] if CHUNK_OVERLAP_LINES else []

        if len(line) > MAX_CHUNK_CHARS:
            if current:
                parts.append("\n".join(current).strip())
                current = []
            parts.extend(_split_long_line(line))
        else:
            current.append(line)

    if current:
        parts.append("\n".join(current).strip())

    return [part for part in parts if part]


def _make_chunks(
    document: Document,
    state: _State,
    source_file: str,
    counter: int,
) -> list[Chunk]:
    text_parts = _split_text_preserving_lines(state.lines)
    if not text_parts:
        return []

    heading_path = _heading_path(state)
    heading = "\n".join(heading_path)
    base_chunk_id = _base_chunk_id(document, state, counter)
    valid_from, valid_to, provision_note = _provision_effective_dates(document, state)
    chunks: list[Chunk] = []

    for part_index, text in enumerate(text_parts, start=1):
        chunk_id = base_chunk_id
        if len(text_parts) > 1:
            chunk_id = f"{base_chunk_id}__PART_{part_index:03d}"

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                chunk_type=_chunk_type(state),
                document_id=document.document_id,
                document_number=document.document_number,
                document_title=document.title,
                article=state.article,
                article_title=state.article_title,
                clause=state.clause,
                point=state.point,
                article_id=None,
                parent_id=None,
                sibling_group_id=None,
                order=counter,
                heading_path=heading_path,
                text=text,
                retrieval_text=_retrieval_text(document, heading, text),
                valid_from=valid_from,
                valid_to=valid_to,
                source_file=source_file,
                coverage_status=document.coverage_status,
                source_quality=document.source_quality,
                ocr_quality=document.ocr_quality,
                metadata={
                    "chapter": state.chapter,
                    "section": state.section,
                    "split_part": part_index if len(text_parts) > 1 else None,
                    "split_total": len(text_parts) if len(text_parts) > 1 else None,
                    "provision_effective_note": provision_note,
                },
            )
        )

    return chunks


def parse_chunks(document: Document, markdown_body: str, source_file: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    state = _State()
    counter = 0

    def flush() -> None:
        nonlocal counter, state
        counter += 1
        chunks.extend(_make_chunks(document, state, source_file, counter))
        state.lines = []

    for raw_line in markdown_body.splitlines():
        line = _clean_line(raw_line)
        if not line:
            if state.lines:
                state.lines.append("")
            continue

        chapter_match = CHAPTER_RE.match(line)
        if chapter_match:
            flush()
            state.chapter = chapter_match.group(1)
            state.section = None
            state.article = None
            state.article_title = None
            state.clause = None
            state.point = None
            state.lines = [line]
            continue

        section_match = SECTION_RE.match(line)
        if section_match:
            flush()
            state.section = section_match.group(1)
            state.article = None
            state.article_title = None
            state.clause = None
            state.point = None
            state.lines = [line]
            continue

        article_match = ARTICLE_RE.match(line)
        if article_match:
            flush()
            state.article = article_match.group(1)
            state.article_title = article_match.group(2).strip() or None
            state.clause = None
            state.point = None
            state.lines = [line]
            continue

        clause_match = CLAUSE_RE.match(line)
        if clause_match and state.article:
            flush()
            state.clause = clause_match.group(1)
            state.point = None
            state.lines = [line]
            continue

        point_match = POINT_RE.match(line)
        if point_match and state.article and state.clause:
            flush()
            state.point = point_match.group(1).lower()
            state.lines = [line]
            continue

        state.lines.append(line)

    flush()
    return _annotate_hierarchy(chunks)


def _sort_key(chunk: Chunk) -> tuple[int, int, str]:
    type_rank = {
        "CHAPTER": 0,
        "SECTION": 1,
        "ARTICLE": 2,
        "CLAUSE": 3,
        "POINT": 4,
        "SPAN": 5,
    }.get(chunk.chunk_type, 9)
    return (chunk.order, type_rank, chunk.chunk_id)


def _annotate_hierarchy(chunks: list[Chunk]) -> list[Chunk]:
    article_by_key: dict[tuple[str, str | None], Chunk] = {}
    clause_by_key: dict[tuple[str, str | None, str | None], Chunk] = {}

    for index, chunk in enumerate(chunks, start=1):
        chunk.order = index
        if chunk.chunk_type == "ARTICLE":
            article_by_key[(chunk.document_id, chunk.article)] = chunk
        elif chunk.chunk_type == "CLAUSE":
            clause_by_key[(chunk.document_id, chunk.article, chunk.clause)] = chunk

    children_by_parent: dict[str, list[str]] = {}
    for chunk in chunks:
        article = article_by_key.get((chunk.document_id, chunk.article))
        if article:
            chunk.article_id = article.chunk_id

        if chunk.chunk_type == "CLAUSE" and article:
            chunk.parent_id = article.chunk_id
            chunk.sibling_group_id = article.chunk_id
            children_by_parent.setdefault(article.chunk_id, []).append(chunk.chunk_id)
        elif chunk.chunk_type == "POINT":
            clause = clause_by_key.get((chunk.document_id, chunk.article, chunk.clause))
            if clause:
                chunk.parent_id = clause.chunk_id
                chunk.sibling_group_id = clause.chunk_id
                children_by_parent.setdefault(clause.chunk_id, []).append(chunk.chunk_id)
            elif article:
                chunk.parent_id = article.chunk_id
                chunk.sibling_group_id = article.chunk_id
                children_by_parent.setdefault(article.chunk_id, []).append(chunk.chunk_id)

    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    for parent_id, child_ids in children_by_parent.items():
        parent = by_id[parent_id]
        parent.children_ids = [
            child.chunk_id
            for child in sorted((by_id[child_id] for child_id in child_ids), key=_sort_key)
        ]

    return chunks
