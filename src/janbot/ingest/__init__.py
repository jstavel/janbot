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

    Only files proven to lie within ``corpus_root`` are read (fail-closed). The
    index is reconciled to this corpus: desired chunks are upserted, then any
    stored id whose source lies within ``corpus_root`` but is no longer present
    is deleted, so a re-run never duplicates and removed or renamed subtrees
    leave no orphan while other corpora's chunks are preserved. A missing or
    non-directory ``corpus_root`` raises ``ValueError`` rather than wiping the
    index.
    """
    root = Path(corpus_root)
    try:
        root_resolved = root.resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"corpus root is not a directory: {root}") from exc
    if not root_resolved.is_dir():
        raise ValueError(f"corpus root is not a directory: {root}")

    chunks: list[Chunk] = []
    for path in iter_org_files(root):
        if not within(root, path):
            continue
        chunks.extend(read_org_file(path))

    store = VectorStore(index_path, embedder or default_embedder())
    store.upsert(chunks)
    desired = {chunk.id for chunk in chunks}
    stale = [
        chunk_id
        for chunk_id, source in store.sources().items()
        if chunk_id not in desired and within(root, source)
    ]
    store.delete(stale)
    return len(chunks)
