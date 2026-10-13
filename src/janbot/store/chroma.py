"""ChromaDB vector store adapter with an injectable embedding seam.

The store owns embedding: it computes vectors through the supplied
:data:`Embedder` and passes them explicitly to Chroma's ``upsert``/``query``.
That keeps the real ``all-MiniLM-L6-v2`` model out of tests (a deterministic
stub is injected) and avoids Chroma's embedding-function validation on the
injected callable. Production uses :func:`default_embedder`.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import chromadb
from chromadb.utils import embedding_functions

__all__ = ["ChunkLike", "Embedder", "VectorStore", "default_embedder"]

Embedder = Callable[[list[str]], list[list[float]]]


class ChunkLike(Protocol):
    """Structural type for a chunk accepted by the store (avoids ingest dep)."""

    @property
    def id(self) -> str: ...

    @property
    def text(self) -> str: ...

    @property
    def source_path(self) -> str: ...

    @property
    def breadcrumb(self) -> str: ...

_COLLECTION_NAME = "janbot"


def _within_scope(scope: Path, source_path: str | None) -> bool:
    """Return ``True`` only when ``source_path`` is *located* inside ``scope``.

    Mirrors :func:`janbot.ingest.scope.within` for an already-resolved root,
    without importing it (``janbot.ingest`` imports ``janbot.store``; that import
    would be circular). The containing directory is resolved while the final
    component is left intact, so containment is judged by where a path sits.
    Fail-closed: a missing or unjudgeable path returns ``False``.
    """
    if not isinstance(source_path, str) or not source_path:
        return False
    if ".." in Path(source_path).parts:
        return False
    try:
        absolute = Path(os.path.abspath(source_path))
        located = absolute.parent.resolve() / absolute.name
    except (OSError, RuntimeError, TypeError):
        return False
    return located == scope or located.is_relative_to(scope)


def default_embedder() -> Embedder:
    """Return the production embedder backed by Chroma's default model.

    Chroma's embedding function yields numpy arrays; the seam contract is plain
    ``list[list[float]]``.
    """
    function = embedding_functions.DefaultEmbeddingFunction()

    def embed(texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in function(texts)]

    return embed


class VectorStore:
    """A persistent ChromaDB collection written and queried via ``embedder``."""

    def __init__(
        self,
        index_path: str | Path,
        embedder: Embedder,
        scope: str | Path | None = None,
    ) -> None:
        self.index_path = Path(index_path)
        self.embedder = embedder
        self.scope = Path(scope).resolve() if scope is not None else None
        self._client = chromadb.PersistentClient(path=str(self.index_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, chunks: Iterable[ChunkLike]) -> None:
        """Embed and store ``chunks`` by their stable ids (no-op when empty)."""
        chunk_list = list(chunks)
        if not chunk_list:
            return

        documents = [chunk.text for chunk in chunk_list]
        self._collection.upsert(
            ids=[chunk.id for chunk in chunk_list],
            documents=documents,
            metadatas=[
                {
                    "source_path": chunk.source_path,
                    "breadcrumb": chunk.breadcrumb,
                }
                for chunk in chunk_list
            ],
            embeddings=self.embedder(documents),
        )

    def ids(self) -> set[str]:
        """Return the ids of every chunk currently stored."""
        result = self._collection.get(include=[])
        return set(result.get("ids") or [])

    def sources(self) -> dict[str, str]:
        """Return a mapping of stored chunk id to its source path."""
        result = self._collection.get(include=["metadatas"])
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        sources: dict[str, str] = {}
        for chunk_id, metadata in zip(ids, metadatas):
            source = (metadata or {}).get("source_path")
            if source is not None:
                sources[chunk_id] = source
        return sources

    def payload(self) -> dict[str, tuple[str, tuple[float, ...]]]:
        """Return each stored chunk id mapped to its (document, embedding) payload.

        The embedding is normalized to a tuple of floats so payloads are
        comparable and hashable; a re-run that corrupts either half of a
        payload while keeping ids stable is therefore detectable.
        """
        result = self._collection.get(include=["documents", "embeddings"])
        ids = result.get("ids") or []
        documents = result.get("documents") or []
        embeddings = result.get("embeddings")
        if embeddings is None:
            embeddings = []
        return {
            chunk_id: (
                document or "",
                tuple(float(value) for value in vector)
                if vector is not None
                else (),
            )
            for chunk_id, document, vector in zip(ids, documents, embeddings)
        }

    def delete(self, ids: Iterable[str]) -> None:
        """Delete ``ids`` from the collection (no-op when empty)."""
        id_list = list(ids)
        if not id_list:
            return
        self._collection.delete(ids=id_list)

    def query(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        """Return up to ``k`` chunks most similar to ``text``.

        When the store is scoped, only chunks *located* within ``self.scope`` can
        be returned: ranked candidates are over-fetched (every stored chunk) and
        filtered to scope before truncating to ``k``, so an out-of-scope chunk
        can never enter retrieval. An unscoped store is the global top-``k``.
        """
        if k <= 0:
            return []

        if self.scope is not None:
            count = self._collection.count()
            if count == 0:
                return []
            n_results = count
        else:
            n_results = k

        result = self._collection.query(
            query_embeddings=self.embedder([text]),
            n_results=n_results,
            include=["documents", "metadatas"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        matches: list[dict[str, Any]] = []
        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            meta = metadata or {}
            source_path = meta.get("source_path")
            if self.scope is not None and not _within_scope(self.scope, source_path):
                continue
            matches.append(
                {
                    "id": chunk_id,
                    "text": document,
                    "source_path": source_path,
                    "breadcrumb": meta.get("breadcrumb"),
                }
            )
            if len(matches) == k:
                break
        return matches
