"""Org-mode reading for the ingestion pipeline.

The tracer chunker is deliberately shallow (per the story plan): one
:class:`Chunk` is produced for each top-level subtree of a file. The text of a
chunk concatenates its heading, body and the text of every descendant node; the
breadcrumb carries the heading path down to (and including) the subtree so a
citation can show where the chunk came from.

Full subtree semantics (PROPERTIES, LOGBOOK, tags, per-subtree chunking) land in
a later story; this module only establishes the reader-to-chunk seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import orgparse

__all__ = ["Chunk", "read_org_file"]


@dataclass(frozen=True)
class Chunk:
    """One semantically intact unit of an org file ready to be embedded."""

    id: str
    text: str
    source_path: str
    breadcrumb: str


def _heading_path(node: orgparse.OrgNode) -> str:
    """Return the heading path from the file root down to ``node``.

    The path includes ``node``'s own heading, so it is unique per subtree and
    can serve as the stable half of a chunk id.
    """
    headings: list[str] = []
    current: orgparse.OrgNode | None = node
    while current is not None and not current.is_root():
        heading = (current.heading or "").strip()
        if heading:
            headings.append(heading)
        current = current.parent
    headings.reverse()
    return " > ".join(headings)


def _subtree_text(node: orgparse.OrgNode) -> str:
    """Render ``node`` and all of its descendants as plain text lines."""
    lines: list[str] = []

    heading = (node.heading or "").strip()
    if heading:
        if node.tags:
            tags = ":".join(sorted(node.tags))
            heading = f"{heading} :{tags}:"
        lines.append(heading)

    body = node.get_body("raw").strip()
    if body:
        lines.append(body)

    for child in node.children:
        child_text = _subtree_text(child)
        if child_text:
            lines.append(child_text)

    return "\n".join(lines)


def read_org_file(path: str | Path) -> list[Chunk]:
    """Read ``path`` and return one chunk per top-level subtree."""
    source = Path(path).resolve()
    root = orgparse.load(source)

    chunks: list[Chunk] = []
    for ordinal, node in enumerate(root.children):
        breadcrumb = _heading_path(node)
        text = _subtree_text(node)
        if not text:
            continue
        chunks.append(
            Chunk(
                id=f"{source}::{ordinal}::{breadcrumb}",
                text=text,
                source_path=str(source),
                breadcrumb=breadcrumb,
            )
        )
    return chunks
