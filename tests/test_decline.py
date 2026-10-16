"""Unit tests for the deterministic decline-reason classifier.

The classifier selects the decline reason — ``personal`` or ``out_of_corpus`` —
from a recorded HR/screening lexicon, with no model call, so it is deterministic
and auditable. These tests pin the personal triggers, the fail-open default for
unlisted questions, and that the same question always yields the same reason.
"""

from __future__ import annotations

import pytest

from janbot.api.contract import decline
from janbot.api.decline import classify_decline_reason

PERSONAL_QUESTIONS = [
    "What is your salary expectation?",
    "What is your notice period?",
    "Are you willing to relocate to another country?",
    "Do you hold a security clearance?",
    "Do you have any dietary restrictions?",
    "Do you have a driving licence?",
    "Do you have a driver's license?",
    "Do you have any children?",
    "What is your religion?",
    "What is your marital status?",
    "What is your date of birth?",
    "Have you ever been arrested?",
    "Are you a smoker?",
]

OUT_OF_CORPUS_QUESTIONS = [
    "What is your favourite music genre?",
    "What search infrastructure have you built?",
    "How did you move from systems engineering into quality engineering?",
    "Have you done smoke testing on embedded firmware?",
    "Did you notice any performance difference after the migration?",
]


@pytest.mark.parametrize("question", PERSONAL_QUESTIONS)
def test_personal_hr_question_classifies_as_personal(question: str) -> None:
    assert classify_decline_reason(question) == "personal"


@pytest.mark.parametrize("question", OUT_OF_CORPUS_QUESTIONS)
def test_unlisted_question_falls_open_to_out_of_corpus(question: str) -> None:
    assert classify_decline_reason(question) == "out_of_corpus"


def test_classification_is_case_insensitive() -> None:
    assert classify_decline_reason("WHAT IS YOUR SALARY?") == "personal"


def test_classification_is_deterministic_across_calls() -> None:
    question = "Are you willing to relocate to another country?"

    assert classify_decline_reason(question) == classify_decline_reason(question)


def test_decline_reason_matches_the_classifier() -> None:
    assert decline("Are you a smoker?").reason == "personal"
    assert decline("What is your favourite music genre?").reason == "out_of_corpus"
