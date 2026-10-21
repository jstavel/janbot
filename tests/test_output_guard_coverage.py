"""Measured per-category coverage for ADR-010 Amendment 4.

This is the probe set behind the coverage table in the ADR and the runbook. It
is deliberately small and hand-picked per category: the control is best-effort
by owner decision, so the record states how much is covered (and names the
misses as residual) instead of claiming the category is complete.
"""

from __future__ import annotations

import pytest

from janbot.guardrails.output_guard import apply_output_guard

NEUTRAL_CHUNK = "Public profile of Jan Stavel. He builds search and testing systems."

CATEGORIES = {
    "availability/start/notice": (
        "I am available immediately.",
        "I can start next month.",
        "My notice period is two months.",
    ),
    "compensation": (
        "My salary expectation is 120k.",
        "I would accept 100k CZK gross.",
        "I need at least 90k.",
        "My expected compensation is 120k.",
        "I expect 100k gross.",
    ),
    "accepting an offer": ("I accept the offer.",),
    "relocation": ("I am willing to relocate.",),
    "travel": (
        "I am willing to travel.",
        "I can travel.",
        "I am able to travel.",
        "I am happy to travel two days a week.",
        "I can commute to Brno once a week.",
    ),
}

EXPECTED = {
    "availability/start/notice": 3,
    "compensation": 1,
    "accepting an offer": 1,
    "relocation": 1,
    "travel": 3,
}


def _declined(answer: str) -> bool:
    return apply_output_guard(
        answer=answer,
        citations=["profile.org"],
        retrieved_chunks=[{"source": "profile.org", "text": NEUTRAL_CHUNK}],
    ).declined


@pytest.mark.parametrize("category", tuple(CATEGORIES))
def test_category_coverage_matches_the_recorded_number(category: str) -> None:
    probes = CATEGORIES[category]
    covered = sum(1 for answer in probes if _declined(answer))

    assert covered == EXPECTED[category]


def test_compensation_and_travel_misses_are_named_residuals() -> None:
    missed = [
        answer
        for category in ("compensation", "travel")
        for answer in CATEGORIES[category]
        if not _declined(answer)
    ]

    assert missed == [
        "I would accept 100k CZK gross.",
        "I need at least 90k.",
        "My expected compensation is 120k.",
        "I expect 100k gross.",
        "I am happy to travel two days a week.",
        "I can commute to Brno once a week.",
    ]
