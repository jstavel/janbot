"""Contract self-test over the committed ``/chat`` response fixture.

A committed fixture pins the exact JSON a caller receives, so the self-test
validates the wire shape through ``ChatResponse`` rather than a Python object
literal. The CI ``contract-negative`` job mutates this fixture and requires the
run to go red, proving the check is not vacuous.

The test is keyless and in-process: it imports the contract models and standard
validation only — no service, no model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from janbot.api.contract import ChatResponse

FIXTURE = Path(__file__).parent / "fixtures" / "chat_response.json"


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def test_response_fixture_validates_unchanged() -> None:
    response = ChatResponse.model_validate(_load_fixture())

    assert response.answer
    assert len(response.citations) >= 1


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload.update(citations=[]),
        lambda payload: payload.pop("answer"),
        lambda payload: payload.update(answer=123),
        lambda payload: payload.update(citations=["profile.org"]),
    ],
    ids=["empty-citations", "missing-answer", "mistyped-answer", "mistyped-citations"],
)
def test_malformed_response_is_rejected(mutation) -> None:
    payload = _load_fixture()
    mutation(payload)

    with pytest.raises(ValidationError):
        ChatResponse.model_validate(payload)
