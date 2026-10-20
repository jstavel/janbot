"""Build-time answer cache for :data:`/chat` (ADR-009 control 1).

The cache is a static artifact baked into the image: it makes no model call and
opens no runtime store. Its payload is the final recorded ``ChatResponse`` from a
pinned **production-config** eval run, not the golden dataset's
``expected_answer`` — the answer a real caller would have received.

Lookup is keyed by a normalized question: trimmed, lower-cased, and with internal
whitespace collapsed. The artifact carries its provenance (run id, date, routed
models, dataset sha256, corpus commit, output-guard state); :mod:`build_cache`
validates it before the artifact is baked. Loading validates every entry as a
:class:`ChatResponse` and refuses an ``insufficient`` entry, so a corrupt cache
fails closed at startup rather than shipping a malformed reply.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from janbot.api.contract import ChatResponse

CACHE_VERSION = 1
REQUIRED_METADATA = (
    "run_id",
    "date",
    "model_mode",
    "requested_model",
    "routed_models",
    "dataset_sha256",
    "corpus_commit",
    "corpus_sha256",
    "output_guard",
)
_WHITESPACE = re.compile(r"\s+")


def corpus_sha256(root: str | Path) -> str:
    """A deterministic content hash over the corpus tree (names + bytes).

    Excludes Python caches, matching the Terraform build trigger's tree hash.
    """
    base = Path(root)
    files = sorted(
        path
        for path in base.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix != ".pyc"
    )
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(base).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def normalize_question(question: str) -> str:
    """Return the cache key for ``question``: trimmed, lower-cased, whitespace collapsed."""
    return _WHITESPACE.sub(" ", question.strip()).lower()


class CacheError(ValueError):
    """The cache artifact is missing metadata or carries an invalid entry."""


@dataclass(frozen=True)
class CacheEntry:
    """One cached answer and the model that produced it."""

    question: str
    response: ChatResponse
    routed_model: str | None = None


@dataclass(frozen=True)
class AnswerCache:
    """A loaded, read-only cache keyed by normalized question."""

    metadata: dict[str, Any]
    entries: dict[str, CacheEntry]

    def lookup(self, question: str) -> ChatResponse | None:
        """Return the cached response for ``question``, or ``None`` on a miss."""
        entry = self.entries.get(normalize_question(question))
        return None if entry is None else entry.response


def _validate_metadata(metadata: Any) -> dict[str, Any]:
    if not isinstance(metadata, dict):
        raise CacheError("cache metadata must be an object")
    missing = [key for key in REQUIRED_METADATA if key not in metadata]
    if missing:
        raise CacheError(f"cache metadata is missing: {', '.join(missing)}")
    version = metadata.get("version", CACHE_VERSION)
    if version != CACHE_VERSION:
        raise CacheError(
            f"cache version {version!r} is unsupported; expected {CACHE_VERSION}"
        )
    if metadata["output_guard"] != "on":
        raise CacheError(
            "cache artifact was recorded with the output guard off; "
            "refusing to serve unguarded answers"
        )
    return metadata


def _parse_entries(raw: Any) -> dict[str, CacheEntry]:
    if not isinstance(raw, list):
        raise CacheError("cache entries must be a list")
    entries: dict[str, CacheEntry] = {}
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise CacheError(f"cache entry at index {index} is not an object")
        question = item.get("question")
        if not isinstance(question, str) or not question.strip():
            raise CacheError(f"cache entry at index {index} has no question")
        response_raw = item.get("response")
        try:
            response = ChatResponse.model_validate(response_raw)
        except Exception as exc:
            raise CacheError(
                f"cache entry at index {index} is not a valid ChatResponse: {exc}"
            ) from exc
        if response.status != "answered":
            raise CacheError(
                f"cache entry at index {index} is a refusal; refusals stay live"
            )
        key = normalize_question(question)
        if key in entries:
            raise CacheError(
                f"cache entry at index {index} duplicates normalized question {key!r}"
            )
        routed_model = item.get("routed_model")
        if routed_model is not None and not isinstance(routed_model, str):
            raise CacheError(
                f"cache entry at index {index} has a non-string routed_model"
            )
        entries[key] = CacheEntry(
            question=question.strip(), response=response, routed_model=routed_model
        )
    return entries


def parse_cache(document: Any) -> AnswerCache:
    """Validate a decoded cache document and return an :class:`AnswerCache`."""
    if not isinstance(document, dict):
        raise CacheError("cache artifact must be a JSON object")
    metadata = _validate_metadata(document.get("metadata"))
    entries = _parse_entries(document.get("entries"))
    return AnswerCache(metadata=metadata, entries=entries)


def load_cache(path: str | Path) -> AnswerCache:
    """Read and validate the cache artifact at ``path``.

    Raises:
        CacheError: if the file is missing, unreadable, malformed, or carries an
            invalid entry.
    """
    cache_path = Path(path)
    try:
        document = json.loads(cache_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CacheError(f"answer cache not found: {cache_path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CacheError(f"answer cache at {cache_path} is unreadable: {exc}") from exc
    return parse_cache(document)


def build_document(
    metadata: dict[str, Any],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the canonical artifact document (validated by :func:`parse_cache`)."""
    document = {
        "metadata": {"version": CACHE_VERSION, **metadata},
        "entries": entries,
    }
    parse_cache(document)
    return document
