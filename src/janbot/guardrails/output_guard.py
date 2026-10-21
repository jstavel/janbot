"""Deterministic output-level guard (ADR-010).

Two rules, no model call, no network, no dataset access:

- **D1 fabricated citation:** a cited label not in the retrieved source set is dropped.
  The answer is kept; if no valid label remains the caller declines through the existing
  uncited path.
- **D2 over-claim:** a clause containing a marker from the versioned lexicon and a subject
  token in the marker's forward window is kept only when a cited chunk contains the marker's
  grounded form and the subject token in the same window. Otherwise the clause is dropped;
  grounded clauses in the same sentence survive. Sentences are split only on the declared
  connector set.

The guard is a floor, not a semantic judge. It cannot catch paraphrase, implication or a
claim phrased without a marker; see ADR-010.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from janbot.guardrails.lexicon import (
    ACTIONABLE_COMMITMENTS,
    CLAUSE_CONNECTORS,
    COMPANY_INTEREST_PREDICATES,
    COMPANY_REFERENCES,
    MARKERS,
    NAMED_COMPANY_PATTERN,
    NON_COMPANY_PROPER_NOUNS,
    SUBJECT_TOKENS,
)

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
    rule: str = ""
    dropped_citations: list[str] = field(default_factory=list)
    dropped_sentences: list[str] = field(default_factory=list)
    dropped_clauses: list[str] = field(default_factory=list)
    normalized_count: int = 0

    @property
    def action(self) -> str:
        """The closed-set seam label (ADR-010 amendment)."""
        if self.declined:
            return f"declined: {self.rule}"
        changed = self.dropped_citations or self.dropped_sentences or self.dropped_clauses
        if not changed:
            return "none"
        return f"repaired: {self.rule}"


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+")
_CLAIM_WINDOW = 120
_CLAUSE_PATTERN = re.compile("(" + "|".join(CLAUSE_CONNECTORS) + ")")


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(phrase.lower())}(?![a-z0-9])")


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
    return _phrase_pattern(phrase).search(text.lower()) is not None


def _subject_tokens_in(text: str) -> list[str]:
    return [token for token in SUBJECT_TOKENS if _contains(text, token)]


_FIRST_PERSON = re.compile(r"\b(?:i|i'm|i am|i'd|i would|i can|my)\b", re.I)


def _marker_is_grounded(chunk_phrase: str, cited_chunk_texts: Sequence[str]) -> bool:
    """Whether a cited chunk contains the marker's grounded form at all."""
    return any(_contains(chunk_text, chunk_phrase) for chunk_text in cited_chunk_texts)


def _named_company_in(clause: str) -> str | None:
    """The first capitalized proper noun that is not a technology/common word."""
    for match in re.finditer(NAMED_COMPANY_PATTERN, clause):
        candidate = match.group(0).strip()
        if candidate.lower() in NON_COMPANY_PROPER_NOUNS:
            continue
        first = candidate.split()[0].lower()
        if first in NON_COMPANY_PROPER_NOUNS:
            continue
        return candidate
    return None


def _company_grounded(predicate: object, reference: object, cited: Sequence[str]) -> bool:
    """Whether a cited chunk sentence contains the predicate and the company reference."""
    if isinstance(reference, str):
        reference_match = lambda sentence: _contains(sentence, reference)
    else:
        reference_match = lambda sentence: re.search(
            reference.pattern, sentence, re.I
        ) is not None
    for chunk_text in cited:
        for chunk_sentence in _split_sentences(chunk_text):
            if _contains(chunk_sentence, predicate.chunk_phrase) and reference_match(
                chunk_sentence
            ):
                return True
    return False


def _commitment_claim_is_ungrounded(
    clause: str, cited_chunk_texts: Sequence[str]
) -> bool:
    """Whether the clause carries a narrowed commitment claim (ADR-010 Amendment 4).

    The control is deliberately narrow: **actionable** commitments on Jan's behalf
    (availability, start/notice, compensation, accepting an offer, relocation/travel)
    and **interest attributed to the prospect's company** (named or deictic company
    reference). Generic enthusiasm or politeness (“Yes, I'd be interested”, “I'd be
    glad to talk”) and topic/role interest are out of scope and are served. The guard
    is a best-effort marker/reference vocabulary; it is not a semantic judge.
    """
    if _FIRST_PERSON.search(clause) is None:
        return False

    grounded_spans: list[tuple[int, int]] = []
    ungrounded_spans: list[tuple[int, int]] = []

    for predicate in ACTIONABLE_COMMITMENTS:
        for match in re.finditer(predicate.pattern, clause, re.I):
            if _marker_is_grounded(predicate.chunk_phrase, cited_chunk_texts):
                grounded_spans.append(match.span())
            else:
                ungrounded_spans.append(match.span())

    references: list[object] = [
        reference
        for reference in COMPANY_REFERENCES
        if re.search(reference.pattern, clause, re.I)
    ]
    named_company = _named_company_in(clause)
    if named_company is not None:
        references.append(named_company)

    for predicate in COMPANY_INTEREST_PREDICATES:
        for match in re.finditer(predicate.pattern, clause, re.I):
            if not references:
                continue
            if all(
                _company_grounded(predicate, reference, cited_chunk_texts)
                for reference in references
            ):
                grounded_spans.append(match.span())
            else:
                ungrounded_spans.append(match.span())

    for start, end in ungrounded_spans:
        if any(
            ground_start <= start and end <= ground_end
            for ground_start, ground_end in grounded_spans
        ):
            continue
        return True
    return False


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]


def _split_clauses(sentence: str) -> tuple[list[str], list[str]]:
    """Split a sentence on the declared connector set, keeping the connectors.

    Returns ``(clauses, connectors)`` where ``connectors[i]`` sits between clause ``i`` and
    ``i + 1``. A sentence with no declared connector is one clause and is never split.
    """
    parts = _CLAUSE_PATTERN.split(sentence)
    if len(parts) == 1:
        return [sentence], []
    clauses = [parts[0]]
    connectors: list[str] = []
    for index in range(1, len(parts), 2):
        connectors.append(parts[index])
        clauses.append(parts[index + 1])
    return clauses, connectors


def _marker_windows(sentence: str) -> list[tuple[str, str]]:
    """Yield ``(chunk_phrase, forward_window)`` for each capability marker."""
    lowered = sentence.lower()
    windows: list[tuple[str, str]] = []
    for marker in MARKERS:
        for match in _phrase_pattern(marker.answer_phrase).finditer(lowered):
            window = sentence[match.end() : match.end() + _CLAIM_WINDOW]
            if window.strip():
                windows.append((marker.chunk_phrase, window))
    return windows


def _clause_is_overclaim(clause: str, cited_chunk_texts: Sequence[str]) -> bool:
    for chunk_phrase, window in _marker_windows(clause):
        subjects = _subject_tokens_in(window)
        if subjects and not all(
            _is_grounded(chunk_phrase, subject, cited_chunk_texts)
            for subject in subjects
        ):
            return True
    return False


def _is_grounded(
    chunk_phrase: str, subject: str, cited_chunk_texts: Sequence[str]
) -> bool:
    for chunk_text in cited_chunk_texts:
        for chunk_sentence in _split_sentences(chunk_text):
            lowered = chunk_sentence.lower()
            for match in _phrase_pattern(chunk_phrase).finditer(lowered):
                window = chunk_sentence[match.end() : match.end() + _CLAIM_WINDOW]
                if _contains(window, subject):
                    return True
    return False


def _alias_map(retrieved_chunks: Sequence[Mapping[str, str]]) -> dict[str, str]:
    """Map an object's own ``:ID:`` to its source label, from retrieved chunks only.

    Only a file-root chunk's own PROPERTIES drawer is considered. A cross-link
    (``[[id:...]]``) in another object's text is never an alias, and an object that was not
    retrieved cannot be resolved. This is request-local: no corpus read, no dataset.
    """
    aliases: dict[str, str] = {}
    for chunk in retrieved_chunks:
        text = str(chunk["text"])
        if not text.lstrip().startswith(":PROPERTIES:"):
            continue
        source = str(chunk["source"])
        for object_id in re.findall(r"(?m)^:ID:\s+(\S+)\s*$", text):
            aliases.setdefault(object_id, source)
    return aliases


def _guard(answer: str, citations: Sequence[str], retrieved_chunks: Sequence[Mapping[str, str]]) -> GuardResult:
    sources = [str(chunk["source"]) for chunk in retrieved_chunks]
    source_set = set(sources)
    aliases = _alias_map(retrieved_chunks)
    raw_labels = [_normalize_label(citation) for citation in citations]
    normalized = [aliases.get(label, label) for label in raw_labels]
    normalized_count = sum(1 for label in raw_labels if label in aliases)
    valid: list[str] = []
    dropped: list[str] = []
    for label in normalized:
        if label in source_set:
            if label not in valid:
                valid.append(label)
        elif label not in dropped:
            dropped.append(label)

    if not normalized:
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="the model cited nothing",
            rule="uncited",
        )
    if not valid:
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="every cited label was fabricated after normalization",
            rule="D1-all-invalid",
            dropped_citations=dropped,
            normalized_count=normalized_count,
        )

    cited_sources = set(valid)
    cited_chunk_texts = [
        str(chunk["text"])
        for chunk in retrieved_chunks
        if str(chunk["source"]) in cited_sources
    ]

    for sentence in _split_sentences(answer):
        for clause in _split_clauses(sentence)[0]:
            if _commitment_claim_is_ungrounded(clause, cited_chunk_texts):
                return GuardResult(
                    answer=answer,
                    citations=[],
                    declined=True,
                    reason=(
                        "an ungrounded first-person commitment or interest claim "
                        "about the prospect"
                    ),
                    rule="commitment-claim",
                    dropped_citations=dropped,
                    normalized_count=normalized_count,
                )

    kept: list[str] = []
    dropped_sentences: list[str] = []
    dropped_clauses: list[str] = []
    commitment_dropped = False
    for sentence in _split_sentences(answer):
        clauses, connectors = _split_clauses(sentence)
        keep: list[bool] = []
        for clause in clauses:
            commitment_over = _commitment_claim_is_ungrounded(
                clause, cited_chunk_texts
            )
            commitment_dropped = commitment_dropped or commitment_over
            keep.append(
                not (commitment_over or _clause_is_overclaim(clause, cited_chunk_texts))
            )
        if all(keep):
            kept.append(sentence)
            continue
        dropped_clauses.extend(
            clause for clause, survives in zip(clauses, keep, strict=True) if not survives
        )
        if not any(keep):
            dropped_sentences.append(sentence)
            continue
        kept_indices = [index for index, survives in enumerate(keep) if survives]
        rebuilt = clauses[kept_indices[0]]
        for index in kept_indices[1:]:
            rebuilt += connectors[index - 1] + clauses[index]
        ending = sentence[-1] if sentence and sentence[-1] in ".!?" else ""
        if ending and not rebuilt.endswith(ending):
            rebuilt += ending
        kept.append(rebuilt)

    if not kept:
        return GuardResult(
            answer=answer,
            citations=[],
            declined=True,
            reason="the answer became empty after dropping ungrounded over-claims",
            rule="commitment-claim" if commitment_dropped else "D2-empty",
            dropped_citations=dropped,
            dropped_sentences=dropped_sentences,
            dropped_clauses=dropped_clauses,
            normalized_count=normalized_count,
        )

    repaired = answer if not (dropped_sentences or dropped_clauses) else " ".join(kept)
    d2 = bool(dropped_sentences or dropped_clauses)
    rule = (
        "D1-partial + D2"
        if dropped and d2
        else "D1-partial"
        if dropped
        else "D2"
        if d2
        else ""
    )
    if commitment_dropped:
        rule = f"{rule} + commitment".strip() if rule else "commitment"
    return GuardResult(
        answer=repaired,
        citations=valid,
        rule=rule,
        dropped_citations=dropped,
        dropped_sentences=dropped_sentences,
        dropped_clauses=dropped_clauses,
        normalized_count=normalized_count,
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
            rule="guard-error",
        )
