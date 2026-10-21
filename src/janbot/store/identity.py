"""Deterministic identity of a baked index.

The identity is a SHA256 over the sorted chunk ids, their documents and their
embedding vectors, plus the pinned embedding-model identity. It does not hash
Chroma's on-disk files (which may carry internal state); it hashes the payload
that determines retrieval, so two clean builds from the same commit and corpus
produce the same identity.
"""

from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from typing import Any

IDENTITY_FILENAME = "index-identity.json"
IDENTITY_SCHEMA_VERSION = 1


def compute_index_identity(store: Any, model: dict[str, str]) -> dict[str, Any]:
    """Return the deterministic identity record for ``store``."""
    payload = store.payload()
    digest = hashlib.sha256()
    for chunk_id in sorted(payload):
        document, embedding = payload[chunk_id]
        digest.update(chunk_id.encode("utf-8"))
        digest.update(b"\0")
        digest.update(document.encode("utf-8"))
        digest.update(b"\0")
        digest.update(struct.pack(f"<{len(embedding)}f", *embedding))
    return {
        "schema_version": IDENTITY_SCHEMA_VERSION,
        "index_identity": digest.hexdigest(),
        "chunk_count": len(payload),
        "embedding_model": model,
    }


def write_index_identity(
    index_path: str | Path, store: Any, model: dict[str, str]
) -> dict[str, Any]:
    """Write ``index-identity.json`` beside the index and return the record."""
    record = compute_index_identity(store, model)
    path = Path(index_path) / IDENTITY_FILENAME
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return record


def read_index_identity(index_path: str | Path) -> dict[str, Any]:
    """Read the recorded identity, failing loudly when it is absent."""
    path = Path(index_path) / IDENTITY_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))
