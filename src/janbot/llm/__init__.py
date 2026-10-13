"""LM adapter and model-mode routing for JanBot.

Per AD-5, model mode is configuration only. ``resolve_model`` routes purely by
the resolved ``Config``: ``eval`` resolves to the locked snapshot in
``config.model_snapshot``; ``production`` resolves to ``openrouter/auto``
against the OpenRouter API base. Switching modes is an environment change only
— no code changes.

``build_lm`` is the LM-construction seam. It assembles constructor kwargs from
pure configuration — always ``model`` and ``temperature``, a ``seed`` for
determinism in every mode but ``production``, and only in ``production`` the
OpenRouter ``api_base`` plus a caller-supplied ``api_key`` — and returns
``lm_factory(**kwargs)``. The default factory is ``dspy.LM``; tests inject a
stub factory, so routing is verifiable without ever constructing a real LM or
touching the network.

The ``seed`` pins eval sampling reproducibility (AD-5): ``production`` stays
seed-free because ``openrouter/auto`` routes across providers where a seed is
meaningless or rejected.

No secrets are read here: the OpenRouter key is an explicit ``api_key``
argument, sourced by the app from the ``OPENROUTER_API_KEY`` environment
variable (see ``janbot.api.main``) and required, failing fast, in
``production`` mode only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import dspy

from janbot.config import MODEL_MODE_EVAL, MODEL_MODE_PRODUCTION, Config

OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"

LMFactory = Callable[..., Any]


def resolve_model(config: Config) -> str:
    """Return the model name the given configuration routes to."""
    if config.model_mode == MODEL_MODE_PRODUCTION:
        return OPENROUTER_MODEL
    if config.model_mode == MODEL_MODE_EVAL:
        return config.model_snapshot
    raise ValueError(f"unknown model mode: {config.model_mode!r}")


def build_lm(
    config: Config,
    api_key: str | None = None,
    *,
    lm_factory: LMFactory = dspy.LM,
) -> Any:
    """Build an LM from pure configuration via ``lm_factory``.

    Raises:
        ValueError: if ``config.model_mode`` is ``production`` and ``api_key``
            is missing.
    """
    kwargs: dict[str, Any] = {
        "model": resolve_model(config),
        "temperature": config.temperature,
    }

    if config.model_mode != MODEL_MODE_PRODUCTION:
        kwargs["seed"] = config.seed

    if config.model_mode == MODEL_MODE_PRODUCTION:
        if not api_key:
            raise ValueError(
                f"api_key is required in {MODEL_MODE_PRODUCTION!r} model mode; "
                "pass the OpenRouter key explicitly to build_lm"
            )
        kwargs["api_base"] = OPENROUTER_API_BASE
        kwargs["api_key"] = api_key

    return lm_factory(**kwargs)
