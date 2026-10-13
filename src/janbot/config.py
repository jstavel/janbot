"""Configuration for JanBot, read from ``JANBOT_*`` environment variables.

Per AD-5, model mode is configuration, not code. This module is stdlib-only and
reads eight variables, each with a documented default:

- ``JANBOT_MODEL_MODE``      -- ``"eval"`` (default) or ``"production"``
- ``JANBOT_MODEL_SNAPSHOT``  -- locked model snapshot;
  default ``"openai/gpt-4o-mini-2024-07-18"``
- ``JANBOT_CORPUS_PATH``     -- indexed corpus root; default ``"public_profile_org"``
- ``JANBOT_INDEX_PATH``      -- vector index location; default ``"chroma_db"``
- ``JANBOT_PROJECT_ROOT``    -- base for relative paths; default is the repository
  root derived from this file's location
- ``JANBOT_TEMPERATURE``     -- LM sampling temperature; default ``0.0``
- ``JANBOT_SEED``            -- eval determinism seed; default ``0``
- ``JANBOT_TOP_K``           -- retrieval top-k; default ``3``

Values are trimmed, and a blank or whitespace-only value counts as unset (so it
takes the documented default). The model mode is normalized to lower case before
validation, so ``"Production"`` and ``" production "`` are accepted.
``JANBOT_TEMPERATURE`` must parse as a number, ``JANBOT_SEED`` must parse as an
integer, and ``JANBOT_TOP_K`` must be a positive integer; a value that violates
any clause fails fast with a ``ValueError`` naming the variable. Paths are
``~``-expanded and, when still relative, resolved against
the project root, then canonicalized to absolute paths, so no path depends on
the process CWD.

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
PROJECT_ROOT_ENV = "JANBOT_PROJECT_ROOT"
TEMPERATURE_ENV = "JANBOT_TEMPERATURE"
SEED_ENV = "JANBOT_SEED"
TOP_K_ENV = "JANBOT_TOP_K"

DEFAULT_MODEL_MODE = MODEL_MODE_EVAL
DEFAULT_MODEL_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"
DEFAULT_CORPUS_PATH = "public_profile_org"
DEFAULT_INDEX_PATH = "chroma_db"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 0
DEFAULT_TOP_K = 3

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    """Resolved JanBot configuration."""

    model_mode: str
    model_snapshot: str
    corpus_path: Path
    index_path: Path
    temperature: float
    seed: int
    top_k: int


def _clean(value: str | None) -> str | None:
    """Trim ``value``; return ``None`` when it is unset or blank."""
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _resolve_path(value: str, root: Path) -> Path:
    """Expand ``~`` and resolve ``value`` beneath ``root`` to an absolute path."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from ``env`` (defaults to ``os.environ``).

    Raises:
        ValueError: if ``JANBOT_MODEL_MODE`` is not one of ``MODEL_MODES``, or
            if ``JANBOT_TEMPERATURE``/``JANBOT_SEED``/``JANBOT_TOP_K`` is set
            to an invalid value.
    """
    source = os.environ if env is None else env

    raw_mode = _clean(source.get(MODEL_MODE_ENV))
    model_mode = DEFAULT_MODEL_MODE if raw_mode is None else raw_mode.lower()
    if model_mode not in MODEL_MODES:
        allowed = ", ".join(repr(mode) for mode in MODEL_MODES)
        raise ValueError(
            f"{MODEL_MODE_ENV}={raw_mode!r} is invalid; allowed values: {allowed}"
        )

    model_snapshot = _clean(source.get(MODEL_SNAPSHOT_ENV)) or DEFAULT_MODEL_SNAPSHOT

    raw_temperature = _clean(source.get(TEMPERATURE_ENV))
    if raw_temperature is None:
        temperature = DEFAULT_TEMPERATURE
    else:
        try:
            temperature = float(raw_temperature)
        except ValueError as exc:
            raise ValueError(
                f"{TEMPERATURE_ENV}={raw_temperature!r} is not a number"
            ) from exc

    raw_seed = _clean(source.get(SEED_ENV))
    if raw_seed is None:
        seed = DEFAULT_SEED
    else:
        try:
            seed = int(raw_seed)
        except ValueError as exc:
            raise ValueError(
                f"{SEED_ENV}={raw_seed!r} is not an integer"
            ) from exc

    raw_top_k = _clean(source.get(TOP_K_ENV))
    if raw_top_k is None:
        top_k = DEFAULT_TOP_K
    else:
        try:
            top_k = int(raw_top_k)
        except ValueError as exc:
            raise ValueError(
                f"{TOP_K_ENV}={raw_top_k!r} is not an integer"
            ) from exc
        if top_k < 1:
            raise ValueError(
                f"{TOP_K_ENV}={raw_top_k!r} must be a positive integer"
            )

    raw_root = _clean(source.get(PROJECT_ROOT_ENV))
    project_root = _resolve_path(raw_root, PROJECT_ROOT) if raw_root else PROJECT_ROOT

    corpus_value = _clean(source.get(CORPUS_PATH_ENV)) or DEFAULT_CORPUS_PATH
    index_value = _clean(source.get(INDEX_PATH_ENV)) or DEFAULT_INDEX_PATH

    return Config(
        model_mode=model_mode,
        model_snapshot=model_snapshot,
        corpus_path=_resolve_path(corpus_value, project_root),
        index_path=_resolve_path(index_value, project_root),
        temperature=temperature,
        seed=seed,
        top_k=top_k,
    )
