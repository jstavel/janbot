"""Schema-level pins for the ``/chat`` contract (AD-4).

The contract models reject malformed values by themselves — before any route,
program, or retrieval runs. These tests pin that self-validation directly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from janbot.api.contract import (
    INSUFFICIENT_ANSWER,
    ChatRequest,
    ChatResponse,
    Citation,
)


def test_chat_request_strips_surrounding_whitespace() -> None:
    request = ChatRequest(question="  What have you built?  ")

    assert request.question == "What have you built?"


@pytest.mark.parametrize("question", ["", "   ", "\t\n"], ids=["empty", "spaces", "tabs"])
def test_chat_request_blank_question_is_rejected(question: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatRequest(question=question)

    assert "question must not be blank" in str(excinfo.value)


def test_chat_request_missing_question_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatRequest()

    assert "question" in str(excinfo.value)


def test_chat_request_mistyped_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(question=123)


def test_chat_response_answered_without_citations_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatResponse(answer="An answer.", citations=[])

    assert "an answered response requires at least one citation" in str(excinfo.value)


def test_chat_response_insufficient_without_citations_is_valid() -> None:
    response = ChatResponse(
        status="insufficient",
        answer=INSUFFICIENT_ANSWER,
        citations=[],
    )

    assert response.status == "insufficient"
    assert response.answer == INSUFFICIENT_ANSWER
    assert response.citations == []


def test_chat_response_insufficient_with_citations_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatResponse(
            status="insufficient",
            answer=INSUFFICIENT_ANSWER,
            citations=[Citation(source="profile.org")],
        )

    assert "an insufficient response must not carry citations" in str(excinfo.value)


def test_chat_response_unknown_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatResponse(status="maybe", answer="An answer.", citations=[Citation(source="profile.org")])


def test_chat_response_valid_construction_conforms() -> None:
    response = ChatResponse(
        answer="Search infrastructure.",
        citations=[Citation(source="profile.org")],
    )

    assert response.status == "answered"
    assert response.answer == "Search infrastructure."
    assert response.citations[0].source == "profile.org"


def test_answered_response_without_citations_is_rejected() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatResponse(answer="An answer.")

    assert "an answered response requires at least one citation" in str(excinfo.value)
