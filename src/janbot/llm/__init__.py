"""LM adapter and model-mode routing for JanBot.

Per AD-5, model mode is configuration only. ``resolve_model`` routes purely by
the resolved ``Config``: ``eval`` resolves to the locked snapshot in
``config.model_snapshot``; ``production`` resolves to ``openrouter/auto``
against the OpenRouter API base. Switching modes is an environment change only
— no code changes.

``build_lm`` is the LM-construction seam. It assembles constructor kwargs from
pure configuration — always ``model``, ``temperature`` and the OpenRouter
``api_base`` (both modes route through OpenRouter, so a single provider pays), a
``seed`` for determinism in every mode but ``production``, and a caller-supplied
``api_key`` whenever one is given (required, failing fast, in ``production``) —
and returns ``lm_factory(**kwargs)``. The default factory is ``dspy.LM``; tests
inject a stub factory, so routing is verifiable without ever constructing a real
LM or touching the network.

Eval keeps the locked snapshot (`openai/gpt-4o-mini-2024-07-18`, which
OpenRouter serves) and its ``seed``; ``production`` uses ``openrouter/auto`` and
stays seed-free because that model routes across providers where a seed is
meaningless or rejected.

No secrets are read here: the OpenRouter key is an explicit ``api_key``
argument, sourced by the app from the ``OPENROUTER_API_KEY`` environment
variable (see ``janbot.api.main``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import dspy

from janbot.config import MODEL_MODE_EVAL, MODEL_MODE_PRODUCTION, Config

OPENROUTER_MODEL = "openrouter/auto"
OPENROUTER_API_BASE = "https://openrouter.ai/api/v1"
JUDGE_TEMPERATURE = 0.0
"""The judge LM samples at temperature 0 so verdicts are as stable as the provider allows."""

LMFactory = Callable[..., Any]


def resolve_model(config: Config) -> str:
    """Return the model name the given configuration routes to.

    Both modes route through OpenRouter: ``eval`` resolves to the locked snapshot
    in ``config.model_snapshot`` wrapped in the ``openrouter/`` transport prefix,
    ``production`` to ``openrouter/auto``. The prefix makes LiteLLM use its
    OpenRouter provider (credential: ``OPENROUTER_API_KEY``), so an ambient
    ``OPENAI_API_KEY`` is never sent to the OpenRouter host.
    """
    if config.model_mode == MODEL_MODE_PRODUCTION:
        return OPENROUTER_MODEL
    if config.model_mode == MODEL_MODE_EVAL:
        return f"openrouter/{config.model_snapshot}"
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
        "api_base": OPENROUTER_API_BASE,
    }

    if config.model_mode != MODEL_MODE_PRODUCTION:
        kwargs["seed"] = config.seed

    if config.model_mode == MODEL_MODE_PRODUCTION and not api_key:
        raise ValueError(
            f"api_key is required in {MODEL_MODE_PRODUCTION!r} model mode; "
            "pass the OpenRouter key explicitly to build_lm"
        )

    if api_key:
        kwargs["api_key"] = api_key

    return lm_factory(**kwargs)


def build_judge_lm(
    config: Config,
    api_key: str | None = None,
    *,
    lm_factory: LMFactory = dspy.LM,
) -> Any:
    """Build the LLM-as-a-judge LM from configuration via the same ``lm_factory`` seam.

    The judge is configuration only (AD-5): it routes ``openrouter/`` + the
    ``config.judge_model`` snapshot through the single OpenRouter host and the
    same ``api_key``, pinned to ``temperature=0`` (a verdict should not wander)
    and the eval ``seed``. It never branches on model mode: a stronger judge is a
    change to ``JANBOT_JUDGE_MODEL``, not code.
    """
    kwargs: dict[str, Any] = {
        "model": f"openrouter/{config.judge_model}",
        "temperature": JUDGE_TEMPERATURE,
        "api_base": OPENROUTER_API_BASE,
        "seed": config.seed,
    }

    if api_key:
        kwargs["api_key"] = api_key

    return lm_factory(**kwargs)
