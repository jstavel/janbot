"""Org-mode reading for the ingestion pipeline.

One :class:`Chunk` is produced for every non-root subtree of a file, at any
depth, plus one for the file root when that root carries a PROPERTIES drawer or
text of its own. The text of a subtree chunk concatenates its heading, tags,
PROPERTIES drawer, body (LOGBOOK included) and the text of every descendant
node; the breadcrumb carries the full heading path down to (and including) the
subtree so a citation can show where the chunk came from. The root chunk carries
the file's drawer (the approved ``:SYNOPSIS:`` among it) and any text above the
first heading, so a document's own summary is retrievable instead of being the
one part of the file nothing can reach; its breadcrumb is the
:data:`_ROOT_BREADCRUMB` marker, which no heading path can collide with.

Org keyword lines (``#+TITLE:`` and friends) are document metadata rather than
prose, so they are not part of the root chunk's text: a file whose root holds
nothing but keywords yields no root chunk at all.

An id derives from the chunk's own content (source, breadcrumb and text) rather
than its document-order position, so a chunk's identity is stable across
insertions and reorderings above it; the text is part of the hash, keeping
sibling subtrees with an identical heading path but different bodies distinct.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import orgparse

from janbot.ingest.scope import located_path

__all__ = ["Chunk", "read_org_file"]

_ROOT_BREADCRUMB = "(file)"

# ``#+TITLE:``/``#+AUTHOR:`` are keywords; ``#+BEGIN_SRC``/``#+END_SRC`` are not
# (no colon), so requiring one keeps block delimiters in the body.
_KEYWORD_LINE = re.compile(r"^\s*#\+[A-Za-z_]+:")


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
    can serve as the breadcrumb a citation shows for the chunk.
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


def _root_text(root: orgparse.OrgNode) -> str:
    """Render the file root: its PROPERTIES drawer and its own text.

    This is the one chunk a document's approved ``:SYNOPSIS:`` can travel in, so
    it is built from the drawer plus whatever text sits above the first heading.
    Org keyword lines are metadata, not prose, so they are dropped; a root left
    with neither drawer nor text renders as ``""`` and yields no chunk.
    """
    parts: list[str] = []

    properties = _properties_text(root)
    if properties:
        parts.append(properties)

    body_lines = [
        line
        for line in root.get_body("raw").splitlines()
        if not _KEYWORD_LINE.match(line)
    ]
    body = "\n".join(body_lines).strip()
    if body:
        parts.append(body)

    return "\n".join(parts)


def _iter_subtree_nodes(node: orgparse.OrgNode):
    """Yield every non-root descendant of ``node`` in document order."""
    for child in node.children:
        yield child
        yield from _iter_subtree_nodes(child)


def _chunk_id(source: Path, breadcrumb: str, text: str) -> str:
    """Return a content-addressed id for a chunk.

    The digest covers the source, breadcrumb and text, so a chunk's id depends
    only on the chunk itself: inserting or reordering a heading above it leaves
    its id unchanged, while editing its own body changes it. Including the text
    keeps sibling subtrees sharing a heading path but differing in body apart.
    """
    digest = hashlib.sha256(f"{source}\n{breadcrumb}\n{text}".encode()).hexdigest()
    return f"{source}::{digest}"


def _append_chunk(
    chunks: list[Chunk],
    seen: dict[str, int],
    source: Path,
    breadcrumb: str,
    text: str,
) -> None:
    """Append ``text`` as a chunk, suffixing a repeat of a base id.

    An id is content-addressed, so exact duplicates (same source, breadcrumb and
    text) would collide; each repeat of a base id takes a numeric suffix. No
    ordinal is used for distinct chunks, so their ids stay stable across edits
    elsewhere in the file.
    """
    if not text:
        return
    base = _chunk_id(source, breadcrumb, text)
    repeat = seen.get(base, 0)
    seen[base] = repeat + 1
    chunks.append(
        Chunk(
            id=base if repeat == 0 else f"{base}::{repeat}",
            text=text,
            source_path=str(source),
            breadcrumb=breadcrumb,
        )
    )


def read_org_file(path: str | Path) -> list[Chunk]:
    """Read ``path`` and return one chunk per non-root subtree, plus the file root.

    The root chunk comes first, carrying the file's PROPERTIES drawer and the
    text above its first heading; it is omitted when the root has neither.

    Ids are content-addressed (see :func:`_append_chunk`).
    """
    source = located_path(path)
    root = orgparse.load(source)

    chunks: list[Chunk] = []
    seen: dict[str, int] = {}
    _append_chunk(chunks, seen, source, _ROOT_BREADCRUMB, _root_text(root))
    for node in _iter_subtree_nodes(root):
        _append_chunk(chunks, seen, source, _heading_path(node), _subtree_text(node))
    return chunks
