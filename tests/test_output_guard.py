"""Unit tests for the deterministic output guard (ADR-010).

No model, no network, no dataset: the guard is pure string logic over a request's answer,
cited labels and retrieved chunks.
"""

from __future__ import annotations

import pytest

from janbot.guardrails import apply_output_guard
from janbot.guardrails import output_guard
from janbot.guardrails.lexicon import LEXICON_VERSION, MARKERS, SUBJECT_TOKENS


def _chunks(*pairs: tuple[str, str]) -> list[dict[str, str]]:
    return [{"source": source, "text": text} for source, text in pairs]


def test_fabricated_label_is_dropped_and_answer_kept() -> None:
    result = apply_output_guard(
        answer="I built JanBot.",
        citations=["profile.org", "elsewhere.md"],
        retrieved_chunks=_chunks(("profile.org", "Built JanBot, a RAG assistant.")),
    )

    assert result.declined is False
    assert result.answer == "I built JanBot."
    assert result.citations == ["profile.org"]
    assert result.dropped_citations == ["elsewhere.md"]


def test_all_fabricated_labels_decline() -> None:
    result = apply_output_guard(
        answer="I built JanBot.",
        citations=["elsewhere.md", "[invented.org]"],
        retrieved_chunks=_chunks(("profile.org", "Built JanBot.")),
    )

    assert result.declined is True
    assert result.citations == []
    assert result.dropped_citations == ["elsewhere.md", "invented.org"]


def test_bracketed_label_is_normalized() -> None:
    result = apply_output_guard(
        answer="I built JanBot.",
        citations=[" [profile.org] "],
        retrieved_chunks=_chunks(("profile.org", "Built JanBot.")),
    )

    assert result.declined is False
    assert result.citations == ["profile.org"]


def test_ungrounded_overclaim_sentence_is_dropped() -> None:
    result = apply_output_guard(
        answer=(
            "I value clarity. I have a strong foundation in TypeScript. "
            "I build systems with verifiable outputs."
        ),
        citations=["intro.org"],
        retrieved_chunks=_chunks(
            ("intro.org", "Python and Perl by hand, Clojure by heart, TypeScript with agents.")
        ),
    )

    assert result.declined is False
    assert result.answer == "I value clarity. I build systems with verifiable outputs."
    assert result.dropped_sentences == ["I have a strong foundation in TypeScript."]


def test_grounded_marker_is_kept() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in Python.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(
            ("profile.org", "I have a strong foundation in Python and Perl.")
        ),
    )

    assert result.declined is False
    assert result.answer == "I have a strong foundation in Python."
    assert result.dropped_sentences == []


def test_marker_without_subject_is_kept() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Engineering background.")),
    )

    assert result.declined is False
    assert result.answer == "I have a strong foundation."


def test_subject_without_marker_is_kept() -> None:
    """The guard is a floor: an unmarked claim is outside D2 and is not dropped."""
    result = apply_output_guard(
        answer="I know TypeScript well.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Engineering background.")),
    )

    assert result.declined is False
    assert result.answer == "I know TypeScript well."


def test_subject_before_marker_is_not_the_markers_object() -> None:
    """A technology mentioned before the marker is not the marker's claim window."""
    answer = (
        "The author has expertise in Python and Perl, and emphasizes a strong "
        "foundation in asynchronous systems and invariant testing."
    )
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(
            ("profile.org", "Python and Perl by hand; asynchronous systems and invariant testing.")
        ),
    )

    assert result.declined is False
    assert result.answer == answer
    assert result.dropped_sentences == []


def test_single_ungrounded_sentence_declines() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in TypeScript.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Engineering background.")),
    )

    assert result.declined is True
    assert result.citations == []
    assert result.dropped_sentences == ["I have a strong foundation in TypeScript."]


def test_clean_answer_is_byte_identical() -> None:
    answer = "I built JanBot — a RAG assistant.\nIt answers from my public profile."
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Built JanBot.")),
    )

    assert result.declined is False
    assert result.answer == answer
    assert result.citations == ["profile.org"]
    assert result.dropped_citations == []
    assert result.dropped_sentences == []


def test_guard_internal_error_declines(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(output_guard, "_guard", explode)

    result = apply_output_guard(
        answer="I built JanBot.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Built JanBot.")),
    )

    assert result.declined is True
    assert result.reason == "guard internal error"
    assert result.citations == []


def test_lexicon_is_versioned_data() -> None:
    assert LEXICON_VERSION
    assert MARKERS
    assert SUBJECT_TOKENS
    assert all(len(marker) == 2 for marker in MARKERS)
