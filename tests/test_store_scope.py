"""Store-boundary corpus scope (CAP-1 / epic Done-when 5).

Retrieval is scoped to the corpus root at the store: a scoped ``query`` returns
only chunks *located* within the scope, excluding an out-of-scope or sourceless
chunk even when it ranks highest, while an unscoped store keeps today's global
top-k. These tests inject the deterministic stub embedder from ``conftest``.
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


def _scoped_store(index_path: Path, embedder: Embedder, scope: Path) -> VectorStore:
    return VectorStore(index_path, embedder, scope=scope)


def test_unscoped_store_returns_global_top_k(
    tmp_path: Path, embedder: Embedder
) -> None:
    """No scope set: an out-of-scope chunk still ranks and is returned."""
    root = tmp_path / "corpus"
    root.mkdir()
    foreign_source = tmp_path / "elsewhere" / "secret.org"
    index_path = tmp_path / "index"

    store = VectorStore(index_path, embedder)
    store.upsert(
        [
            StoredChunk("public::0::H", "gamma delta", str(root / "a.org")),
            StoredChunk("foreign::0::H", "needle", str(foreign_source)),
        ]
    )

    rows = store.query("needle", k=1)

    assert [row["id"] for row in rows] == ["foreign::0::H"]


def test_scoped_store_excludes_out_of_scope_chunk_that_ranks_highest(
    tmp_path: Path, embedder: Embedder
) -> None:
    """The out-of-scope chunk ranks first but is filtered; the public chunk is returned."""
    root = tmp_path / "corpus"
    root.mkdir()
    foreign_source = tmp_path / "elsewhere" / "secret.org"
    public_source = str(root / "a.org")
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert(
        [
            StoredChunk("public::0::H", "gamma delta", public_source),
            StoredChunk("foreign::0::H", "needle", str(foreign_source)),
        ]
    )

    rows = store.query("needle", k=3)

    assert [row["id"] for row in rows] == ["public::0::H"]
    assert all(row["source_path"] == public_source for row in rows)


def test_scoped_store_with_only_out_of_scope_chunks_returns_empty(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert(
        [StoredChunk("foreign::0::H", "needle", str(tmp_path / "elsewhere" / "x.org"))]
    )

    assert store.query("needle", k=3) == []


def test_scoped_store_excludes_chunk_without_source_path(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert([StoredChunk("sourceless::0::H", "needle", None)])

    assert store.query("needle", k=3) == []


def test_scoped_store_excludes_non_string_source_path(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert([StoredChunk("unjudgeable::0::H", "needle", 123)])

    assert store.query("needle", k=3) == []


def test_scoped_store_query_k_zero_returns_empty(
    tmp_path: Path, embedder: Embedder
) -> None:
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert([StoredChunk("public::0::H", "needle", str(root / "a.org"))])

    assert store.query("needle", k=0) == []


def test_scoped_store_truncates_to_k_within_scope(
    tmp_path: Path, embedder: Embedder
) -> None:
    """Filtering happens before truncation, so k in-scope chunks are returned."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert(
        [
            StoredChunk("foreign::0::H", "needle", str(tmp_path / "elsewhere" / "x.org")),
            StoredChunk("public::0::H", "needle", str(root / "a.org")),
            StoredChunk("public::1::H", "needle", str(root / "b.org")),
        ]
    )

    rows = store.query("needle", k=2)

    assert len(rows) == 2
    assert all(Path(row["source_path"]).is_relative_to(root) for row in rows)


def test_scoped_store_excludes_relative_source_path(
    tmp_path: Path,
    embedder: Embedder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A relative ``source_path`` is excluded, matching the rewriter's refusal — no CWD dependence.

    The process CWD is set to the corpus root, so a relative path would resolve
    *inside* it under the old ``abspath`` behaviour; the guard must still exclude it.
    """
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"
    monkeypatch.chdir(root)

    store = _scoped_store(index_path, embedder, root)
    store.upsert([StoredChunk("rel::0::H", "needle", str(root / "a.org"))])
    store.upsert([StoredChunk("rel::1::H", "needle", "a.org")])

    rows = store.query("needle", k=3)

    assert [row["id"] for row in rows] == ["rel::0::H"]


def test_scoped_store_excludes_dotdot_source_path(
    tmp_path: Path, embedder: Embedder
) -> None:
    """A ``..`` in a ``source_path`` is excluded (fail-closed)."""
    root = tmp_path / "corpus"
    root.mkdir()
    index_path = tmp_path / "index"

    store = _scoped_store(index_path, embedder, root)
    store.upsert([StoredChunk("in::0::H", "needle", str(root / "a.org"))])
    store.upsert([StoredChunk("dd::1::H", "needle", str(root / ".." / "elsewhere" / "x.org"))])

    rows = store.query("needle", k=3)

    assert [row["id"] for row in rows] == ["in::0::H"]
