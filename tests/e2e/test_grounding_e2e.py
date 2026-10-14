"""The grounding boundary through the running service (keyless).

Two rows prove at the port what the in-process tests prove inside:

- an index built from a different corpus root holds an out-of-scope chunk, so
  the goal-5 startup check refuses to serve it — the process exits non-zero and
  its log names the out-of-scope count (a served insufficiency reply would not
  prove the boundary, because the service never gets to serve);
- a sourceless-only index starts, but every question retrieves nothing *in*
  corpus, so ``POST /chat`` answers ``200`` with ``status="insufficient"`` and no
  citations (empty retrieval, before any model call).

The crafted indexes come from ``make_index.py`` run as a subprocess, so this
module imports no ``janbot`` internals — ``httpx``, ``pytest`` and the standard
library only.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx


def test_foreign_index_refuses_to_start(
    foreign_index: Path,
    start_service_expecting_exit: Callable[[Path], tuple[int, str]],
) -> None:
    returncode, log_text = start_service_expecting_exit(foreign_index)

    assert returncode != 0, f"the service served a foreign index; log:\n{log_text}"
    assert "1 chunk(s) whose source_path lies outside" in log_text, (
        f"the startup refusal did not name the out-of-scope count; log:\n{log_text}"
    )
    assert "refusing to start" in log_text, f"log:\n{log_text}"


def test_sourceless_index_returns_200_insufficiency(
    sourceless_service_base_url: str,
) -> None:
    response = httpx.post(
        f"{sourceless_service_base_url}/chat",
        json={"question": "anything"},
        timeout=30.0,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "insufficient"
    assert body["citations"] == []
    assert body["answer"]
