"""Independent commitment/interest paraphrase battery (authored before the predicate).

These formulations were written from the class description — a first-person
commitment or interest in the prospect (working for / joining / being interested
in their company, team, role) — not derived from the live answer string. The
guard must refuse the claim or decline the answer unless a cited chunk supports
it. The must-not-regress cases pin topic interest, grounded capability, grounded
values and the Clojure control.
"""

from __future__ import annotations

import pytest

from janbot.guardrails.lexicon import COMMITMENT_MARKERS, PARTY_TOKENS
from janbot.guardrails.output_guard import apply_output_guard

PLAIN_CHUNK = "Public profile of Jan Stavel. He builds search and testing systems."

COMMITMENT_ANSWERS = (
    "I'd be keen to join your team.",
    "I'm genuinely excited about the opportunity to work for your company.",
    "Working for your organisation would suit me well.",
    "I'd be interested in the position you're hiring for.",
    "I want to be considered for this role.",
    "I'm open to joining your team.",
    "I can start immediately if you make an offer.",
    "I'd accept an offer from your company.",
    "Joining your team would be a privilege.",
    "Sign me up — I'd be glad to come aboard.",
    "I'd love to be part of your organisation.",
    "I'm attracted to your company's mission.",
)


def _chunks(text: str) -> list[dict[str, str]]:
    return [{"source": "profile.org", "text": text}]


@pytest.mark.parametrize("answer", COMMITMENT_ANSWERS)
def test_commitment_or_interest_claim_is_declined(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(PLAIN_CHUNK),
    )

    assert result.declined is True
    assert result.rule == "commitment-claim"


@pytest.mark.parametrize(
    "answer",
    (
        "I'm interested in trading systems and distributed testing.",
        "I'm interested in learning more about distributed testing.",
    ),
)
def test_interest_in_a_topic_is_not_declined(answer: str) -> None:
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(PLAIN_CHUNK),
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


def test_grounded_commitment_statement_is_kept() -> None:
    answer = "I am interested in working for your company."
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(answer),
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


def test_commitment_lexicon_is_declared() -> None:
    assert COMMITMENT_MARKERS
    assert PARTY_TOKENS
    assert all(len(marker) == 3 for marker in COMMITMENT_MARKERS)


def test_live_acceptance_string_is_declined() -> None:
    """Regression case, recorded after the battery: the live janbot-api-00005-xqs answer."""
    answer = (
        "Yes, I'd be interested. I'm drawn to a workplace where people have the "
        "freedom to contribute thought."
    )
    result = apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=_chunks(PLAIN_CHUNK),
    )

    assert result.declined is True
    assert result.rule == "commitment-claim"
