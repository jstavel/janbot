"""Schema-level pins for the ``/chat`` contract (AD-4).

The contract models reject malformed values by themselves — before any route,
program, or retrieval runs. These tests pin that self-validation directly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from janbot.api.contract import ChatRequest, ChatResponse, Citation


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


def test_chat_response_rejects_zero_citations() -> None:
    with pytest.raises(ValidationError) as excinfo:
        ChatResponse(answer="An answer.", citations=[])

    assert "citations" in str(excinfo.value)


def test_chat_response_valid_construction_conforms() -> None:
    response = ChatResponse(
        answer="Search infrastructure.",
        citations=[Citation(source="profile.org")],
    )

    assert response.answer == "Search infrastructure."
    assert response.citations[0].source == "profile.org"


def test_chat_response_missing_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ChatResponse(answer="An answer.")
