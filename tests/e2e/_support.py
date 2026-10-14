"""Shared, ``janbot``-free values for the port-only e2e modules.

Test modules cannot import ``conftest.py`` by name, so the constants the modules
share live here instead. Nothing here imports ``janbot`` internals — the e2e tree
stays reachable only over HTTP.
"""

from __future__ import annotations

# The one question the keyed rows post (the happy path and the determinism row).
QUESTION = "What search infrastructure has Jan worked on?"

# The model key the keyed rows need; both modes route through OpenRouter.
MODEL_KEY_ENV = "OPENROUTER_API_KEY"
