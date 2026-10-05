"""Org-mode ingestion: read, scope and index the public corpus."""

from __future__ import annotations

from pathlib import Path

from janbot.ingest.org import Chunk, read_org_file
from janbot.ingest.scope import iter_org_files, within
from janbot.store import Embedder, VectorStore, default_embedder

__all__ = [
    "Chunk",
    "index_corpus",
    "iter_org_files",
    "read_org_file",
    "within",
]


def index_corpus(
    corpus_root: str | Path,
    index_path: str | Path,
    embedder: Embedder | None = None,
) -> int:
    """Index every ``.org`` file under ``corpus_root`` and return the chunk count.

    Only files proven to lie within ``corpus_root`` are read (fail-closed). An
    empty corpus writes nothing and returns ``0`` without error.
    """
    root = Path(corpus_root)
    chunks: list[Chunk] = []
    for path in iter_org_files(root):
        if not within(root, path):
            continue
        chunks.extend(read_org_file(path))

    store = VectorStore(index_path, embedder or default_embedder())
    store.upsert(chunks)
    return len(chunks)
