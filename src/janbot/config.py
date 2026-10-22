"""Configuration for JanBot, read from ``JANBOT_*`` environment variables.

Per AD-5, model mode is configuration, not code. This module is stdlib-only and
reads a documented set of variables, each with a default:

- ``JANBOT_MODEL_MODE``      -- ``"eval"`` (default) or ``"production"``
- ``JANBOT_MODEL_SNAPSHOT``  -- locked model snapshot;
  default ``"openai/gpt-4o-mini-2024-07-18"``
- ``JANBOT_JUDGE_MODEL``     -- LLM-as-a-judge model; default the locked snapshot
  in ``JANBOT_MODEL_SNAPSHOT`` (a stronger judge is a config change, not code)
- ``JANBOT_CORPUS_PATH``     -- indexed corpus root; default ``"public_profile_org"``
- ``JANBOT_INDEX_PATH``      -- vector index location; default ``"chroma_db"``
- ``JANBOT_PROGRAM_PATH``    -- compiled DSPy program (BootstrapFewShot output);
  default unset (no compiled program — the freshly built program runs)
- ``JANBOT_PROJECT_ROOT``    -- base for relative paths; default is the repository
  root derived from this file's location
- ``JANBOT_TEMPERATURE``     -- LM sampling temperature; default ``0.0``
- ``JANBOT_SEED``            -- eval determinism seed; default ``0``
- ``JANBOT_TOP_K``           -- retrieval top-k; default ``4``
- ``JANBOT_RETRIEVAL_MODE``  -- ``"dense"`` (default) or ``"hybrid"``
- ``JANBOT_RETRIEVAL_WINDOW`` -- ``"chunks"`` (default) or ``"sources"``
- ``JANBOT_RELEVANCE_THRESHOLD`` -- the low-relevance decline gate; default
  ``0.26`` (the measured value that raises ``refusal_pass_rate`` with no
  ``spurious_refusal_rate`` and no in-corpus regression). ``0.0`` disables the gate.
- ``JANBOT_OUTPUT_GUARD`` -- deterministic output guard; ``"on"`` (default,
  shipped) or ``"off"`` for measurement isolation. It never calls a model.
- ``JANBOT_GUARDRAILS``      -- the request guardrail layer; ``"on"`` (default) or
  ``"off"``. ``off`` is honoured only outside production: production + ``off``
  fails fast at startup.
- ``JANBOT_CACHE_PATH``      -- baked answer-cache artifact; default unset (no
  cache). The container image sets it to the build-time artifact.
- ``JANBOT_RATE_LIMIT``      -- requests per IP per window; default ``10``
- ``JANBOT_RATE_WINDOW_SECONDS`` -- per-IP rate window; default ``600`` (10 min)
- ``JANBOT_DAILY_QUOTA``     -- hard global model-call quota per UTC day; default
  ``500``
- ``JANBOT_MAX_QUESTION_CHARS`` -- maximum question length; default ``2000``
- ``JANBOT_MAX_BODY_BYTES``  -- maximum ``/chat`` request body; default ``8192``
- ``JANBOT_FIRESTORE_PROJECT`` -- GCP project for the shared counters; default
  unset. Production mode requires it.
- ``JANBOT_FIRESTORE_DATABASE`` -- Firestore native database id; default
  ``"(default)"``
- ``JANBOT_CORS_ORIGINS`` -- comma-separated exact origins allowed to call
  ``/chat`` from a browser (the ADR-008 CORS allowance); default unset, which
  adds no ``CORSMiddleware`` at all. Each entry is trimmed and must be an
  explicit ``http(s)://host[:port]`` origin — no ``*``, no path/query/fragment
  (a trailing slash included), no userinfo — and any other shape fails fast
  with a ``ValueError`` naming the variable. Blank = unset.

Values are trimmed, and a blank or whitespace-only value counts as unset (so it
takes the documented default). The model mode, the retrieval mode, the
retrieval window and the guardrail switch are normalized to lower case before validation, so
``"Production"`` and ``" production "`` (and ``"Hybrid"``, ``"Sources"``) are
accepted.
``JANBOT_TEMPERATURE`` must parse as a finite number, ``JANBOT_SEED`` must parse
as an integer, ``JANBOT_TOP_K`` must be a positive integer,
``JANBOT_RELEVANCE_THRESHOLD`` must parse as a finite number that is not negative,
and a value that violates
any clause fails fast with a ``ValueError`` naming the variable. Paths are
``~``-expanded and, when still relative, resolved against
the project root, then canonicalized to absolute paths, so no path depends on
the process CWD.

No secrets are read here; the OpenRouter key (``OPENROUTER_API_KEY``) is read
by the app, not by config. Configuration is environment-only (no ``.env`` or
config-file support).

``load_config`` accepts an optional mapping so tests can supply an environment
without mutating process state; when omitted it reads ``os.environ``.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

MODEL_MODE_EVAL = "eval"
MODEL_MODE_PRODUCTION = "production"
MODEL_MODES = (MODEL_MODE_EVAL, MODEL_MODE_PRODUCTION)

RETRIEVAL_MODE_DENSE = "dense"
RETRIEVAL_MODE_HYBRID = "hybrid"
RETRIEVAL_MODES = (RETRIEVAL_MODE_DENSE, RETRIEVAL_MODE_HYBRID)

RETRIEVAL_WINDOW_CHUNKS = "chunks"
RETRIEVAL_WINDOW_SOURCES = "sources"
RETRIEVAL_WINDOWS = (RETRIEVAL_WINDOW_CHUNKS, RETRIEVAL_WINDOW_SOURCES)

OUTPUT_GUARD_ON = "on"
OUTPUT_GUARD_OFF = "off"
OUTPUT_GUARDS = (OUTPUT_GUARD_ON, OUTPUT_GUARD_OFF)

GUARDRAILS_ON = "on"
GUARDRAILS_OFF = "off"
GUARDRAILS_MODES = (GUARDRAILS_ON, GUARDRAILS_OFF)

MODEL_MODE_ENV = "JANBOT_MODEL_MODE"
MODEL_SNAPSHOT_ENV = "JANBOT_MODEL_SNAPSHOT"
JUDGE_MODEL_ENV = "JANBOT_JUDGE_MODEL"
CORPUS_PATH_ENV = "JANBOT_CORPUS_PATH"
INDEX_PATH_ENV = "JANBOT_INDEX_PATH"
PROGRAM_PATH_ENV = "JANBOT_PROGRAM_PATH"
PROJECT_ROOT_ENV = "JANBOT_PROJECT_ROOT"
TEMPERATURE_ENV = "JANBOT_TEMPERATURE"
SEED_ENV = "JANBOT_SEED"
TOP_K_ENV = "JANBOT_TOP_K"
RETRIEVAL_MODE_ENV = "JANBOT_RETRIEVAL_MODE"
RETRIEVAL_WINDOW_ENV = "JANBOT_RETRIEVAL_WINDOW"
RELEVANCE_THRESHOLD_ENV = "JANBOT_RELEVANCE_THRESHOLD"
OUTPUT_GUARD_ENV = "JANBOT_OUTPUT_GUARD"
GUARDRAILS_ENV = "JANBOT_GUARDRAILS"
CACHE_PATH_ENV = "JANBOT_CACHE_PATH"
RATE_LIMIT_ENV = "JANBOT_RATE_LIMIT"
RATE_WINDOW_ENV = "JANBOT_RATE_WINDOW_SECONDS"
DAILY_QUOTA_ENV = "JANBOT_DAILY_QUOTA"
MAX_QUESTION_CHARS_ENV = "JANBOT_MAX_QUESTION_CHARS"
MAX_BODY_BYTES_ENV = "JANBOT_MAX_BODY_BYTES"
FIRESTORE_PROJECT_ENV = "JANBOT_FIRESTORE_PROJECT"
FIRESTORE_DATABASE_ENV = "JANBOT_FIRESTORE_DATABASE"
CORS_ORIGINS_ENV = "JANBOT_CORS_ORIGINS"

DEFAULT_MODEL_MODE = MODEL_MODE_EVAL
DEFAULT_MODEL_SNAPSHOT = "openai/gpt-4o-mini-2024-07-18"
DEFAULT_CORPUS_PATH = "public_profile_org"
DEFAULT_INDEX_PATH = "chroma_db"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_SEED = 0
DEFAULT_TOP_K = 4
DEFAULT_RETRIEVAL_MODE = RETRIEVAL_MODE_HYBRID
DEFAULT_RETRIEVAL_WINDOW = RETRIEVAL_WINDOW_CHUNKS
DEFAULT_RELEVANCE_THRESHOLD = 0.26
DEFAULT_OUTPUT_GUARD = OUTPUT_GUARD_ON
DEFAULT_GUARDRAILS = GUARDRAILS_ON
DEFAULT_RATE_LIMIT = 10
DEFAULT_RATE_WINDOW_SECONDS = 600
DEFAULT_DAILY_QUOTA = 500
DEFAULT_MAX_QUESTION_CHARS = 2000
DEFAULT_MAX_BODY_BYTES = 8192
DEFAULT_FIRESTORE_DATABASE = "(default)"

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Config:
    """Resolved JanBot configuration."""

    model_mode: str
    model_snapshot: str
    judge_model: str
    corpus_path: Path
    index_path: Path
    program_path: Path | None
    temperature: float
    seed: int
    top_k: int
    retrieval_mode: str
    retrieval_window: str
    relevance_threshold: float
    output_guard: str
    guardrails: str
    cache_path: Path | None
    rate_limit: int
    rate_window_seconds: int
    daily_quota: int
    max_question_chars: int
    max_body_bytes: int
    cors_origins: tuple[str, ...] | None
    firestore_project: str | None
    firestore_database: str


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


def _valid_origin(origin: str) -> bool:
    """True only for an explicit ``http(s)://host[:port]`` origin.

    ``*`` (standalone or as a host) would make Starlette's ``CORSMiddleware``
    allow every origin; a path, query, fragment or trailing slash is not an
    origin; userinfo is never part of one.
    """
    if "*" in origin:
        return False
    parts = urlsplit(origin)
    return (
        parts.scheme in ("http", "https")
        and parts.netloc != ""
        and "@" not in parts.netloc
        and parts.path == ""
        and parts.query == ""
        and parts.fragment == ""
    )


def load_config(env: Mapping[str, str] | None = None) -> Config:
    """Load configuration from ``env`` (defaults to ``os.environ``).

    Raises:
        ValueError: if ``JANBOT_MODEL_MODE`` is not one of ``MODEL_MODES``, if
            ``JANBOT_RETRIEVAL_MODE`` is not one of ``RETRIEVAL_MODES``, if
            ``JANBOT_RETRIEVAL_WINDOW`` is not one of ``RETRIEVAL_WINDOWS``, or
            if ``JANBOT_TEMPERATURE``/``JANBOT_SEED``/``JANBOT_TOP_K``/
            ``JANBOT_RELEVANCE_THRESHOLD`` is set to an invalid value.
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
    judge_model = _clean(source.get(JUDGE_MODEL_ENV)) or model_snapshot

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
        if not math.isfinite(temperature):
            raise ValueError(
                f"{TEMPERATURE_ENV}={raw_temperature!r} must be a finite number"
            )

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

    raw_retrieval_mode = _clean(source.get(RETRIEVAL_MODE_ENV))
    retrieval_mode = (
        DEFAULT_RETRIEVAL_MODE
        if raw_retrieval_mode is None
        else raw_retrieval_mode.lower()
    )
    if retrieval_mode not in RETRIEVAL_MODES:
        allowed = ", ".join(repr(mode) for mode in RETRIEVAL_MODES)
        raise ValueError(
            f"{RETRIEVAL_MODE_ENV}={raw_retrieval_mode!r} is invalid; "
            f"allowed values: {allowed}"
        )

    raw_retrieval_window = _clean(source.get(RETRIEVAL_WINDOW_ENV))
    retrieval_window = (
        DEFAULT_RETRIEVAL_WINDOW
        if raw_retrieval_window is None
        else raw_retrieval_window.lower()
    )
    if retrieval_window not in RETRIEVAL_WINDOWS:
        allowed = ", ".join(repr(window) for window in RETRIEVAL_WINDOWS)
        raise ValueError(
            f"{RETRIEVAL_WINDOW_ENV}={raw_retrieval_window!r} is invalid; "
            f"allowed values: {allowed}"
        )

    raw_relevance = _clean(source.get(RELEVANCE_THRESHOLD_ENV))
    if raw_relevance is None:
        relevance_threshold = DEFAULT_RELEVANCE_THRESHOLD
    else:
        try:
            relevance_threshold = float(raw_relevance)
        except ValueError as exc:
            raise ValueError(
                f"{RELEVANCE_THRESHOLD_ENV}={raw_relevance!r} is not a number"
            ) from exc
        if not math.isfinite(relevance_threshold):
            raise ValueError(
                f"{RELEVANCE_THRESHOLD_ENV}={raw_relevance!r} must be a finite number"
            )
        if relevance_threshold < 0:
            raise ValueError(
                f"{RELEVANCE_THRESHOLD_ENV}={raw_relevance!r} must not be negative"
            )

    raw_output_guard = _clean(source.get(OUTPUT_GUARD_ENV))
    output_guard = (
        DEFAULT_OUTPUT_GUARD
        if raw_output_guard is None
        else raw_output_guard.lower()
    )
    if output_guard not in OUTPUT_GUARDS:
        allowed = ", ".join(repr(value) for value in OUTPUT_GUARDS)
        raise ValueError(
            f"{OUTPUT_GUARD_ENV}={raw_output_guard!r} is invalid; "
            f"allowed values: {allowed}"
        )

    raw_root = _clean(source.get(PROJECT_ROOT_ENV))
    project_root = _resolve_path(raw_root, PROJECT_ROOT) if raw_root else PROJECT_ROOT

    raw_guardrails = _clean(source.get(GUARDRAILS_ENV))
    if raw_guardrails is None:
        # Production is guarded by default; eval/test must not be rate-limited
        # or require a shared store, so it defaults off and is explicit to test.
        guardrails = (
            DEFAULT_GUARDRAILS
            if model_mode == MODEL_MODE_PRODUCTION
            else GUARDRAILS_OFF
        )
    else:
        guardrails = raw_guardrails.lower()
    if guardrails not in GUARDRAILS_MODES:
        allowed = ", ".join(repr(value) for value in GUARDRAILS_MODES)
        raise ValueError(
            f"{GUARDRAILS_ENV}={raw_guardrails!r} is invalid; allowed values: {allowed}"
        )
    if model_mode == MODEL_MODE_PRODUCTION and guardrails == GUARDRAILS_OFF:
        raise ValueError(
            f"{GUARDRAILS_ENV}={GUARDRAILS_OFF!r} is not permitted in "
            f"{MODEL_MODE_PRODUCTION!r} model mode; the guardrail layer cannot be "
            "switched off in production"
        )

    def _positive_int(name: str, default: int) -> int:
        raw = _clean(source.get(name))
        if raw is None:
            return default
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{name}={raw!r} is not an integer") from exc
        if value < 1:
            raise ValueError(f"{name}={raw!r} must be a positive integer")
        return value

    rate_limit = _positive_int(RATE_LIMIT_ENV, DEFAULT_RATE_LIMIT)
    rate_window_seconds = _positive_int(
        RATE_WINDOW_ENV, DEFAULT_RATE_WINDOW_SECONDS
    )
    daily_quota = _positive_int(DAILY_QUOTA_ENV, DEFAULT_DAILY_QUOTA)
    max_question_chars = _positive_int(
        MAX_QUESTION_CHARS_ENV, DEFAULT_MAX_QUESTION_CHARS
    )
    max_body_bytes = _positive_int(MAX_BODY_BYTES_ENV, DEFAULT_MAX_BODY_BYTES)

    firestore_project = _clean(source.get(FIRESTORE_PROJECT_ENV))
    firestore_database = (
        _clean(source.get(FIRESTORE_DATABASE_ENV)) or DEFAULT_FIRESTORE_DATABASE
    )

    raw_cors_origins = _clean(source.get(CORS_ORIGINS_ENV))
    cors_origins: tuple[str, ...] | None = None
    if raw_cors_origins is not None:
        origins: list[str] = []
        for entry in raw_cors_origins.split(","):
            origin = entry.strip()
            if not origin:
                continue
            if not _valid_origin(origin):
                raise ValueError(
                    f"{CORS_ORIGINS_ENV}={raw_cors_origins!r} holds {origin!r}; "
                    "each entry must be an explicit origin of the form "
                    "'https://host[:port]' — no '*', no path/query/fragment "
                    "(including a trailing slash), no userinfo"
                )
            origins.append(origin)
        cors_origins = tuple(origins) or None

    corpus_value = _clean(source.get(CORPUS_PATH_ENV)) or DEFAULT_CORPUS_PATH
    index_value = _clean(source.get(INDEX_PATH_ENV)) or DEFAULT_INDEX_PATH
    program_value = _clean(source.get(PROGRAM_PATH_ENV))
    cache_value = _clean(source.get(CACHE_PATH_ENV))

    return Config(
        model_mode=model_mode,
        model_snapshot=model_snapshot,
        judge_model=judge_model,
        corpus_path=_resolve_path(corpus_value, project_root),
        index_path=_resolve_path(index_value, project_root),
        program_path=(
            _resolve_path(program_value, project_root)
            if program_value is not None
            else None
        ),
        temperature=temperature,
        seed=seed,
        top_k=top_k,
        retrieval_mode=retrieval_mode,
        retrieval_window=retrieval_window,
        relevance_threshold=relevance_threshold,
        output_guard=output_guard,
        guardrails=guardrails,
        cache_path=(
            _resolve_path(cache_value, project_root)
            if cache_value is not None
            else None
        ),
        rate_limit=rate_limit,
        rate_window_seconds=rate_window_seconds,
        daily_quota=daily_quota,
        max_question_chars=max_question_chars,
        max_body_bytes=max_body_bytes,
        cors_origins=cors_origins,
        firestore_project=firestore_project,
        firestore_database=firestore_database,
    )
