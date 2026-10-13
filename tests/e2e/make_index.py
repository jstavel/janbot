"""Build a crafted ChromaDB index for the port-only grounding tests.

The ingestion CLI writes only in-scope, sourced chunks, so it cannot produce the
two indexes the grounding cases need:

- ``foreign``    -- one chunk whose absolute ``source_path`` lies outside the
  served corpus root (the goal-5 startup refusal).
- ``sourceless`` -- one chunk with ``source_path=None`` (a sourceless-only index
  that starts but yields no in-corpus grounding).

This helper runs as a subprocess (like ``python -m janbot.ingest``) so the test
modules never import ``janbot`` themselves. It is a non-test module: the name
does not start with ``test_``, so pytest never collects it. It embeds with the
production :func:`janbot.store.default_embedder` so the vectors it writes match
the embedder the served process uses at query time.

Usage::

    python tests/e2e/make_index.py <index_path> --kind foreign|sourceless [--corpus PATH]
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from janbot.store import VectorStore, default_embedder

KINDS = ("foreign", "sourceless")

DEFAULT_FOREIGN_SOURCE = "/tmp/janbot-foreign/foreign.org"
FOREIGN_TEXT = "a private note that lives outside the public corpus"
SOURCELESS_TEXT = "an unattributable note with no source path"


class CraftedChunk:
    """Chunk-shaped stand-in the store's ``upsert`` accepts."""

    def __init__(self, chunk_id: str, text: str, source_path: Any) -> None:
        self.id = chunk_id
        self.text = text
        self.source_path = source_path
        self.breadcrumb = "Crafted"


def _foreign_source(corpus: Path | None) -> str:
    """Return an absolute path outside ``corpus`` (a sibling ``elsewhere`` tree)."""
    if corpus is None:
        return DEFAULT_FOREIGN_SOURCE
    return str(Path(corpus).expanduser().resolve().parent / "elsewhere" / "foreign.org")


def build(index_path: Path, kind: str, corpus: Path | None = None) -> int:
    """Write a one-chunk index of ``kind`` at ``index_path``; return the chunk count."""
    store = VectorStore(index_path, default_embedder())
    if kind == "foreign":
        chunk = CraftedChunk("crafted::foreign::0", FOREIGN_TEXT, _foreign_source(corpus))
    elif kind == "sourceless":
        chunk = CraftedChunk("crafted::sourceless::0", SOURCELESS_TEXT, None)
    else:
        raise SystemExit(f"unknown kind {kind!r}; choose from {', '.join(KINDS)}")
    store.upsert([chunk])
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python tests/e2e/make_index.py")
    parser.add_argument("index_path", help="where to write the ChromaDB index")
    parser.add_argument("--kind", required=True, choices=KINDS, help="crafted chunk kind")
    parser.add_argument(
        "--corpus",
        default=None,
        help="served corpus root; the foreign source is placed outside it",
    )
    args = parser.parse_args(argv)

    corpus = Path(args.corpus) if args.corpus is not None else None
    count = build(Path(args.index_path), args.kind, corpus)
    print(count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
