"""Deterministic output-level guard (ADR-010).

Two rules, no model call, no network, no dataset access:

- **D1 fabricated citation:** a cited label not in the retrieved source set is dropped.
  The answer is kept; if no valid label remains the caller declines through the existing
  uncited path.
- **D2 over-claim:** a sentence containing a marker from the versioned lexicon and a
  subject token is kept only when a cited chunk contains the marker's grounded form and the
  subject token in the same sentence. Otherwise the sentence is dropped.

The guard is a floor, not a semantic judge. It cannot catch paraphrase, implication or a
claim phrased without a marker; see ADR-010.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from janbot.guardrails.lexicon import MARKERS, SUBJECT_TOKENS

__all__ = ["GuardResult", "apply_output_guard"]


@dataclass(frozen=True)
class GuardResult:
    """The guard's decision for one prediction.

    ``declined`` is the fail-closed outcome: the caller must route it through the existing
    decline path and must not emit ``answer``. ``answer`` and ``citations`` are only
    meaningful when ``declined`` is false.
    """

    answer: str
    citations: list[str]
    declined: bool = False
    reason: str = ""
    dropped_citations: list[str] = field(default_factory=list)
    dropped_sentences: list[str] = field(default_factory=list)


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")


def _normalize_label(label: str) -> str:
    """Strip whitespace and an optional surrounding ``[ ]`` pair (context labels)."""
    normalized = label.strip()
    if len(normalized) >= 2 and normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    return normalized


def _contains(text: str, phrase: str) -> bool:
    """Case-insensitive phrase match with non-alphanumeric boundaries.

    Boundaries are deliberately based on letters/digits rather than ``\\b`` so tokens such
    as ``c++`` and ``on-site`` still match without swallowing a longer word.
    """
    pattern = rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])"
    return re.search(pattern, text.lower()) is not None


def _subject_tokens_in(sentence: str) -> list[str]:
    return [token for token in SUBJECT_TOKENS if _contains(sentence, token)]


def _markers_in(sentence: str) -> list[tuple[str, str]]:
    return [
        (marker.answer_phrase, marker.chunk_phrase)
        for marker in MARKERS
        if _contains(sentence, marker.answer_phrase)
    ]


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]


def _is_grounded(
    marker: tuple[str, str], subject: str, cited_chunk_texts: Sequence[str]
) -> bool:
    _, chunk_phrase = marker
    for chunk_text in cited_chunk_texts:
        for chunk_sentence in _split_sentences(chunk_text):
            if _contains(chunk_sentence, chunk_phrase) and _contains(chunk_sentence, subject):
                return True
    return False


def _guard(answer: str, citations: Sequence[str], retrieved_chunks: Sequence[Mapping[str, str]]) -> GuardResult:
    sources = [str(chunk["source"]) for chunk in retrieved_chunks]
    source_set = set(sources)
    normalized = [_normalize_label(citation) for citation in citations]
    valid: list[str] = []
    dropped: list[str] = []
    for label in normalized:
        if label in source_set:
            if label not in valid:
                valid.append(label)
        elif label not in dropped:
            dropped.append(label)

    if not valid:
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="no valid citation remains after dropping fabricated labels",
            dropped_citations=dropped,
        )

    cited_sources = set(valid)
    cited_chunk_texts = [
        str(chunk["text"])
        for chunk in retrieved_chunks
        if str(chunk["source"]) in cited_sources
    ]

    kept: list[str] = []
    dropped_sentences: list[str] = []
    for sentence in _split_sentences(answer):
        markers = _markers_in(sentence)
        subjects = _subject_tokens_in(sentence)
        if markers and subjects and not any(
            _is_grounded(marker, subject, cited_chunk_texts)
            for marker in markers
            for subject in subjects
        ):
            dropped_sentences.append(sentence)
        else:
            kept.append(sentence)

    if not kept:
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="every sentence was an ungrounded over-claim",
            dropped_citations=dropped,
            dropped_sentences=dropped_sentences,
        )

    repaired = answer if not dropped_sentences else " ".join(kept)
    return GuardResult(
        answer=repaired,
        citations=valid,
        dropped_citations=dropped,
        dropped_sentences=dropped_sentences,
    )


def apply_output_guard(
    *,
    answer: str,
    citations: Sequence[str],
    retrieved_chunks: Sequence[Mapping[str, str]],
) -> GuardResult:
    """Apply D1 and D2 to one prediction. Never raises; an internal error declines.

    ``retrieved_chunks`` is the request-local list of ``{"source": label, "text": text}``
    entries. The guard uses the source labels for D1 and the text of *cited* chunks for D2.
    It must never receive ``expected_sources`` or any dataset field.
    """
    try:
        return _guard(answer, citations, retrieved_chunks)
    except Exception:  # fail closed: never emit unguarded text
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="guard internal error",
        )
