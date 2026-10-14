"""Contract & request-validation coverage over the HTTP port (keyless).

The running service (a real subprocess, see ``conftest.py``) is asked malformed
questions and, separately, is started against an empty index; the former returns
FastAPI's standard ``{detail}`` validation envelope, while the latter declines
with a ``200`` insufficiency reply. It imports no ``janbot`` internals and needs
no model key: ``422`` is request validation and the decline is empty retrieval,
both raised before any model call.
"""

from __future__ import annotations

import httpx
import pytest

MALFORMED_BODIES = [
    pytest.param({}, id="missing"),
    pytest.param({"question": 123}, id="non-string"),
    pytest.param({"question": "   "}, id="blank"),
]


@pytest.mark.parametrize("body", MALFORMED_BODIES)
def test_malformed_question_is_rejected_with_422_envelope(
    empty_service_base_url: str, body: dict[str, object]
) -> None:
    # Request validation is independent of the index, so the empty-index service
    # keeps this row model-free (no fixture-index build).
    response = httpx.post(f"{empty_service_base_url}/chat", json=body, timeout=30.0)

    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail, "FastAPI validation detail must be a non-empty list"


def test_empty_index_returns_200_insufficiency(
    empty_service_base_url: str,
) -> None:
    response = httpx.post(
        f"{empty_service_base_url}/chat", json={"question": "anything"}, timeout=30.0
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "insufficient"
    assert body["citations"] == []
    assert body["answer"]
