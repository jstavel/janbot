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


def test_item19_clause_keeps_the_grounded_clause() -> None:
    """The recorded item-19 shape: drop the technology clause, keep the grounded clause."""
    result = apply_output_guard(
        answer=(
            "I have a strong foundation in TypeScript, and I focus on creating "
            "systems with verifiable outputs."
        ),
        citations=["intro.org"],
        retrieved_chunks=_chunks(
            (
                "intro.org",
                "Python and Perl by hand, Clojure by heart, TypeScript with agents. "
                "I focus on creating systems with verifiable outputs.",
            )
        ),
    )

    assert result.declined is False
    assert result.answer == "I focus on creating systems with verifiable outputs."
    assert result.dropped_clauses == ["I have a strong foundation in TypeScript"]


def test_overclaim_in_the_first_of_two_clauses() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in TypeScript, and I build verified systems.",
        citations=["intro.org"],
        retrieved_chunks=_chunks(("intro.org", "I build verified systems.")),
    )

    assert result.declined is False
    assert result.answer == "I build verified systems."
    assert result.dropped_clauses == ["I have a strong foundation in TypeScript"]


def test_overclaim_in_the_second_of_two_clauses() -> None:
    result = apply_output_guard(
        answer="I build verified systems, and I have a strong foundation in TypeScript.",
        citations=["intro.org"],
        retrieved_chunks=_chunks(("intro.org", "I build verified systems.")),
    )

    assert result.declined is False
    assert result.answer == "I build verified systems."
    assert result.dropped_clauses == ["I have a strong foundation in TypeScript."]


def test_version_number_is_not_a_clause_boundary() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in Python 3.12.",
        citations=["intro.org"],
        retrieved_chunks=_chunks(
            ("intro.org", "I have a strong foundation in Python 3.12.")
        ),
    )

    assert result.declined is False
    assert result.answer == "I have a strong foundation in Python 3.12."
    assert result.dropped_clauses == []


def test_object_id_alias_resolves_to_the_retrieved_source() -> None:
    result = apply_output_guard(
        answer="I built the matching engine.",
        citations=["20261007-matching-engine"],
        retrieved_chunks=_chunks(
            (
                "matching-engine.org",
                ":PROPERTIES:\n:ID: 20261007-matching-engine\n:END:\n\n# Matching engine\n",
            )
        ),
    )

    assert result.declined is False
    assert result.answer == "I built the matching engine."
    assert result.citations == ["matching-engine.org"]
    assert result.normalized_count == 1


def test_cross_link_is_not_an_alias_of_another_objects_id() -> None:
    """A [[id:...]] cross-link in another object's text must not map that object as an alias."""
    result = apply_output_guard(
        answer="The recovery work used the Linux From Scratch story.",
        citations=["20261007-linux-from-scratch"],
        retrieved_chunks=_chunks(
            (
                "linux-from-scratch.org",
                ":PROPERTIES:\n:ID: 20261007-linux-from-scratch\n:END:\n\n# LFS\n",
            ),
            (
                "filesystem-recovery.org",
                "Related: [[id:20261007-linux-from-scratch][Linux From Scratch]].\n",
            ),
        ),
    )

    assert result.citations == ["linux-from-scratch.org"]
    assert result.normalized_count == 1
    assert result.citations != ["filesystem-recovery.org"]


def test_unretrieved_object_id_falls_through_to_d1() -> None:
    result = apply_output_guard(
        answer="I built it.",
        citations=["20261007-not-retrieved"],
        retrieved_chunks=_chunks(("profile.org", ":PROPERTIES:\n:ID: 20261001-profile\n:END:\n")),
    )

    assert result.declined is True
    assert result.action == "declined: D1-all-invalid"
    assert result.normalized_count == 0


def test_empty_citations_decline_as_uncited() -> None:
    result = apply_output_guard(
        answer="I built it.",
        citations=[],
        retrieved_chunks=_chunks(("profile.org", "Built it.")),
    )

    assert result.declined is True
    assert result.action == "declined: uncited"


def test_all_invalid_labels_decline_as_d1_all_invalid() -> None:
    result = apply_output_guard(
        answer="I built it.",
        citations=["elsewhere.md"],
        retrieved_chunks=_chunks(("profile.org", "Built it.")),
    )

    assert result.declined is True
    assert result.action == "declined: D1-all-invalid"


def test_partial_d1_repair_action() -> None:
    result = apply_output_guard(
        answer="I built it.",
        citations=["profile.org", "elsewhere.md"],
        retrieved_chunks=_chunks(("profile.org", "Built it.")),
    )

    assert result.declined is False
    assert result.action == "repaired: D1-partial"


def test_d1_and_d2_repair_action() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in TypeScript. I build verified systems.",
        citations=["profile.org", "elsewhere.md"],
        retrieved_chunks=_chunks(("profile.org", "I build verified systems.")),
    )

    assert result.declined is False
    assert result.action == "repaired: D1-partial + D2"


def test_d2_empty_action() -> None:
    result = apply_output_guard(
        answer="I have a strong foundation in TypeScript.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Engineering background.")),
    )

    assert result.declined is True
    assert result.action == "declined: D2-empty"


def test_guard_error_action_is_named() -> None:
    # Force the internal helper to fail by passing a malformed chunk mapping.
    result = apply_output_guard(
        answer="I built it.",
        citations=["profile.org"],
        retrieved_chunks=[{"source": "profile.org"}],  # type: ignore[list-item]
    )

    assert result.declined is True
    assert result.action == "declined: guard-error"


def test_probe_overclaim_is_refused_and_clojure_control_survives() -> None:
    """The two recorded probe answers: the commitment claim is refused; the control answers."""
    overclaim = apply_output_guard(
        answer="I am interested in working for your company on Clojure.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "Public profile of Jan Stavel.")),
    )
    assert overclaim.declined is True

    control = apply_output_guard(
        answer="I have used Clojure in production systems.",
        citations=["profile.org"],
        retrieved_chunks=_chunks(("profile.org", "I have used Clojure in production systems.")),
    )
    assert control.declined is False
    assert control.citations == ["profile.org"]
