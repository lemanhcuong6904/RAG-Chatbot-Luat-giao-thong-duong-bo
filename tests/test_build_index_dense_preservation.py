from __future__ import annotations

import json

from rag_luat_gt.ingestion.build_index import build_index


def test_build_index_can_preserve_dense_manifest_without_invalidating_ready(tmp_path) -> None:
    markdown_dir = tmp_path / "markdown"
    index_dir = tmp_path / "index"
    markdown_dir.mkdir()
    (markdown_dir / "doc.md").write_text(
        "---\nso_ky_hieu: 1/2026/TEST\nngay_co_hieu_luc: '2026-01-01'\n---\n\n"
        "#### Điều 1. Quy định thử\n"
        "1. Nội dung thử nghiệm.\n",
        encoding="utf-8",
    )

    first_manifest = build_index(markdown_dir, tmp_path, index_dir=index_dir, invalidate_dense=True)
    dense_manifest = {
        "ready": True,
        "collection": "traffic_law_chunks",
        "embedding_model": "BAAI/bge-m3",
        "corpus_hash": first_manifest["corpus_hash"],
        "chunking_version": first_manifest["chunking_version"],
        "chunks": first_manifest["chunks"],
    }
    manifest_path = index_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dense"] = dense_manifest
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    second_manifest = build_index(markdown_dir, tmp_path, index_dir=index_dir, invalidate_dense=False)

    assert second_manifest["dense"] == dense_manifest
