"""Idempotent index rebuild: the index reconciles to the corpus after every run.

These tests never load the real embedding model; they inject the deterministic
stub embedder from ``conftest`` through the store's seam.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from janbot.ingest import index_corpus, read_org_file
from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]


def _ids(index_path: Path, embedder: Embedder) -> set[str]:
    return VectorStore(index_path, embedder).ids()


def _payload(
    index_path: Path, embedder: Embedder
) -> dict[str, tuple[str, tuple[float, ...]]]:
    return VectorStore(index_path, embedder).payload()


def _assert_payload_equal(
    actual: dict[str, tuple[str, tuple[float, ...]]],
    expected: dict[str, tuple[str, tuple[float, ...]]],
    *,
    tol: float = 1e-5,
) -> None:
    """Compare payloads by document exactly and embeddings within ``tol``.

    Chroma persists embeddings as float32, so a stored vector read back drifts
    from the exact embedder output by float32 epsilon; comparing within ``tol``
    keeps the assertion meaningful while still catching real corruption.
    """
    assert set(actual) == set(expected)
    for chunk_id in expected:
        actual_doc, actual_vec = actual[chunk_id]
        expected_doc, expected_vec = expected[chunk_id]
        assert actual_doc == expected_doc
        assert len(actual_vec) == len(expected_vec)
        for actual_value, expected_value in zip(actual_vec, expected_vec):
            assert abs(actual_value - expected_value) <= tol


def _expected_payload(
    corpus: Path, embedder: Embedder
) -> dict[str, tuple[str, tuple[float, ...]]]:
    """Independent oracle: the payload the chunks *should* carry, derived from
    the reader and the embedder directly rather than from the store's upsert
    path, so a corruption in either half of a stored payload is detected."""
    expected: dict[str, tuple[str, tuple[float, ...]]] = {}
    for path in sorted(corpus.glob("*.org")):
        for chunk in read_org_file(path):
            expected[chunk.id] = (
                chunk.text,
                tuple(float(value) for value in embedder([chunk.text])[0]),
            )
    return expected


def test_rerun_unchanged_yields_identical_collection(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "a.org", "Alpha")
    write_org(corpus / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 2
    first = _ids(index_path, embedder)
    assert len(first) == 2

    assert index_corpus(corpus, index_path, embedder) == 2
    second = _ids(index_path, embedder)

    assert second == first
    assert len(second) == 2


def test_rerun_preserves_documents_and_embeddings(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "a.org", "Alpha")
    write_org(corpus / "b.org", "Beta")
    index_path = tmp_path / "index"
    expected = _expected_payload(corpus, embedder)

    assert index_corpus(corpus, index_path, embedder) == 2
    _assert_payload_equal(_payload(index_path, embedder), expected)

    assert index_corpus(corpus, index_path, embedder) == 2
    _assert_payload_equal(_payload(index_path, embedder), expected)


def test_rerun_repairs_corrupted_payload(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "a.org", "Alpha")
    index_path = tmp_path / "index"
    expected = _expected_payload(corpus, embedder)

    assert index_corpus(corpus, index_path, embedder) == 1
    chunk_id = next(iter(expected))

    store = VectorStore(index_path, embedder)
    store._collection.update(
        ids=[chunk_id],
        documents=["CORRUPTED"],
        embeddings=[[0.0] * 64],
    )
    assert _payload(index_path, embedder)[chunk_id][0] != expected[chunk_id][0]

    assert index_corpus(corpus, index_path, embedder) == 1
    _assert_payload_equal(_payload(index_path, embedder), expected)


def test_removed_file_chunks_are_deleted(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    chunk_id: Callable[..., str],
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "keep.org", "Keep")
    write_org(corpus / "drop.org", "Drop")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 2
    dropped = _ids(index_path, embedder) & {chunk_id(corpus / "drop.org", 0, "Drop")}
    assert len(dropped) == 1

    (corpus / "drop.org").unlink()

    assert index_corpus(corpus, index_path, embedder) == 1
    remaining = _ids(index_path, embedder)

    assert remaining == {chunk_id(corpus / "keep.org", 0, "Keep")}
    assert not remaining & dropped


def test_edited_subtree_replaces_chunk_without_duplication(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    chunk_id: Callable[..., str],
) -> None:
    corpus = tmp_path / "corpus"
    source = corpus / "doc.org"
    write_org(source, "About", "Original body.")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {chunk_id(source, 0, "About")}

    write_org(source, "About", "Rewritten body.")

    assert index_corpus(corpus, index_path, embedder) == 1
    rows = VectorStore(index_path, embedder).query("Rewritten")
    assert len(_ids(index_path, embedder)) == 1
    assert rows
    assert "Rewritten body." in rows[0]["text"]


def test_renamed_heading_removes_orphan(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    chunk_id: Callable[..., str],
) -> None:
    corpus = tmp_path / "corpus"
    source = corpus / "doc.org"
    write_org(source, "Old")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {chunk_id(source, 0, "Old")}

    write_org(source, "New")

    assert index_corpus(corpus, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {chunk_id(source, 0, "New")}


def test_empty_corpus_empties_populated_index(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "a.org", "Alpha")
    write_org(corpus / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 2
    assert len(_ids(index_path, embedder)) == 2

    (corpus / "a.org").unlink()
    (corpus / "b.org").unlink()

    assert index_corpus(corpus, index_path, embedder) == 0
    assert _ids(index_path, embedder) == set()


def test_existing_collection_is_reused_without_corruption(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    chunk_id: Callable[..., str],
) -> None:
    first = tmp_path / "first"
    write_org(first / "a.org", "Alpha")
    second = tmp_path / "second"
    write_org(second / "b.org", "Beta")
    index_path = tmp_path / "index"
    first_id = chunk_id(first / "a.org", 0, "Alpha")
    second_id = chunk_id(second / "b.org", 0, "Beta")

    assert index_corpus(first, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {first_id}

    assert index_corpus(second, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {first_id, second_id}

    assert index_corpus(first, index_path, embedder) == 1
    assert _ids(index_path, embedder) == {first_id, second_id}


def test_second_corpus_preserves_first_corpus_chunks(
    tmp_path: Path,
    embedder: Embedder,
    write_org: Callable[..., None],
    chunk_id: Callable[..., str],
) -> None:
    first = tmp_path / "first"
    write_org(first / "a.org", "Alpha")
    write_org(first / "a2.org", "Alpha Two")
    second = tmp_path / "second"
    write_org(second / "b.org", "Beta")
    index_path = tmp_path / "index"

    assert index_corpus(first, index_path, embedder) == 2
    first_ids = _ids(index_path, embedder)
    assert len(first_ids) == 2

    assert index_corpus(second, index_path, embedder) == 1
    assert first_ids <= _ids(index_path, embedder)
    assert chunk_id(second / "b.org", 0, "Beta") in _ids(index_path, embedder)


def test_missing_corpus_root_raises_and_leaves_index_intact(
    tmp_path: Path, embedder: Embedder, write_org: Callable[..., None]
) -> None:
    corpus = tmp_path / "corpus"
    write_org(corpus / "a.org", "Alpha")
    index_path = tmp_path / "index"

    assert index_corpus(corpus, index_path, embedder) == 1
    before = _ids(index_path, embedder)
    assert len(before) == 1

    with pytest.raises(ValueError):
        index_corpus(tmp_path / "missing", index_path, embedder)

    file_root = corpus / "a.org"
    with pytest.raises(ValueError):
        index_corpus(file_root, index_path, embedder)

    assert _ids(index_path, embedder) == before
