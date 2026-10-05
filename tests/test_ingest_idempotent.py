"""Idempotent index rebuild: the index reconciles to the corpus after every run.

These tests never load the real embedding model. They always inject a
deterministic, offline stub embedder through the store's seam.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from janbot.ingest import index_corpus
from janbot.ingest.scope import located_path
from janbot.store import VectorStore

_STUB_DIM = 64


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder; no model, stable across runs."""
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * _STUB_DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % _STUB_DIM
            vector[index] += 1.0
        vectors.append(vector)
    return vectors


def _write_org(path: Path, heading: str, body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"* {heading}\n{body}\n")


def _chunk_id(path: Path, ordinal: int, breadcrumb: str) -> str:
    """Build the id production would use: from the located path, not the symlink."""
    return f"{located_path(path)}::{ordinal}::{breadcrumb}"


def _ids(index_path: Path) -> set[str]:
    return VectorStore(index_path, _stub_embedder).ids()


def test_rerun_unchanged_yields_identical_collection(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    _write_org(corpus / "a.org", "Alpha")
    _write_org(corpus / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 2
    first = _ids(index_path)
    assert len(first) == 2

    assert index_corpus(corpus, index_path, _stub_embedder) == 2
    second = _ids(index_path)

    assert second == first
    assert len(second) == 2


def test_removed_file_chunks_are_deleted(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    _write_org(corpus / "keep.org", "Keep")
    _write_org(corpus / "drop.org", "Drop")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 2
    dropped = _ids(index_path) & {_chunk_id(corpus / "drop.org", 0, "Drop")}
    assert len(dropped) == 1

    (corpus / "drop.org").unlink()

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    remaining = _ids(index_path)

    assert remaining == {_chunk_id(corpus / "keep.org", 0, "Keep")}
    assert not remaining & dropped


def test_edited_subtree_replaces_chunk_without_duplication(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    source = corpus / "doc.org"
    _write_org(source, "About", "Original body.")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {_chunk_id(source, 0, "About")}

    _write_org(source, "About", "Rewritten body.")

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    rows = VectorStore(index_path, _stub_embedder).query("Rewritten")
    assert len(_ids(index_path)) == 1
    assert rows
    assert "Rewritten body." in rows[0]["text"]


def test_renamed_heading_removes_orphan(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    source = corpus / "doc.org"
    _write_org(source, "Old")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {_chunk_id(source, 0, "Old")}

    _write_org(source, "New")

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {_chunk_id(source, 0, "New")}


def test_empty_corpus_empties_populated_index(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    _write_org(corpus / "a.org", "Alpha")
    _write_org(corpus / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 2
    assert len(_ids(index_path)) == 2

    (corpus / "a.org").unlink()
    (corpus / "b.org").unlink()

    assert index_corpus(corpus, index_path, _stub_embedder) == 0
    assert _ids(index_path) == set()


def test_existing_collection_is_reused_without_corruption(tmp_path: Path) -> None:
    first = tmp_path / "first"
    _write_org(first / "a.org", "Alpha")
    second = tmp_path / "second"
    _write_org(second / "b.org", "Beta")
    index_path = tmp_path / "index"
    first_id = _chunk_id(first / "a.org", 0, "Alpha")
    second_id = _chunk_id(second / "b.org", 0, "Beta")

    assert index_corpus(first, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {first_id}

    assert index_corpus(second, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {first_id, second_id}

    assert index_corpus(first, index_path, _stub_embedder) == 1
    assert _ids(index_path) == {first_id, second_id}


def test_second_corpus_preserves_first_corpus_chunks(tmp_path: Path) -> None:
    first = tmp_path / "first"
    _write_org(first / "a.org", "Alpha")
    _write_org(first / "a2.org", "Alpha Two")
    second = tmp_path / "second"
    _write_org(second / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(first, index_path, _stub_embedder) == 2
    first_ids = _ids(index_path)
    assert len(first_ids) == 2

    assert index_corpus(second, index_path, _stub_embedder) == 1
    assert first_ids <= _ids(index_path)
    assert _chunk_id(second / "b.org", 0, "Beta") in _ids(index_path)


def test_missing_corpus_root_raises_and_leaves_index_intact(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    _write_org(corpus / "a.org", "Alpha")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, _stub_embedder) == 1
    before = _ids(index_path)
    assert len(before) == 1

    with pytest.raises(ValueError):
        index_corpus(tmp_path / "missing", index_path, _stub_embedder)

    file_root = corpus / "a.org"
    with pytest.raises(ValueError):
        index_corpus(file_root, index_path, _stub_embedder)

    assert _ids(index_path) == before
