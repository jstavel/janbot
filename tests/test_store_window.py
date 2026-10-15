"""Source-diverse retrieval window (entry 11, the breadth-vs-depth lever).

The store's default ``chunks`` window returns the top-``k`` ranked chunks and
must stay byte-identical to today (the order-asserting tests cover that). These
tests exercise the opt-in ``sources`` window: up to ``k`` **distinct** sources,
each represented by its best-ranked chunk, selected after the fail-closed scope
filter. They compose with both retrieval modes (``dense`` and ``hybrid``) and
inject the deterministic stub embedder from ``conftest`` — no model is loaded.
"""

from __future__ import annotations

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


def _corpus(root: Path) -> list[StoredChunk]:
    """A source-duplicating corpus whose dense order is deterministic.

    ``x.org`` contributes two chunks (``x1`` best, ``x2`` later); ``z.org``,
    ``y.org`` and ``w.org`` one each. Querying ``"alpha"`` against the stub
    bag-of-words embedder orders them ``x1, z1, x2, y1, w1`` — so the top-3
    chunks hold only two distinct sources (a duplicate crowds out ``y.org``),
    while the top-3 distinct sources are ``x1, z1, y1``.
    """
    return [
        StoredChunk("x1", "alpha", str(root / "x.org")),
        StoredChunk("x2", "alpha alpha alpha beta", str(root / "x.org")),
        StoredChunk("z1", "alpha alpha alpha alpha beta", str(root / "z.org")),
        StoredChunk("y1", "alpha alpha beta", str(root / "y.org")),
        StoredChunk("w1", "alpha alpha beta beta", str(root / "w.org")),
    ]


def _dedup_sources(rows: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
    """First-seen chunk per source, capped at ``k`` distinct sources."""
    selected: list[dict[str, Any]] = []
    seen: set[Any] = set()
    for row in rows:
        if row["source_path"] in seen:
            continue
        seen.add(row["source_path"])
        selected.append(row)
        if len(selected) == k:
            break
    return selected


def _store(
    index_path: Path,
    embedder: Embedder,
    root: Path | None,
    *,
    mode: str = "dense",
    window: str = "chunks",
) -> VectorStore:
    return VectorStore(
        index_path,
        embedder,
        scope=root,
        retrieval_mode=mode,
        retrieval_window=window,
    )


def test_default_window_is_chunks_and_matches_explicit_chunks(
    tmp_path: Path, embedder: Embedder
) -> None:
    """No knob -> the default store is byte-identical to an explicit chunks store."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    default = _store(index_path, embedder, root)
    explicit = _store(index_path, embedder, root, window="chunks")
    default.upsert(_corpus(root))

    assert default.retrieval_window == "chunks"
    assert default.query("alpha", k=4) == explicit.query("alpha", k=4)


def test_dense_sources_window_selects_distinct_sources(
    tmp_path: Path, embedder: Embedder
) -> None:
    """A pinned dense order: chunks duplicate ``x.org``; sources replace the repeat."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    chunks = _store(index_path, embedder, root, window="chunks")
    sources = _store(index_path, embedder, root, window="sources")
    chunks.upsert(_corpus(root))

    assert [row["id"] for row in chunks.query("alpha", k=3)] == ["x1", "z1", "x2"]
    assert [row["id"] for row in sources.query("alpha", k=3)] == ["x1", "z1", "y1"]


def test_sources_window_matches_dedup_of_chunks_order(
    tmp_path: Path, embedder: Embedder
) -> None:
    """For both modes, sources is the first-seen-per-source dedup of the ranked chunks."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    corpus = _corpus(root)
    for mode in ("dense", "hybrid"):
        chunks = _store(index_path, embedder, root, mode=mode, window="chunks")
        sources = _store(index_path, embedder, root, mode=mode, window="sources")
        chunks.upsert(corpus)

        ranked = chunks.query("alpha", k=len(corpus))
        expected = _dedup_sources(ranked, 3)
        assert sources.query("alpha", k=3) == expected


def test_sources_window_k_is_k_distinct_sources(
    tmp_path: Path, embedder: Embedder
) -> None:
    """``k`` counts distinct sources, not chunks."""
    root = tmp_path / "corpus"
    root.mkdir()
    store = _store(tmp_path / "index", embedder, root, window="sources")
    store.upsert(_corpus(root))

    rows = store.query("alpha", k=3)

    assert len(rows) == 3
    assert len({row["source_path"] for row in rows}) == 3


def test_sources_window_scope_filter_precedes_selection(
    tmp_path: Path, embedder: Embedder
) -> None:
    """An out-of-scope chunk cannot consume a distinct-source slot."""
    root = tmp_path / "corpus"
    root.mkdir()
    foreign = tmp_path / "elsewhere" / "secret.org"
    store = _store(tmp_path / "index", embedder, root, window="sources")
    store.upsert(
        [
            StoredChunk("x1", "alpha", str(root / "x.org")),
            StoredChunk("f1", "alpha alpha alpha alpha alpha beta", str(foreign)),
            StoredChunk("x2", "alpha alpha alpha beta", str(root / "x.org")),
            StoredChunk("y1", "alpha alpha beta", str(root / "y.org")),
        ]
    )

    rows = store.query("alpha", k=2)

    assert [row["id"] for row in rows] == ["x1", "y1"]
    assert all(Path(row["source_path"]).is_relative_to(root) for row in rows)


def test_unscoped_sources_window_fewer_distinct_than_k(
    tmp_path: Path, embedder: Embedder
) -> None:
    """When fewer distinct sources exist than ``k``, all are returned (fewer than k)."""
    root = tmp_path / "corpus"
    root.mkdir()
    store = _store(tmp_path / "index", embedder, root=None, window="sources")
    store.upsert(_corpus(root))

    rows = store.query("alpha", k=10)

    assert len(rows) == 4
    assert len({row["source_path"] for row in rows}) == 4
    assert [row["id"] for row in rows] == ["x1", "z1", "y1", "w1"]


def test_unscoped_sources_window_degradation_returns_fewer(
    tmp_path: Path, embedder: Embedder
) -> None:
    """Documented degradation: an unscoped dense store fetches only ``k`` candidates.

    With ``k=2`` the two fetched candidates are both ``a.org`` chunks, so the
    distinct-source window holds a single source — it cannot recover a source
    that was never fetched. The unscoped dense path is deliberately not changed
    to over-fetch.
    """
    root = tmp_path / "corpus"
    root.mkdir()
    store = _store(tmp_path / "index", embedder, root=None, window="sources")
    store.upsert(
        [
            StoredChunk("a1", "alpha", str(root / "a.org")),
            StoredChunk("a2", "alpha alpha alpha beta", str(root / "a.org")),
            StoredChunk("b1", "alpha alpha beta", str(root / "b.org")),
            StoredChunk("c1", "alpha alpha beta beta", str(root / "c.org")),
        ]
    )

    rows = store.query("alpha", k=2)

    assert [row["id"] for row in rows] == ["a1"]


def test_unscoped_sources_window_keeps_fetched_sourceless_chunks(
    tmp_path: Path, embedder: Embedder
) -> None:
    """Sourceless chunks are each their own unit; the sources window does not collapse them."""
    store = _store(tmp_path / "index", embedder, root=None, window="sources")
    store.upsert(
        [
            StoredChunk("s1", "needle alpha", None),
            StoredChunk("s2", "needle beta", None),
            StoredChunk("s3", "needle gamma", None),
        ]
    )

    rows = store.query("needle", k=3)

    assert len(rows) == 3
    assert {row["id"] for row in rows} == {"s1", "s2", "s3"}


def test_sources_window_is_deterministic_across_two_calls(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    for mode in ("dense", "hybrid"):
        store = _store(tmp_path / "index", embedder, root, mode=mode, window="sources")
        store.upsert(_corpus(root))

        assert store.query("alpha", k=3) == store.query("alpha", k=3)


@pytest.mark.parametrize("mode", ["dense", "hybrid"])
@pytest.mark.parametrize("window", ["chunks", "sources"])
def test_window_invariant_across_both_modes(
    tmp_path: Path, embedder: Embedder, mode: str, window: str
) -> None:
    """Every mode x window keeps the documented window invariant."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    corpus = _corpus(root)
    chunks = _store(index_path, embedder, root, mode=mode, window="chunks")
    windowed = _store(index_path, embedder, root, mode=mode, window=window)
    chunks.upsert(corpus)

    ranked = chunks.query("alpha", k=len(corpus))
    rows = windowed.query("alpha", k=3)

    if window == "chunks":
        assert rows == ranked[:3]
    else:
        assert rows == _dedup_sources(ranked, 3)
        assert len({row["source_path"] for row in rows}) == len(rows)


@pytest.mark.parametrize("value", ["bogus", "chunk", "source", "Chunks"])
def test_invalid_retrieval_window_rejected(
    tmp_path: Path, embedder: Embedder, value: str
) -> None:
    with pytest.raises(ValueError) as excinfo:
        VectorStore(tmp_path / "index", embedder, retrieval_window=value)

    message = str(excinfo.value)
    assert value in message
    assert "chunks" in message
    assert "sources" in message
