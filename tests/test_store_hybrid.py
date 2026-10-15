"""Hybrid (dense+lexical) retrieval mode (entry 10, the query-side lever).

The store's default ``dense`` mode is the embedder's cosine similarity alone and
must stay byte-identical to today (the order-asserting tests in
``test_store_scope`` cover that). These tests exercise the opt-in ``hybrid``
mode: a deterministic in-module BM25 lexical ranking fused with the dense
ranking by reciprocal-rank fusion, over the scope-filtered candidate set, with
the return shape and ``k`` truncation unchanged. They inject the deterministic
stub embedder from ``conftest`` — no model is loaded.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from janbot.store import VectorStore

Embedder = Callable[[list[str]], list[list[float]]]

# The fusion spec under test, restated independently of the implementation.
_RRF_K = 60
_K1 = 1.5
_B = 0.75
_TOKEN = re.compile(r"[a-z0-9]+")


class StoredChunk:
    """Chunk-shaped stand-in for direct ``upsert`` at the store boundary."""

    def __init__(self, chunk_id: str, text: str, source_path: Any) -> None:
        self.id = chunk_id
        self.text = text
        self.source_path = source_path
        self.breadcrumb = "Heading"


def _corpus(root: Path) -> list[StoredChunk]:
    """A tie-free corpus whose dense and lexical rankings provably disagree.

    Every chunk has a distinct cosine distance to the query, so the dense order
    is deterministic and independent of tie-breaking. Dense ranks ``d1`` (the
    rare ``beta`` chunk) last; BM25 ranks it second, so the fusion lifts it into
    the window while the dense ranking excludes it.
    """
    return [
        StoredChunk("d6", "alpha beta gamma", str(root / "d6.org")),
        StoredChunk("d2", "alpha", str(root / "d2.org")),
        StoredChunk("d4", "alpha delta", str(root / "d4.org")),
        StoredChunk("d1", "beta epsilon zeta tau upsilon", str(root / "d1.org")),
        StoredChunk("d3", "alpha theta iota", str(root / "d3.org")),
        StoredChunk("d5", "alpha mu nu xi", str(root / "d5.org")),
    ]


def _reference_lexical_order(query: str, documents: list[str]) -> list[int]:
    """An independent BM25 ranking, written from the spec (not the module)."""
    tokens = [_TOKEN.findall(document.lower()) for document in documents]
    total = len(tokens)
    average_length = sum(len(entry) for entry in tokens) / total
    document_frequency: dict[str, int] = {}
    for entry in tokens:
        for term in set(entry):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    scores = [0.0] * total
    for term in _TOKEN.findall(query.lower()):
        frequency = document_frequency.get(term, 0)
        if frequency == 0:
            continue
        idf = math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
        for index, entry in enumerate(tokens):
            tf = entry.count(term)
            if tf == 0:
                continue
            denom = tf + _K1 * (
                1 - _B + _B * (len(entry) / average_length if average_length else 0)
            )
            scores[index] += idf * (tf * (_K1 + 1) / denom)
    return sorted(range(total), key=lambda index: (-scores[index], index))


def _reference_fusion_order(dense_ids: list[str], lexical_ids: list[str]) -> list[str]:
    """RRF of two id rankings, restated from the spec."""
    fused = {chunk_id: 0.0 for chunk_id in dense_ids}
    for rank, chunk_id in enumerate(dense_ids, start=1):
        fused[chunk_id] += 1.0 / (_RRF_K + rank)
    for rank, chunk_id in enumerate(lexical_ids, start=1):
        fused[chunk_id] += 1.0 / (_RRF_K + rank)
    return sorted(dense_ids, key=lambda chunk_id: -fused[chunk_id])


def test_hybrid_return_shape_is_unchanged(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert(_corpus(root))

    rows = store.query("alpha beta", k=3)

    assert len(rows) == 3
    for row in rows:
        assert set(row) == {"id", "text", "source_path", "breadcrumb"}
        assert row["source_path"] is not None


def test_hybrid_fuses_dense_and_lexical_rankings(
    tmp_path: Path, embedder: Embedder
) -> None:
    """The hybrid order equals an independent RRF of the dense and BM25 rankings."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    dense = VectorStore(index_path, embedder, scope=root)
    hybrid = VectorStore(index_path, embedder, scope=root, retrieval_mode="hybrid")
    corpus = _corpus(root)
    dense.upsert(corpus)

    query = "alpha beta"
    dense_ids = [row["id"] for row in dense.query(query, k=6)]
    lexical_ids = [
        corpus[index].id
        for index in _reference_lexical_order(
            query, [chunk.text for chunk in corpus]
        )
    ]
    expected = _reference_fusion_order(dense_ids, lexical_ids)

    hybrid_ids = [row["id"] for row in hybrid.query(query, k=6)]

    assert hybrid_ids == expected
    assert hybrid_ids != dense_ids


def test_hybrid_golden_pinned_order(tmp_path: Path, embedder: Embedder) -> None:
    """A pinned golden order on a tiny fixed corpus.

    The literal expected order catches any drift in the BM25/RRF maths. The
    reference implementation above cannot do this: it mirrors the production
    formula, so it would drift with it. Full independence would need a second,
    independently written retrieval implementation (or a second BM25 library),
    which the no-new-dependency boundary for this story excludes.
    """
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    corpus = [
        StoredChunk("p1", "alpha beta gamma", str(root / "p1.org")),
        StoredChunk("p2", "alpha", str(root / "p2.org")),
        StoredChunk("p3", "beta epsilon zeta", str(root / "p3.org")),
        StoredChunk("p4", "alpha delta", str(root / "p4.org")),
    ]
    dense = VectorStore(index_path, embedder, scope=root)
    hybrid = VectorStore(index_path, embedder, scope=root, retrieval_mode="hybrid")
    dense.upsert(corpus)

    dense_ids = [row["id"] for row in dense.query("alpha beta", k=4)]
    hybrid_ids = [row["id"] for row in hybrid.query("alpha beta", k=4)]

    assert dense_ids == ["p1", "p2", "p4", "p3"]
    assert hybrid_ids == ["p1", "p2", "p3", "p4"]


def test_hybrid_is_deterministic_across_two_calls(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert(_corpus(root))

    first = store.query("alpha beta", k=4)
    second = store.query("alpha beta", k=4)

    assert first == second


def test_hybrid_truncates_to_k(tmp_path: Path, embedder: Embedder) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert(_corpus(root))

    full = store.query("alpha beta", k=6)
    truncated = store.query("alpha beta", k=2)

    assert len(full) == 6
    assert truncated == full[:2]


def test_hybrid_k_zero_returns_empty(tmp_path: Path, embedder: Embedder) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert(_corpus(root))

    assert store.query("alpha beta", k=0) == []


def test_hybrid_scope_filter_precedes_truncation(
    tmp_path: Path, embedder: Embedder
) -> None:
    """An out-of-scope chunk that ranks lexically cannot enter the hybrid window."""
    root = tmp_path / "corpus"
    root.mkdir()
    foreign = tmp_path / "elsewhere" / "secret.org"
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert(
        [
            StoredChunk("public::0::H", "alpha beta", str(root / "a.org")),
            StoredChunk("foreign::0::H", "alpha beta", str(foreign)),
        ]
    )

    rows = store.query("alpha beta", k=3)

    assert [row["id"] for row in rows] == ["public::0::H"]
    assert all(Path(row["source_path"]).is_relative_to(root) for row in rows)


def test_hybrid_scoped_store_with_only_out_of_scope_chunks_returns_empty(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    store = VectorStore(
        tmp_path / "index", embedder, scope=root, retrieval_mode="hybrid"
    )
    store.upsert([StoredChunk("foreign::0::H", "alpha beta", str(tmp_path / "x.org"))])

    assert store.query("alpha beta", k=3) == []


def test_hybrid_unscoped_store_overfetches_to_fuse(
    tmp_path: Path, embedder: Embedder
) -> None:
    """The unscoped path over-fetches, so a lexically-strong doc can enter the window.

    With ``k=4`` the dense ranking alone never reaches ``d1`` (the rare "beta"
    chunk, dense rank 6); the fused ranking lifts it to rank 4 and returns it.
    """
    index_path = tmp_path / "index"
    dense = VectorStore(index_path, embedder)
    hybrid = VectorStore(index_path, embedder, retrieval_mode="hybrid")
    dense.upsert(_corpus(tmp_path))

    dense_ids = [row["id"] for row in dense.query("alpha beta", k=4)]
    hybrid_ids = [row["id"] for row in hybrid.query("alpha beta", k=4)]

    assert "d1" not in dense_ids
    assert "d1" in hybrid_ids


def test_default_mode_is_dense_and_matches_explicit_dense(
    tmp_path: Path, embedder: Embedder
) -> None:
    """No knob -> the default store is byte-identical to an explicit dense store."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    default = VectorStore(index_path, embedder, scope=root)
    explicit = VectorStore(index_path, embedder, scope=root, retrieval_mode="dense")
    default.upsert(_corpus(root))

    assert default.retrieval_mode == "dense"
    assert default.query("alpha beta", k=4) == explicit.query("alpha beta", k=4)


@pytest.mark.parametrize("value", ["bogus", "lexical", "Dense"])
def test_invalid_retrieval_mode_rejected(
    tmp_path: Path, embedder: Embedder, value: str
) -> None:
    with pytest.raises(ValueError) as excinfo:
        VectorStore(tmp_path / "index", embedder, retrieval_mode=value)

    message = str(excinfo.value)
    assert value in message
    assert "dense" in message
    assert "hybrid" in message
