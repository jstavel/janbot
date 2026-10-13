"""Shared, ``janbot``-free helpers for the port-only e2e modules.

Test modules cannot import ``conftest.py`` by name, so the constants and the
error-envelope assertion the modules share live here instead. Nothing here
imports ``janbot`` internals — the e2e tree stays reachable only over HTTP.
"""

from __future__ import annotations

import httpx

# The one question the keyed rows post (the happy path and the determinism row).
QUESTION = "What search infrastructure has Jan worked on?"

# The model key the keyed rows need; both modes route through OpenRouter.
MODEL_KEY_ENV = "OPENROUTER_API_KEY"


def assert_detail_string(response: httpx.Response, status: int) -> str:
    """Assert ``status`` with a non-empty ``{detail: <str>}`` envelope; return the detail."""
    assert response.status_code == status, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str) and detail, "the detail must be a non-empty string"
    return detail
