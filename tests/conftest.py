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


def _chunk_id(path: Path, ordinal: int, breadcrumb: str) -> str:
    """Build the id production uses: from the located path, not the symlink."""
    return f"{located_path(path)}::{ordinal}::{breadcrumb}"


@pytest.fixture
def embedder() -> Callable[[list[str]], list[list[float]]]:
    return _stub_embedder


@pytest.fixture
def write_org() -> Callable[..., None]:
    return _write_org


@pytest.fixture
def chunk_id() -> Callable[..., str]:
    return _chunk_id
