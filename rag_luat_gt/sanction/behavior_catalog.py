from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from rag_luat_gt.text import normalize_text, strip_accents


CATALOG_PATH = Path("data/curated/behavior_catalog.json")


def _norm(value: str) -> str:
    return strip_accents(normalize_text(value))


@lru_cache(maxsize=1)
def _catalog() -> dict[str, dict[str, Any]]:
    try:
        return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def match_behavior(query: str) -> dict[str, Any] | None:
    matches = match_behaviors(query)
    return matches[0] if matches else None


def match_behaviors(query: str) -> list[dict[str, Any]]:
    normalized = _norm(query)
    candidates: list[dict[str, Any]] = []
    matches: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    seen_aliases: list[str] = []

    for catalog_code, item in _catalog().items():
        aliases = item.get("aliases") or []
        matched_alias = next((str(alias) for alias in aliases if _norm(str(alias)) in normalized), None)
        if not matched_alias:
            continue
        normalized_alias = _norm(matched_alias)
        candidates.append(
            {
                "catalog_code": catalog_code,
                "matched_alias": matched_alias,
                "_match_start": normalized.find(normalized_alias),
                **item,
            }
        )

    candidates.sort(
        key=lambda match: (
            int(match.get("_match_start", 0)),
            -len(_norm(str(match.get("matched_alias") or ""))),
        )
    )
    for candidate in candidates:
        catalog_code = str(candidate["catalog_code"])
        matched_alias = _norm(str(candidate.get("matched_alias") or ""))
        if catalog_code in seen_codes or any(matched_alias in alias for alias in seen_aliases):
            continue
        seen_codes.add(catalog_code)
        seen_aliases.append(matched_alias)
        matches.append(candidate)

    return matches


def behavior_code_from_query(query: str) -> str | None:
    match = match_behavior(query)
    if not match:
        return None
    codes = match.get("rule_behavior_codes") or []
    return str(codes[0]) if codes else None


def behavior_contains_from_query(query: str) -> str | None:
    match = match_behavior(query)
    if not match:
        return None
    value = match.get("behavior_contains")
    return str(value) if value else None
