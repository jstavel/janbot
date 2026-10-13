"""The keyed happy path over the HTTP port: the tracer-bullet proof.

The service is a real subprocess (see ``conftest.py``); this module posts a
question to ``POST /chat`` and asserts the shipped contract: ``200`` with an
``answer`` and at least one corpus-relative citation. It imports no ``janbot``
internals — ``httpx``, ``pytest`` and the standard library only.

The real-model answer needs a model key (the ``eval`` snapshot
``openai/gpt-4o-mini-2024-07-18`` is served through ``dspy``/LiteLLM, which reads
``OPENROUTER_API_KEY``). Without one the happy path is *skipped*, never failed, so a
keyless run (CI) stays green.
"""

from __future__ import annotations

import os

import httpx
import pytest

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"

QUESTION = "What search infrastructure has Jan worked on?"


@pytest.mark.skipif(
    not (os.environ.get(OPENROUTER_API_KEY_ENV) or "").strip(),
    reason=f"{OPENROUTER_API_KEY_ENV} is not set: the real-model e2e happy path is skipped",
)
def test_chat_returns_grounded_answer_with_corpus_relative_citation(
    service_base_url: str,
) -> None:
    response = httpx.post(
        f"{service_base_url}/chat",
        json={"question": QUESTION},
        timeout=120.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert isinstance(body["answer"], str)
    assert body["answer"].strip()

    citations = body["citations"]
    assert citations, "expected at least one citation"
    for citation in citations:
        source = citation["source"]
        assert isinstance(source, str) and source
        assert not source.startswith("/"), f"citation is not corpus-relative: {source!r}"
