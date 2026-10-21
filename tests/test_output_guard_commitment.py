"""Narrowed commitment control sweep (ADR-010 Amendment 4).

The control is **not** "every first-person commitment or interest claim". It is:

1. actionable commitments on Jan's behalf — availability, start/notice,
   compensation, accepting an offer, relocation/travel;
2. interest attributed to the prospect's company (named or deictic).

Generic enthusiasm or politeness, topic interest and role interest are out of
scope and are served. The generated products below are a regression of the
published axes, not proof of the class: **a sweep generated from the
implementation's own axes cannot fail** (it tests cross-product completeness).
The acceptance record carries the independent measurements: 5/12 (iteration 1),
14/64 on foreign vocabulary (iterations 2/3), 8/8 implication-only.
"""

from __future__ import annotations

import itertools

import pytest

from janbot.guardrails.lexicon import (
    ACTIONABLE_COMMITMENTS,
    COMPANY_INTEREST_PREDICATES,
    COMPANY_REFERENCES,
    NAMED_COMPANIES,
    SUBJECT_FORMS,
)
from janbot.guardrails.output_guard import apply_output_guard

NEUTRAL_CHUNK = "Public profile of Jan Stavel. He builds search and testing systems."
LIVE_ANSWER = (
    "Yes, I'd be interested. I'm drawn to a workplace where people have the "
    "freedom to contribute thought."
)

ACTIONABLE_CELLS = tuple(
    f"{subject} {predicate.lead}"
    for subject, predicate in itertools.product(
        SUBJECT_FORMS, ACTIONABLE_COMMITMENTS
    )
)
COMPANY_CELLS = tuple(
    f"{subject} {predicate.lead} {reference.phrase}"
    for subject, predicate, reference in itertools.product(
        SUBJECT_FORMS, COMPANY_INTEREST_PREDICATES, COMPANY_REFERENCES
    )
)
NAMED_COMPANY_CELLS = tuple(
    f"{subject} {predicate.lead} {company}"
    for subject, predicate, company in itertools.product(
        SUBJECT_FORMS, COMPANY_INTEREST_PREDICATES, NAMED_COMPANIES
    )
)
UNGROUNDED_CELLS = ACTIONABLE_CELLS + COMPANY_CELLS + NAMED_COMPANY_CELLS
GROUNDED_CELLS = tuple(
    f"I'm {predicate.lead} {reference.phrase}"
    for predicate, reference in itertools.product(
        COMPANY_INTEREST_PREDICATES, COMPANY_REFERENCES
    )
)
GROUNDED_ACTIONABLE = tuple(
    f"I'm {predicate.lead}" for predicate in ACTIONABLE_COMMITMENTS
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

OUT_OF_SCOPE = (
    "Yes, I'd be interested.",
    "Sounds great.",
    "I'd be glad to talk.",
    LIVE_ANSWER,
    "I'm interested in trading systems and distributed testing.",
    "I'm interested in the role.",
    "I'd love to be part of the trading community.",
    "I'm interested in what you do.",
)


def _chunks(text: str) -> list[dict[str, str]]:
    return [{"source": "profile.org", "text": text}]


@pytest.mark.parametrize("answer", UNGROUNDED_CELLS)
def test_every_ungrounded_actionable_or_company_cell_is_declined(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is True
    assert result.rule == "commitment-claim"


@pytest.mark.parametrize("answer", GROUNDED_ACTIONABLE + GROUNDED_CELLS)
def test_a_supporting_chunk_keeps_the_same_cell(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(answer),
    )

    assert result.declined is False
    assert result.answer == answer


@pytest.mark.parametrize("answer", OUT_OF_SCOPE)
def test_generic_enthusiasm_politeness_and_topic_interest_are_served(
    answer: str,
) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is False
    assert result.answer == answer


@pytest.mark.parametrize(
    ("answer", "chunk"),
    (
        ("My notice period is two months.", "My notice period is two months."),
        ("I expect a salary of 80,000 EUR.", "I expect a salary of 80,000 EUR."),
        ("I can start next month.", "I can start next month."),
        ("I'm willing to relocate.", "I'm willing to relocate."),
        ("I can travel.", "I can travel."),
    ),
)
def test_actionable_commitments_are_caught_and_can_be_grounded(
    answer: str, chunk: str
) -> None:
    ungrounded = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )
    grounded = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(chunk),
    )

    assert ungrounded.declined is True
    assert grounded.declined is False


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
    # caught by a marker/reference predicate. The number is the acceptance record.
    assert sum(declined) == 0


def test_published_axes_are_populated() -> None:
    assert len(SUBJECT_FORMS) == 6
    assert len(ACTIONABLE_COMMITMENTS) >= 10
    assert len(COMPANY_INTEREST_PREDICATES) >= 10
    assert len(COMPANY_REFERENCES) >= 10
    assert len(NAMED_COMPANIES) >= 3
    assert len(UNGROUNDED_CELLS) >= 100
