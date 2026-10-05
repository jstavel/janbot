"""ChromaDB vector store adapter with an injectable embedding seam.

The store owns embedding: it computes vectors through the supplied
:data:`Embedder` and passes them explicitly to Chroma's ``upsert``/``query``.
That keeps the real ``all-MiniLM-L6-v2`` model out of tests (a deterministic
stub is injected) and avoids Chroma's embedding-function validation on the
injected callable. Production uses :func:`default_embedder`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import chromadb
from chromadb.utils import embedding_functions

__all__ = ["ChunkLike", "Embedder", "VectorStore", "default_embedder"]

Embedder = Callable[[list[str]], list[list[float]]]


class ChunkLike(Protocol):
    """Structural type for a chunk accepted by the store (avoids ingest dep)."""

    id: str
    text: str
    source_path: str
    breadcrumb: str

_COLLECTION_NAME = "janbot"


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

    def __init__(self, index_path: str | Path, embedder: Embedder) -> None:
        self.index_path = Path(index_path)
        self.embedder = embedder
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

    def delete(self, ids: Iterable[str]) -> None:
        """Delete ``ids`` from the collection (no-op when empty)."""
        id_list = list(ids)
        if not id_list:
            return
        self._collection.delete(ids=id_list)

    def query(self, text: str, k: int = 3) -> list[dict[str, Any]]:
        """Return up to ``k`` chunks most similar to ``text``."""
        result = self._collection.query(
            query_embeddings=self.embedder([text]),
            n_results=k,
            include=["documents", "metadatas"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]

        matches: list[dict[str, Any]] = []
        for chunk_id, document, metadata in zip(ids, documents, metadatas):
            meta = metadata or {}
            matches.append(
                {
                    "id": chunk_id,
                    "text": document,
                    "source_path": meta.get("source_path"),
                    "breadcrumb": meta.get("breadcrumb"),
                }
            )
        return matches
