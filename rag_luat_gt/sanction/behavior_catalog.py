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
    matches: list[dict[str, Any]] = []
    seen_codes: set[str] = set()

    for catalog_code, item in _catalog().items():
        aliases = item.get("aliases") or []
        matched_alias = next((str(alias) for alias in aliases if _norm(str(alias)) in normalized), None)
        if not matched_alias or catalog_code in seen_codes:
            continue
        seen_codes.add(catalog_code)
        matches.append({"catalog_code": catalog_code, "matched_alias": matched_alias, **item})

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
