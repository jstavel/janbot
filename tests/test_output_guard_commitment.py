"""Structural commitment/interest sweep (ADR-010 Amendment 3).

The sweep is the specification of the class, not a hand-written battery. The
test generates the full product of the published axes at collection time:

    subject form × commitment predicate × prospect reference

Ungrounded cells must be declined; a supporting cited chunk must keep the same
cell. Topic interest, grounded capability/values, the grounded commitment case
and the Clojure control are the must-not-regress edge. The live
``janbot-api-00005-xqs`` answer is one cell, not a separate test. The residual
implication-only forms (no commitment word) are counted, not waived.
"""

from __future__ import annotations

import itertools

import pytest

from janbot.guardrails.lexicon import (
    COMMITMENT_PREDICATES,
    PROSPECT_REFERENCES,
    SUBJECT_FORMS,
)
from janbot.guardrails.output_guard import apply_output_guard

NEUTRAL_CHUNK = "Public profile of Jan Stavel. He builds search and testing systems."
LIVE_ANSWER = (
    "Yes, I'd be interested. I'm drawn to a workplace where people have the "
    "freedom to contribute thought."
)

SWEEP_CELLS = tuple(
    f"{subject} {predicate.lead} {reference.phrase}"
    for subject, predicate, reference in itertools.product(
        SUBJECT_FORMS, COMMITMENT_PREDICATES, PROSPECT_REFERENCES
    )
)
UNGROUNDED_ANSWERS = SWEEP_CELLS + (LIVE_ANSWER,)
GROUNDED_PAIRS = tuple(
    (predicate, reference)
    for predicate, reference in itertools.product(
        COMMITMENT_PREDICATES, PROSPECT_REFERENCES
    )
    if not predicate.bare
)

RESIDUAL_IMPLICATION = (
    "Sounds great.",
    "That sounds like a good fit.",
    "I'd be happy with that.",
    "Where do I sign?",
    "Count me in.",
    "I'm in.",
    "That works for me.",
    "I like the sound of that.",
)


def _chunks(text: str) -> list[dict[str, str]]:
    return [{"source": "profile.org", "text": text}]


@pytest.mark.parametrize("answer", UNGROUNDED_ANSWERS)
def test_every_ungrounded_sweep_cell_is_declined(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is True
    assert result.rule == "commitment-claim"


@pytest.mark.parametrize(("predicate", "reference"), GROUNDED_PAIRS)
def test_a_supporting_chunk_keeps_the_same_cell(predicate, reference) -> None:
    answer = f"I'm {predicate.lead} {reference.phrase}"
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(answer),
    )

    assert result.declined is False
    assert result.answer == answer


@pytest.mark.parametrize(
    "answer",
    (
        "I'd love to be part of the trading community.",
        "I'm interested in trading systems and distributed testing.",
        "I'm interested in what you do.",
    ),
)
def test_topic_interest_is_not_declined(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is False
    assert result.answer == answer


def test_grounded_capability_claim_is_kept() -> None:
    answer = "I have a strong foundation in Python."
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(answer),
    )

    assert result.declined is False
    assert result.answer == answer


def test_grounded_values_statement_is_kept() -> None:
    answer = "I value freedom, commitment, and accountability."
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks("We value freedom and accountability."),
    )

    assert result.declined is False
    assert result.answer == answer


@pytest.mark.parametrize(
    ("answer", "chunk"),
    (
        ("I can start.", "I can start."),
        ("I gladly accept.", "I gladly accept."),
        ("I accept.", "I accept the offer."),
        ("Yes, I'd be interested.", "I am interested in working for your company."),
        ("I'm available.", "I'm available."),
    ),
)
def test_a_bare_commitment_is_kept_by_a_supporting_chunk(
    answer: str, chunk: str
) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(chunk),
    )

    assert result.declined is False


def test_clojure_control_still_answers_with_citations() -> None:
    answer = "I have used Clojure in production systems."
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(answer),
    )

    assert result.declined is False
    assert result.answer == answer
    assert result.citations == ["profile.org"]


def test_implication_only_residual_is_counted_not_waived() -> None:
    declined = [
        apply_output_guard(
            answer=answer,
            citations=["profile.org"],
            retrieved_chunks=_chunks(NEUTRAL_CHUNK),
        ).declined
        for answer in RESIDUAL_IMPLICATION
    ]

    # Residual: 8/8 implication-only forms have no commitment word and are not
    # caught by a predicate-based guard. The number is the acceptance record.
    assert sum(declined) == 0


def test_published_axes_are_populated() -> None:
    assert len(SUBJECT_FORMS) >= 6
    assert len(COMMITMENT_PREDICATES) >= 10
    assert len(PROSPECT_REFERENCES) >= 10
    assert len(UNGROUNDED_ANSWERS) >= 8
