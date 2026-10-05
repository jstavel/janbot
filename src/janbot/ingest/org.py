"""Org-mode reading for the ingestion pipeline.

One :class:`Chunk` is produced for every non-root subtree of a file, at any
depth. The text of a chunk concatenates its heading, tags, PROPERTIES drawer,
body (LOGBOOK included) and the text of every descendant node; the breadcrumb
carries the full heading path down to (and including) the subtree so a citation
can show where the chunk came from. A document-order ordinal keeps ids unique
within a file even when sibling headings collide.
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


def _properties_text(node: orgparse.OrgNode) -> str:
    """Render the node's PROPERTIES drawer, if any, as an org-style block."""
    if not node.properties:
        return ""
    lines = [":PROPERTIES:"]
    for key, value in node.properties.items():
        lines.append(f":{key}: {value}")
    lines.append(":END:")
    return "\n".join(lines)


def _subtree_text(node: orgparse.OrgNode) -> str:
    """Render ``node`` and all of its descendants as plain text lines."""
    lines: list[str] = []

    heading = (node.heading or "").strip()
    if heading or node.tags:
        if node.tags:
            tags = ":".join(sorted(node.tags))
            heading = f"{heading} :{tags}:".strip()
        lines.append(heading)

    properties = _properties_text(node)
    if properties:
        lines.append(properties)

    body = node.get_body("raw").strip()
    if body:
        lines.append(body)

    for child in node.children:
        child_text = _subtree_text(child)
        if child_text:
            lines.append(child_text)

    return "\n".join(lines)


def _iter_subtree_nodes(node: orgparse.OrgNode):
    """Yield every non-root descendant of ``node`` in document order."""
    for child in node.children:
        yield child
        yield from _iter_subtree_nodes(child)


def read_org_file(path: str | Path) -> list[Chunk]:
    """Read ``path`` and return one chunk per non-root subtree node."""
    source = Path(path).resolve()
    root = orgparse.load(source)

    chunks: list[Chunk] = []
    for ordinal, node in enumerate(_iter_subtree_nodes(root)):
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
