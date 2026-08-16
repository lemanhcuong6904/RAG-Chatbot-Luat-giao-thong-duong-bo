#!/usr/bin/env python
"""
Extract YAML front matter metadata from Markdown files.

Default input:
  data/markdown

Default output:
  data/markdown_metadata.json
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any

ROOT_DIR = Path(".").resolve()
INPUT_DIR = ROOT_DIR / "data" / "markdown"
OUTPUT_FILE = ROOT_DIR / "data" / "markdown_metadata.json"

FRONT_MATTER_RE = re.compile(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", re.DOTALL)


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""

    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None

    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]

    if re.fullmatch(r"[-+]?\d+", value):
        return int(value)
    if re.fullmatch(r"[-+]?\d+\.\d+", value):
        return float(value)

    return value


def parse_simple_yaml(yaml_text: str) -> dict[str, Any]:
    """
    Minimal YAML parser for the current front matter shape:
    top-level key/value pairs and top-level lists written as:

      key:
        - item
    """
    metadata: dict[str, Any] = {}
    current_list_key: str | None = None

    for raw_line in yaml_text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        stripped = raw_line.strip()
        if stripped.startswith("- "):
            if current_list_key is None:
                raise ValueError(f"List item without a parent key: {raw_line!r}")
            metadata[current_list_key].append(parse_scalar(stripped[2:]))
            continue

        if raw_line.startswith((" ", "\t")):
            raise ValueError(f"Unsupported nested YAML line: {raw_line!r}")

        key, separator, value = stripped.partition(":")
        if not separator:
            raise ValueError(f"Unsupported YAML line: {raw_line!r}")

        key = key.strip()
        value = value.strip()
        if value == "":
            metadata[key] = []
            current_list_key = key
        else:
            metadata[key] = parse_scalar(value)
            current_list_key = None

    return metadata


def parse_front_matter(markdown_text: str) -> dict[str, Any]:
    match = FRONT_MATTER_RE.match(markdown_text)
    if not match:
        return {}

    yaml_text = match.group(1)
    try:
        import yaml  # type: ignore

        parsed = yaml.safe_load(yaml_text) or {}
        if not isinstance(parsed, dict):
            raise ValueError("YAML front matter is not a mapping")
        return parsed
    except ImportError:
        return parse_simple_yaml(yaml_text)


def extract_metadata(markdown_dir: Path, root_dir: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for markdown_file in sorted(markdown_dir.rglob("*.md")):
        relative_source = markdown_file.relative_to(root_dir).as_posix()
        text = markdown_file.read_text(encoding="utf-8-sig")
        metadata = parse_front_matter(text)
        records.append({"source_file": relative_source, "metadata": metadata})

    return records


def main() -> None:
    # Configure paths at the top of this file.
    if not INPUT_DIR.is_dir():
        raise FileNotFoundError(f"Markdown directory not found: {INPUT_DIR}")

    records = extract_metadata(INPUT_DIR, ROOT_DIR)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Extracted metadata from {len(records)} Markdown files")
    print(f"Output: {OUTPUT_FILE.relative_to(ROOT_DIR).as_posix()}")


if __name__ == "__main__":
    main()
