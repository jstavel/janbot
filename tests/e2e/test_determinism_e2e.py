"""Grounding determinism at the locked snapshot over the HTTP port (keyed).

Two cache-cold eval service runs — each a fresh subprocess with its own
``DSPY_CACHEDIR`` and pinned config (temperature ``0``, seed ``0``, snapshot
``openai/gpt-4o-mini-2024-07-18``) — are each posted the same question exactly
once. Because every run starts cache-cold, its single ``POST /chat`` is a real
generation, not a DSPy response-cache hit.

The provider does **not** guarantee byte-identical answer text at temperature 0:
``gpt-4o-mini`` varies its wording run to run (observed: ``…and evaluation before
starting JanBot.`` vs ``…and evaluation.``). Determinism is therefore asserted at
the layer the service controls — the same question is **grounded in the same
corpus sources** (retrieval is deterministic; citations are emitted in retrieval
order, ``pipeline/chat.py``) and each run returns a well-formed
``{answer, citations}`` body — not on the wording the model does not fix. It
imports no ``janbot`` internals — ``httpx``, ``pytest`` and the standard library
only.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager
from typing import Any

import httpx
import pytest

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

QUESTION = "What search infrastructure has Jan worked on?"


def _assert_grounded_response(body: dict[str, Any]) -> None:
    """Assert a well-formed grounded body: non-empty answer, corpus-relative citations."""
    answer = body["answer"]
    assert isinstance(answer, str) and answer.strip(), "the answer must be non-empty"

    citations = body["citations"]
    assert citations, "expected at least one citation"
    for citation in citations:
        source = citation["source"]
        assert isinstance(source, str) and source
        assert not source.startswith("/"), f"citation is not corpus-relative: {source!r}"


def _sources(body: dict[str, Any]) -> list[str]:
    return [citation["source"] for citation in body["citations"]]


@pytest.mark.skipif(
    not (os.environ.get(OPENAI_API_KEY_ENV) or "").strip(),
    reason=f"{OPENAI_API_KEY_ENV} is not set: the determinism e2e row is skipped",
)
def test_two_cold_runs_ground_the_answer_in_the_same_sources(
    cold_service: Callable[[], AbstractContextManager[str]],
) -> None:
    def generate() -> dict[str, Any]:
        with cold_service() as base_url:
            response = httpx.post(
                f"{base_url}/chat",
                json={"question": QUESTION},
                timeout=120.0,
            )
        assert response.status_code == 200, response.text
        return response.json()

    first = generate()
    second = generate()

    _assert_grounded_response(first)
    _assert_grounded_response(second)

    assert _sources(first) == _sources(second), (
        "two cache-cold runs grounded the same question in different sources:\n"
        f"first:  {first}\n"
        f"second: {second}"
    )
