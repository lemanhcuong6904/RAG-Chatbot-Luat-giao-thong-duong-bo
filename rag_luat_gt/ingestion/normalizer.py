from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from rag_luat_gt.schemas import Document
from rag_luat_gt.text import normalize_text, strip_accents


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


def _metadata_text(metadata: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ["ghi_chu_nguon", "dinh_dang_nguon", "pham_vi_dieu"]:
        value = metadata.get(key)
        if value:
            values.append(str(value))
    for key in ["ghi_chu_hieu_luc", "noi_dung_sua_doi_chinh"]:
        value = metadata.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
    return strip_accents(normalize_text(" ".join(values)))


def _coverage_status(metadata: dict[str, Any]) -> str:
    if not metadata:
        return "UNKNOWN"

    text = _metadata_text(metadata)
    if metadata.get("phu_luc_co_trong_file") is False:
        return "MISSING_APPENDIX"
    if any(term in text for term in ["thieu phu luc", "khong chua phu luc", "chua co phu luc"]):
        return "MISSING_APPENDIX"
    if any(term in text for term in ["thieu bang", "khong chua bang", "bang chua co"]):
        return "MISSING_TABLE"
    if any(term in text for term in ["thieu trang", "mat trang", "khong day du"]):
        return "MISSING_PAGES"
    if any(term in text for term in ["mot phan", "trich xuat", "khong chua"]):
        return "PARTIAL"
    return str(metadata.get("coverage_status") or "COMPLETE")


def _source_quality(metadata: dict[str, Any], coverage_status: str) -> str:
    text = _metadata_text(metadata)
    if "ocr" in text:
        return "OCR"
    if coverage_status in {"PARTIAL", "MISSING_APPENDIX", "MISSING_TABLE", "MISSING_PAGES"}:
        return "PARTIAL_SOURCE"
    return "VERIFIED_METADATA" if metadata else "UNKNOWN"


def _ocr_quality(metadata: dict[str, Any]) -> str | None:
    text = _metadata_text(metadata)
    if "ocr" not in text:
        return None
    if any(term in text for term in ["unverified", "chua xac minh", "scan", "image-only"]):
        return "OCR_UNVERIFIED"
    return "OCR_NORMALIZED"


def normalize_document(metadata: dict[str, Any], source_file: str) -> Document:
    document_number = metadata.get("so_ky_hieu")
    coverage_status = _coverage_status(metadata)
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
        coverage_status=coverage_status,
        source_quality=_source_quality(metadata, coverage_status),
        ocr_quality=_ocr_quality(metadata),
        keywords=metadata.get("tu_khoa") or [],
        metadata=metadata,
    )
