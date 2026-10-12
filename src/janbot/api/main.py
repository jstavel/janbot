"""FastAPI application for JanBot.

``create_app`` is the composition root: it resolves configuration, opens the
vector store, builds the LM and the ``/chat`` DSPy program once at startup, and
wires the HTTP port on top. Callers reach JanBot only through ``POST /chat``
with the Pydantic contract in :mod:`janbot.api.contract`; model selection stays
configuration-only (AD-5) — the routed model and its temperature come from the
resolved ``Config``, never from code branches.

The OpenRouter key is ``OPENROUTER_API_KEY``: an operator-supplied environment
variable read once here, never a config field and never a per-request lookup.
In ``production`` mode a missing key fails fast at startup — it can never
surface as a per-request error. Tests build their own app instance with
injected store/LM adapters and speak HTTP only (AD-7).

Import order matters: ``janbot.store`` (chromadb) must load before anything
that imports ``dspy``, whose lazy numpy proxy breaks numpy when it lands
first.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import FastAPI, HTTPException

from janbot.api.contract import ChatRequest, ChatResponse
from janbot.config import MODEL_MODE_PRODUCTION, load_config
from janbot.store import Embedder, VectorStore, default_embedder

import dspy

from janbot.llm import LMFactory, build_lm
from janbot.pipeline.chat import ChatProgram, EmptyRetrieval, corpus_relative

OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"


def create_app(
    env: Mapping[str, str] | None = None,
    *,
    embedder: Embedder | None = None,
    lm_factory: LMFactory = dspy.LM,
) -> FastAPI:
    """Build the app: config -> store -> LM -> program, then wire the port.

    ``env`` replaces the process environment (tests pass a mapping so ambient
    variables cannot leak in); ``embedder`` and ``lm_factory`` choose the
    driven adapters — the production store embedder and ``dspy.LM`` when
    omitted. A blank or whitespace-only ``OPENROUTER_API_KEY`` counts as
    absent.

    Raises:
        ValueError: if the resolved configuration is invalid, or if the model
            mode is ``production`` and no ``OPENROUTER_API_KEY`` is present.
    """
    config = load_config(env)
    store = VectorStore(config.index_path, embedder or default_embedder())

    source = os.environ if env is None else env
    api_key = (source.get(OPENROUTER_API_KEY_ENV) or "").strip() or None
    if config.model_mode == MODEL_MODE_PRODUCTION and not api_key:
        raise ValueError(
            f"{OPENROUTER_API_KEY_ENV} is required in "
            f"{MODEL_MODE_PRODUCTION!r} model mode; set it in the environment "
            "before starting the server"
        )
    lm = build_lm(config, api_key=api_key, lm_factory=lm_factory)

    program = ChatProgram(
        store, top_k=config.top_k, rewriter=corpus_relative(config.corpus_path)
    )
    program.set_lm(lm)

    app = FastAPI(title="JanBot")
    app.state.program = program

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        try:
            return app.state.program(question=request.question)
        except EmptyRetrieval as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    return app


app = create_app()
