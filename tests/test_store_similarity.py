"""The store's exposed relevance signal (entry 2, candidate (b)).

``query`` returns each chunk's ``similarity`` — the complement of Chroma's
cosine distance (``1 - distance``), higher meaning more relevant — alongside the
unchanged ``id``/``text``/``source_path``/``breadcrumb`` keys. Both ``dense`` and
``hybrid`` expose it; the hybrid ranking reorders chunks but each keeps the dense
similarity it had in the underlying dense ranking. These tests inject the
deterministic stub embedder from ``conftest`` and compute the expected cosine
similarity independently from the same embedder, so the value is checked, not
just its presence. No model is loaded.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]


class StoredChunk:
    """Chunk-shaped stand-in for direct ``upsert`` at the store boundary."""

    def __init__(self, chunk_id: str, text: str, source_path: Any) -> None:
        self.id = chunk_id
        self.text = text
        self.source_path = source_path
        self.breadcrumb = "Heading"


def _cosine(left: list[float], right: list[float]) -> float:
    """Cosine similarity of two vectors, written independently of the store."""
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _corpus(root: Path) -> list[StoredChunk]:
    return [
        StoredChunk("a", "alpha beta gamma", str(root / "a.org")),
        StoredChunk("b", "beta", str(root / "b.org")),
        StoredChunk("c", "gamma delta", str(root / "c.org")),
    ]


def _expected(query: str, corpus: list[StoredChunk], embedder: Embedder) -> dict[str, float]:
    query_vector = embedder([query])[0]
    vectors = embedder([chunk.text for chunk in corpus])
    return {
        chunk.id: _cosine(query_vector, vector)
        for chunk, vector in zip(corpus, vectors)
    }


def test_dense_query_exposes_cosine_similarity(tmp_path: Path, embedder: Embedder) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    corpus = _corpus(root)
    store = VectorStore(tmp_path / "index", embedder, scope=root)
    store.upsert(corpus)

    rows = store.query("alpha beta", k=3)

    expected = _expected("alpha beta", corpus, embedder)
    assert [row["id"] for row in rows]  # non-empty
    for row in rows:
        assert row["similarity"] == pytest.approx(expected[row["id"]])


def test_dense_similarity_is_ordered_with_the_dense_ranking(
    tmp_path: Path, embedder: Embedder
) -> None:
    """Dense ranks by distance ascending, so the exposed similarity is non-increasing."""
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(tmp_path / "index", embedder, scope=root)
    store.upsert(_corpus(root))

    similarities = [row["similarity"] for row in store.query("alpha beta", k=3)]

    assert similarities == sorted(similarities, reverse=True)


def test_hybrid_exposes_the_underlying_dense_similarity(
    tmp_path: Path, embedder: Embedder
) -> None:
    """The hybrid order differs, but each chunk keeps its dense similarity."""
    root = tmp_path / "corpus"
    root.mkdir()
    corpus = _corpus(root)
    index_path = tmp_path / "index"
    dense = VectorStore(index_path, embedder, scope=root)
    hybrid = VectorStore(index_path, embedder, scope=root, retrieval_mode="hybrid")
    dense.upsert(corpus)

    expected = _expected("alpha beta", corpus, embedder)
    dense_rows = {row["id"]: row["similarity"] for row in dense.query("alpha beta", k=3)}

    for row in hybrid.query("alpha beta", k=3):
        assert row["similarity"] == pytest.approx(expected[row["id"]])
        assert row["similarity"] == dense_rows[row["id"]]


def test_similarity_is_present_at_every_k(tmp_path: Path, embedder: Embedder) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(tmp_path / "index", embedder, scope=root)
    store.upsert(_corpus(root))

    for row in store.query("alpha beta", k=1):
        assert "similarity" in row
