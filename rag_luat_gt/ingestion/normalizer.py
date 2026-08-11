from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from rag_luat_gt.schemas import Document


def _ascii_slug(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    value = value.upper().replace("Đ", "D")
    value = re.sub(r"[^A-Z0-9]+", "_", value)
    return re.sub(r"_+", "_", value).strip("_")


def document_id_from_number(document_number: str | None, source_file: str) -> str:
    if document_number:
        parts = document_number.split("/")
        if len(parts) >= 3:
            number = _ascii_slug(parts[0])
            year = _ascii_slug(parts[1])
            doc_type = _ascii_slug(parts[2])
            return f"{doc_type}_{number}_{year}"
        return _ascii_slug(document_number)
    return _ascii_slug(Path(source_file).stem)


def normalize_document(metadata: dict[str, Any], source_file: str) -> Document:
    document_number = metadata.get("so_ky_hieu")
    return Document(
        document_id=document_id_from_number(document_number, source_file),
        document_number=document_number,
        title=metadata.get("title") or metadata.get("trich_yeu"),
        document_type=metadata.get("loai_van_ban"),
        issuing_authority=metadata.get("co_quan_ban_hanh"),
        issue_date=metadata.get("ngay_ban_hanh"),
        effective_from=metadata.get("ngay_co_hieu_luc"),
        effective_to=metadata.get("ngay_het_hieu_luc"),
        source_markdown=source_file,
        source_original=metadata.get("file_nguon"),
        coverage_status="COMPLETE" if metadata else "UNKNOWN",
        keywords=metadata.get("tu_khoa") or [],
        metadata=metadata,
    )

