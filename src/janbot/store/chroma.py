"""ChromaDB vector store adapter with an injectable embedding seam.

The store owns embedding: it computes vectors through the supplied
:data:`Embedder` and passes them explicitly to Chroma's ``upsert``/``query``.
That keeps the real ``all-MiniLM-L6-v2`` model out of tests (a deterministic
stub is injected) and avoids Chroma's embedding-function validation on the
injected callable. Production uses :func:`default_embedder`.
"""

from __future__ import annotations

import math
import os
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

import chromadb
from chromadb.utils import embedding_functions

from janbot.config import (
    DEFAULT_RETRIEVAL_MODE,
    DEFAULT_RETRIEVAL_WINDOW,
    RETRIEVAL_MODE_HYBRID,
    RETRIEVAL_MODES,
    RETRIEVAL_WINDOW_SOURCES,
    RETRIEVAL_WINDOWS,
)

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

_BM25_K1 = 1.5
_BM25_B = 0.75
_RRF_K = 60

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    """Lower-case runs of ``[a-z0-9]+`` — the fixed BM25 tokenizer (no stemming)."""
    return _TOKEN_RE.findall(text.lower())


def _bm25_scores(query: str, documents: list[str]) -> list[float]:
    """Deterministic Okapi BM25 score for ``query`` against each document.

    Fixed parameters (``k1``/``b``) and the fixed :func:`_tokenize` tokenizer, so
    the lexical ranking is reproducible by specification, not by accident.
    """
    tokenized = [_tokenize(document) for document in documents]
    total = len(tokenized)
    if total == 0:
        return []
    average_length = sum(len(tokens) for tokens in tokenized) / total
    document_frequency: dict[str, int] = {}
    for tokens in tokenized:
        for term in set(tokens):
            document_frequency[term] = document_frequency.get(term, 0) + 1
    scores = [0.0] * total
    for term in _tokenize(query):
        frequency = document_frequency.get(term, 0)
        if frequency == 0:
            continue
        idf = math.log(1 + (total - frequency + 0.5) / (frequency + 0.5))
        for index, tokens in enumerate(tokenized):
            term_frequency = tokens.count(term)
            if term_frequency == 0:
                continue
            length_ratio = (len(tokens) / average_length) if average_length else 0.0
            denominator = term_frequency + _BM25_K1 * (
                1 - _BM25_B + _BM25_B * length_ratio
            )
            scores[index] += idf * (term_frequency * (_BM25_K1 + 1) / denominator)
    return scores


def _reciprocal_rank_fusion(
    dense_order: list[int], lexical_order: list[int], size: int
) -> list[float]:
    """Fuse two rankings of ``size`` items by reciprocal-rank fusion.

    Each ranking contributes ``1 / (_RRF_K + rank)`` (rank is 1-based) to the
    item at that position; the fused scores decide the final order. Fixed
    constant, so the fusion is deterministic.
    """
    scores = [0.0] * size
    for rank, index in enumerate(dense_order, start=1):
        scores[index] += 1.0 / (_RRF_K + rank)
    for rank, index in enumerate(lexical_order, start=1):
        scores[index] += 1.0 / (_RRF_K + rank)
    return scores



def _similarity(distance: Any) -> float:
    """Return the cosine similarity for a Chroma cosine-distance value.

    The collection is created with ``hnsw:space="cosine"``, so Chroma reports
    ``1 - cosine similarity``; the exposed relevance score is its complement
    (higher is more relevant).
    """
    return 1.0 - float(distance)


def _within_scope(scope: Path, source_path: str | None) -> bool:
    """Return ``True`` only when ``source_path`` is *located* inside ``scope``.

    Containment is judged by the *located* path, like the citation rewriter
    (:func:`janbot.pipeline.chat.corpus_relative`), so the retrieval and citation
    guards agree; it does not import ``janbot.ingest.scope`` (that import would
    be circular: ``janbot.ingest`` imports ``janbot.store``), and it is stricter
    than ``janbot.ingest.scope.within``, which does not require an absolute path.
    The containing directory is resolved while the final component is left
    intact, so containment is judged by where a path sits.
    Fail-closed: a missing, non-string, **non-absolute**, or unjudgeable path
    returns ``False`` (a relative path's meaning would depend on the process
    CWD, which the citation rewriter — which refuses relative paths — would
    disagree with).
    """
    if not isinstance(source_path, str) or not source_path:
        return False
    if not Path(source_path).is_absolute():
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
    from janbot.store.embedding_model import assert_model_pin

    assert_model_pin()
    function = embedding_functions.DefaultEmbeddingFunction()

    def embed(texts: list[str]) -> list[list[float]]:
        return [[float(value) for value in vector] for vector in function(texts)]

    return embed


def _chunk_metadata(
    chunk: ChunkLike, *, scope_key: str | None = None
) -> dict[str, str]:
    """Build the metadata written for a chunk.

    ``scope_key`` is included only when provided, so a chunk stored without one
    simply cannot be attributed to a corpus (Chroma silently drops ``None``
    metadata values, which would lose that distinction anyway).
    """
    metadata = {
        "source_path": chunk.source_path,
        "breadcrumb": chunk.breadcrumb,
    }
    if scope_key is not None:
        metadata["scope_key"] = scope_key
    return metadata


class VectorStore:
    """A persistent ChromaDB collection written and queried via ``embedder``."""

    def __init__(
        self,
        index_path: str | Path,
        embedder: Embedder,
        scope: str | Path | None = None,
        retrieval_mode: str = DEFAULT_RETRIEVAL_MODE,
        retrieval_window: str = DEFAULT_RETRIEVAL_WINDOW,
    ) -> None:
        self.index_path = Path(index_path)
        self.embedder = embedder
        self.scope = Path(scope).resolve() if scope is not None else None
        if retrieval_mode not in RETRIEVAL_MODES:
            allowed = ", ".join(repr(mode) for mode in RETRIEVAL_MODES)
            raise ValueError(
                f"retrieval_mode={retrieval_mode!r} is invalid; "
                f"allowed values: {allowed}"
            )
        self.retrieval_mode = retrieval_mode
        if retrieval_window not in RETRIEVAL_WINDOWS:
            allowed = ", ".join(repr(window) for window in RETRIEVAL_WINDOWS)
            raise ValueError(
                f"retrieval_window={retrieval_window!r} is invalid; "
                f"allowed values: {allowed}"
            )
        self.retrieval_window = retrieval_window
        self._client = chromadb.PersistentClient(path=str(self.index_path))
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def _window(self, ranked: list[dict[str, Any]], k: int) -> list[dict[str, Any]]:
        """Select the retrieval window of up to ``k`` chunks from ``ranked``.

        With the default ``chunks`` window this is the top-``k`` ranked chunks.
        With the ``sources`` window it is the top-``k`` **distinct** sources,
        keeping each source's best-ranked (first-seen) chunk: the walk skips a
        chunk whose source is already selected and stops once ``k`` distinct
        sources are held. Scope filtering already happened upstream, so only
        in-scope chunks are ever selected.
        """
        if self.retrieval_window != RETRIEVAL_WINDOW_SOURCES:
            return ranked[:k]
        selected: list[dict[str, Any]] = []
        seen: set[Any] = set()
        for chunk in ranked:
            source = chunk["source_path"]
            key = source if source is not None else chunk["id"]
            if key in seen:
                continue
            seen.add(key)
            selected.append(chunk)
            if len(selected) == k:
                break
        return selected

    def upsert(
        self, chunks: Iterable[ChunkLike], *, scope_key: str | None = None
    ) -> None:
        """Embed and store ``chunks`` by their stable ids (no-op when empty).

        When ``scope_key`` is given it is recorded in every chunk's metadata, so
        the corpus a chunk belongs to is stored with the chunk rather than
        re-derived from its ``source_path``. The keyword is optional so existing
        direct-upsert callers (tests) keep working unchanged.
        """
        chunk_list = list(chunks)
        if not chunk_list:
            return

        documents = [chunk.text for chunk in chunk_list]
        self._collection.upsert(
            ids=[chunk.id for chunk in chunk_list],
            documents=documents,
            metadatas=[
                _chunk_metadata(chunk, scope_key=scope_key) for chunk in chunk_list
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

    def scope_keys(self) -> dict[str, str]:
        """Return a mapping of stored chunk id to its recorded scope key.

        The scope key is the resolved corpus root recorded at upsert, so this is
        the stored ownership the reconcile deletes by. Chunks stored without a
        scope key are omitted: they cannot be attributed to a corpus.
        """
        result = self._collection.get(include=["metadatas"])
        ids = result.get("ids") or []
        metadatas = result.get("metadatas") or []
        scopes: dict[str, str] = {}
        for chunk_id, metadata in zip(ids, metadatas):
            scope_key = (metadata or {}).get("scope_key")
            if scope_key is not None:
                scopes[chunk_id] = scope_key
        return scopes

    def out_of_scope_sources(self) -> dict[str, str]:
        """Return stored chunks whose ``source_path`` lies outside ``scope``.

        Empty when the store is unscoped. Used at startup to surface an index
        built from a corpus root other than the one being served.
        """
        if self.scope is None:
            return {}
        return {
            chunk_id: source
            for chunk_id, source in self.sources().items()
            if not _within_scope(self.scope, source)
        }

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

        In the default ``dense`` mode the ranking is the embedder's cosine
        similarity alone. In ``hybrid`` mode the same dense ranking is fused with
        a deterministic BM25 lexical ranking of the candidate texts by
        reciprocal-rank fusion; both modes share the scope filter, the return
        shape and the ``k`` truncation.

        Every returned chunk carries a ``similarity`` key: the collection is a
        cosine space, so Chroma's distance is ``1 - cosine similarity`` and the
        exposed score is ``1 - distance`` (higher is more relevant). The
        ``hybrid`` ranking reorders the chunks, but each chunk keeps the dense
        similarity it had in the underlying dense ranking.

        The window selected from the ranking is ``chunks`` by default (the top
        ``k`` ranked chunks). With ``retrieval_window == "sources"`` the window
        instead holds up to ``k`` distinct sources, each represented by its
        best-ranked chunk, so ``k`` chunks stand for ``k`` sources. Selection
        happens after the fail-closed scope filter, so an out-of-scope chunk can
        never enter either window.
        """
        if k <= 0:
            return []

        if self.retrieval_mode == RETRIEVAL_MODE_HYBRID:
            return self._query_hybrid(text, k)

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
            include=["documents", "metadatas", "distances"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        matches: list[dict[str, Any]] = []
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
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
                    "similarity": _similarity(distance),
                }
            )
        return self._window(matches, k)

    def _query_hybrid(self, text: str, k: int) -> list[dict[str, Any]]:
        """Dense+lexical retrieval over the whole candidate set.

        Over-fetches every stored chunk (the scoped path's behaviour, applied to
        both stores so the unscoped path has candidates to fuse), fails closed on
        scope *before* ranking, fuses the dense and BM25 rankings by RRF, then
        truncates to ``k`` with the unchanged return shape.
        """
        count = self._collection.count()
        if count == 0:
            return []

        result = self._collection.query(
            query_embeddings=self.embedder([text]),
            n_results=count,
            include=["documents", "metadatas", "distances"],
        )

        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]

        candidates: list[dict[str, Any]] = []
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            meta = metadata or {}
            source_path = meta.get("source_path")
            if self.scope is not None and not _within_scope(self.scope, source_path):
                continue
            candidates.append(
                {
                    "id": chunk_id,
                    "text": document,
                    "source_path": source_path,
                    "breadcrumb": meta.get("breadcrumb"),
                    "similarity": _similarity(distance),
                }
            )
        if not candidates:
            return []

        dense_order = list(range(len(candidates)))
        lexical_scores = _bm25_scores(
            text, [candidate["text"] or "" for candidate in candidates]
        )
        lexical_order = sorted(
            range(len(candidates)), key=lambda index: (-lexical_scores[index], index)
        )
        fused = _reciprocal_rank_fusion(dense_order, lexical_order, len(candidates))
        order = sorted(
            range(len(candidates)), key=lambda index: (-fused[index], index)
        )
        ranked = [candidates[index] for index in order]
        return self._window(ranked, k)
