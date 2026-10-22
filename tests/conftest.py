"""Shared helpers for the ingestion/store test suite.

These fixtures keep the deterministic, offline stub embedder and the org-file
helpers in one place, so no test file duplicates them and none loads the real
model.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from pathlib import Path

import pytest

from janbot.ingest import read_org_file
from janbot.ingest.scope import located_path

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


def _write_org(path: Path, heading: str = "Heading", body: str = "Body.") -> None:
    """Write a minimal org file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"* {heading}\n{body}\n")


def _chunk_id(path: Path, breadcrumb: str, root: Path) -> str:
    """Reconstruct the expected content-hash id for a chunk independently.

    The chunk's text and breadcrumb come from the reader; the id is rebuilt with
    the documented formula (``{source}::{sha256(source, breadcrumb, text)}``)
    rather than read off a chunk, so a regression in the id construction is
    caught by the assertion. ``source`` is the corpus-root-relative path — the
    id, and the index identity built from it, must not depend on where the
    corpus sits on disk.
    """
    source = located_path(path).relative_to(Path(root).resolve()).as_posix()
    text = next(
        chunk.text
        for chunk in read_org_file(path, root)
        if chunk.breadcrumb == breadcrumb
    )
    digest = hashlib.sha256(f"{source}\n{breadcrumb}\n{text}".encode()).hexdigest()
    return f"{source}::{digest}"


@pytest.fixture
def embedder() -> Callable[[list[str]], list[list[float]]]:
    return _stub_embedder


@pytest.fixture
def write_org() -> Callable[..., None]:
    return _write_org


@pytest.fixture
def chunk_id() -> Callable[..., str]:
    return _chunk_id


@pytest.fixture(autouse=True)
def release_per_test_stores():
    """Close the chroma Systems and mlflow engines a test created.

    Chroma keeps a process-global, refcounted cache of its ``System``
    instances keyed by the persist path, and a ``VectorStore`` opens a
    ``chromadb.PersistentClient`` per instance without closing it. A per-test
    index (a fresh ``tmp_path``) therefore pins its System — sqlite
    connections, HNSW artifacts, telemetry sockets — for the whole run, which
    exhausts the 1024-fd CI limit near the suite's end (measured: 1021/1024
    fds open at session finish, ~11-12 leaked per store-building test, 50
    failures + 10 errors). Releasing exactly the references the test added
    drives each new System to chroma's own last-reference stop
    (``_release_system`` stops and pops it); systems opened *before* the test
    — the shared repo-index system behind ``janbot.api.main``'s module-level
    app, or an index built by an e2e subprocess — keep their references and
    stay open.

    mlflow caches one SQLAlchemy engine per tracking URI (and one store per
    resolved URI); each eval test's tmp ``mlflow.db`` would otherwise keep its
    pooled connections open for the rest of the run, so every engine the test
    created is disposed *and popped*, and the store cache is cleared — a later
    test that reuses a URI therefore gets a fresh store and engine instead of
    reconnecting the disposed one.

    The private cache attributes are read on purpose: if chromadb or mlflow
    changes them, this fixture fails loudly rather than silently
    reintroducing the leak. Measure, never assert: the evidence for this fix
    is the fd-count delta in the plan's Implementation Notes.
    """
    from chromadb.api.client import SharedSystemClient
    from mlflow.store.tracking.sqlalchemy_store import SqlAlchemyStore
    from mlflow.tracking._tracking_service.utils import _tracking_store_registry

    chroma_before = dict(SharedSystemClient._identifier_to_refcount)
    mlflow_before = set(SqlAlchemyStore._engine_map)
    yield
    for identifier, count in list(SharedSystemClient._identifier_to_refcount.items()):
        for _ in range(max(count - chroma_before.get(identifier, 0), 0)):
            SharedSystemClient._release_system(identifier)
    disposed = False
    for uri in list(SqlAlchemyStore._engine_map):
        if uri not in mlflow_before:
            SqlAlchemyStore._engine_map.pop(uri).dispose()
            disposed = True
    if disposed:
        _tracking_store_registry._get_store_with_resolved_uri.cache_clear()
