"""Narrowed commitment control sweep (ADR-010 Amendments 4 and 5).

The control is **not** "every first-person commitment or interest claim". It is:

1. actionable commitments on Jan's behalf — availability, start/notice,
   compensation, accepting an offer, relocation/travel;
2. interest attributed to the prospect's company (named or deictic).

Generic enthusiasm or politeness, topic interest and role interest are out of
scope and are served. What counts is **what the interest is attached to**
(Amendment 5): a role/position is not a party reference, and the named-company
detector ignores technologies, places and discourse words — the live
`janbot-api-00007-xjj` answer to "Are you interested in this role?" was declined
as `commitment-claim` because "AI-assisted" was read as the prospect's company.
The generated products below are a regression of the published axes, not proof
of the class: **a sweep generated from the implementation's own axes cannot
fail** (it tests cross-product completeness). The acceptance record carries the
independent measurements: 5/12 (iteration 1), 14/64 on foreign vocabulary
(iterations 2/3), 8/8 implication-only.
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
LIVE_00007_ANSWER = (
    "Yes, I\u2019m interested in roles where I can help set direction, guide and "
    "review the work, and break it into small, manageable steps. I\u2019m especially "
    "interested in applying an architect\u2019s mindset to AI-assisted workflows, "
    "where the AI can generate while I remain responsible for decisions and quality. "
    "If the role requires deep VPN or Layer 3 networking expertise, I\u2019d want to "
    "discuss that fit, since that isn\u2019t an area I\u2019ve mastered."
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

# Amendment 5 (2026-10-21): role-attributed interest is served even when the
# clause carries tokens the named-company detector could misread as the
# prospect's company; party attribution keeps declining. The live cell is the
# `openrouter/auto` answer reproduced from the `janbot-api-00007-xjj` decline.
ROLE_INTEREST_SERVED = (
    LIVE_00007_ANSWER,
    "I'm especially interested in applying an architect's mindset to AI-assisted workflows, where the AI can generate while I remain responsible for decisions and quality.",
    "Yes, I'm interested in roles where I can help set direction, steer the work, review results, and plan in small, bounded steps.",
    "Certainly, I'm interested in this role.",
    "I'm interested in the role in Prague.",
    "I'm interested in this role even though deep VPN and IPsec are not areas I've mastered.",
)

PARTY_INTEREST_COVERED = (
    "I'd be interested in working with you.",
    "I'd love to join your team.",
    "I am interested in working for your company.",
    "I'm interested in Kraken.",
    "I'm excited to join Kraken.",
    "That's the company I'm interested in.",
    "I want to work there.",
    "I'm interested in this role and in joining your team.",
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


@pytest.mark.parametrize("answer", ROLE_INTEREST_SERVED)
def test_role_attributed_interest_is_served_even_with_pseudo_companies(
    answer: str,
) -> None:
    """ADR-010 Amendment 5: interest attached to a role/position is served.

    The live cell is the reproduced `janbot-api-00007-xjj` answer to
    "Are you interested in this role?" — declined as `commitment-claim` because
    "AI-assisted" was read as the prospect's company.
    """
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is False
    assert result.answer == answer


@pytest.mark.parametrize("answer", PARTY_INTEREST_COVERED)
def test_party_attributed_interest_still_declines(answer: str) -> None:
    """Amendment 5 did not relax party attribution: company/team/party stays covered."""
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(NEUTRAL_CHUNK),
    )

    assert result.declined is True
    assert result.rule == "commitment-claim"


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
