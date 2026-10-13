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
    index is reconciled to this corpus: desired chunks are upserted carrying this
    corpus's resolved root as their scope key, then any stored id whose *stored*
    scope key equals this corpus's root but is no longer present is deleted, so a
    re-run never duplicates and removed or renamed subtrees leave no orphan while
    other corpora's chunks are preserved. Ownership is stored with the chunk, not
    re-derived from a filesystem-path coincidence. A chunk written before the
    scope key existed (none recorded) falls back to path ownership, so an
    in-place rebuild still prunes its orphans. A missing or non-directory
    ``corpus_root`` raises ``ValueError`` rather than wiping the index.
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

    scope_key = str(root_resolved)
    store = VectorStore(index_path, embedder or default_embedder())
    store.upsert(chunks, scope_key=scope_key)
    desired = {chunk.id for chunk in chunks}
    scopes = store.scope_keys()
    sources = store.sources()
    stale: list[str] = []
    for chunk_id in store.ids():
        if chunk_id in desired:
            continue
        stored_scope = scopes.get(chunk_id)
        if stored_scope == scope_key:
            stale.append(chunk_id)
        elif stored_scope is None:
            # Predates the scope-key scheme; fall back to path ownership so an
            # in-place rebuild prunes this corpus's orphans.
            source = sources.get(chunk_id)
            if source and within(root, source):
                stale.append(chunk_id)
    store.delete(stale)
    return len(chunks)
