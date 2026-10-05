"""Configuration for JanBot, read from ``JANBOT_*`` environment variables.

Per AD-5, model mode is configuration, not code. This module is stdlib-only and
reads four variables, each with a documented default:

- ``JANBOT_MODEL_MODE``      -- ``"eval"`` (default) or ``"production"``
- ``JANBOT_MODEL_SNAPSHOT``  -- locked model snapshot;
  default ``"openai/gpt-4o-mini-2024-07-18"``
- ``JANBOT_CORPUS_PATH``     -- indexed corpus root; default ``"public_profile_org"``
- ``JANBOT_INDEX_PATH``      -- vector index location; default ``"chroma_db"``

No secrets are read here; the OpenRouter key is a later, separately-managed
concern. Configuration is environment-only (no ``.env`` or config-file support).

``load_config`` accepts an optional mapping so tests can supply an environment
without mutating process state; when omitted it reads ``os.environ``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

MODEL_MODE_EVAL = "eval"
MODEL_MODE_PRODUCTION = "production"
MODEL_MODES = (MODEL_MODE_EVAL, MODEL_MODE_PRODUCTION)

MODEL_MODE_ENV = "JANBOT_MODEL_MODE"
MODEL_SNAPSHOT_ENV = "JANBOT_MODEL_SNAPSHOT"
CORPUS_PATH_ENV = "JANBOT_CORPUS_PATH"
INDEX_PATH_ENV = "JANBOT_INDEX_PATH"

DEFAULT_MODEL_MODE = MODEL_MODE_EVAL
DEFAULT_MODEL_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"
DEFAULT_CORPUS_PATH = "public_profile_org"
DEFAULT_INDEX_PATH = "chroma_db"


@dataclass(frozen=True)
class Config:
    """Resolved JanBot configuration."""

    model_mode: str
    model_snapshot: str
    corpus_path: Path
    index_path: Path


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from ``env`` (defaults to ``os.environ``).

    Raises:
        ValueError: if ``JANBOT_MODEL_MODE`` is not one of ``MODEL_MODES``.
    """
    source = os.environ if env is None else env

    model_mode = source.get(MODEL_MODE_ENV, DEFAULT_MODEL_MODE)
    if model_mode not in MODEL_MODES:
        allowed = ", ".join(repr(mode) for mode in MODEL_MODES)
        raise ValueError(
            f"{MODEL_MODE_ENV}={model_mode!r} is invalid; allowed values: {allowed}"
        )

    return Config(
        model_mode=model_mode,
        model_snapshot=source.get(MODEL_SNAPSHOT_ENV, DEFAULT_MODEL_SNAPSHOT),
        corpus_path=Path(source.get(CORPUS_PATH_ENV, DEFAULT_CORPUS_PATH)),
        index_path=Path(source.get(INDEX_PATH_ENV, DEFAULT_INDEX_PATH)),
    )
