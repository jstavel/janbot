"""Determinism at the locked snapshot over the HTTP port (keyed).

Two cache-cold eval service runs — each a fresh subprocess with its own
``DSPY_CACHEDIR`` and pinned config (temperature ``0``, seed ``0``, snapshot
``openai/gpt-4o-mini-2024-07-18``) — are each posted the same question exactly
once. Because every run starts cache-cold, its single ``POST /chat`` is a real
generation, not a DSPy response-cache hit; byte-identical response bodies then
prove the *shipped service generates* the same answer, which is the property the
adapter-level tests cannot show. It imports no ``janbot`` internals — ``httpx``,
``pytest`` and the standard library only.

The real eval snapshot answers through ``dspy``/LiteLLM, which reads
``OPENAI_API_KEY``; without a key the row is skipped cleanly, never failed.
"""

from __future__ import annotations

import os
from collections.abc import Callable
from contextlib import AbstractContextManager

import httpx
import pytest

OPENAI_API_KEY_ENV = "OPENAI_API_KEY"

QUESTION = "What search infrastructure has Jan worked on?"


@pytest.mark.skipif(
    not (os.environ.get(OPENAI_API_KEY_ENV) or "").strip(),
    reason=f"{OPENAI_API_KEY_ENV} is not set: the determinism e2e row is skipped",
)
def test_two_cold_runs_generate_byte_identical_bodies(
    cold_service: Callable[[], AbstractContextManager[str]],
) -> None:
    def generate() -> bytes:
        with cold_service() as base_url:
            response = httpx.post(
                f"{base_url}/chat",
                json={"question": QUESTION},
                timeout=120.0,
            )
        assert response.status_code == 200, response.text
        return response.content

    first = generate()
    second = generate()

    assert first == second, (
        "two cache-cold generations of the same question differ:\n"
        f"first:  {first!r}\n"
        f"second: {second!r}"
    )
