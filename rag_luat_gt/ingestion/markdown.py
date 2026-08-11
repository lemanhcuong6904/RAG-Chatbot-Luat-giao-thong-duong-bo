from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


FRONT_MATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)


def split_front_matter(markdown_text: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(markdown_text)
    if not match:
        return {}, markdown_text

    metadata = yaml.safe_load(match.group(1)) or {}
    if not isinstance(metadata, dict):
        metadata = {}
    return metadata, markdown_text[match.end() :]


def read_markdown(path: Path) -> tuple[dict[str, Any], str]:
    return split_front_matter(path.read_text(encoding="utf-8-sig"))

