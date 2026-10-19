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
first (verified 2026-10-13: importing ``dspy`` before ``chromadb`` fails
with ``TypeError: data type 'bool' not understood``).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import ResponseValidationError
from fastapi.responses import JSONResponse

from janbot.api.contract import ChatRequest, ChatResponse, decline
from janbot.config import MODEL_MODE_PRODUCTION, OUTPUT_GUARD_ON, load_config
from janbot.store import Embedder, VectorStore, default_embedder

import dspy

from janbot.llm import LMFactory, build_lm
from janbot.pipeline.chat import (
    ChatProgram,
    EmptyRetrieval,
    LowRelevance,
    UncitedAnswer,
    corpus_relative,
)

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
        ValueError: if the resolved configuration is invalid, if
            ``JANBOT_PROGRAM_PATH`` is set but does not name a file, if the model
            mode is ``production`` and no ``OPENROUTER_API_KEY`` is present, or
            if the index holds chunks whose ``source_path`` lies outside
            ``JANBOT_CORPUS_PATH`` (built from a different corpus root).
    """
    config = load_config(env)
    if config.program_path is not None and not config.program_path.is_file():
        raise ValueError(
            f"JANBOT_PROGRAM_PATH={str(config.program_path)!r} does not name a file; "
            "the configured compiled program is missing — refusing to start"
        )
    store = VectorStore(
        config.index_path,
        embedder or default_embedder(),
        scope=config.corpus_path,
        retrieval_mode=config.retrieval_mode,
        retrieval_window=config.retrieval_window,
    )
    foreign = store.out_of_scope_sources()
    if foreign:
        raise ValueError(
            f"the index holds {len(foreign)} chunk(s) whose source_path lies "
            f"outside {config.corpus_path} — the index was built from a different "
            "corpus root; refusing to start"
        )

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
        store,
        top_k=config.top_k,
        rewriter=corpus_relative(config.corpus_path),
        relevance_threshold=config.relevance_threshold,
        guard_enabled=config.output_guard == OUTPUT_GUARD_ON,
    )
    if config.program_path is not None:
        from janbot.eval.optimize import load_program

        load_program(program, config.program_path)
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
        except (EmptyRetrieval, LowRelevance, UncitedAnswer):
            return decline(question=request.question)
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        except HTTPException:
            raise
        except dspy.DSPyError as exc:
            raise HTTPException(
                status_code=500,
                detail="the model response could not be processed",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="the service failed to process the request",
            ) from exc

    @app.exception_handler(ResponseValidationError)
    def _response_validation(
        request: Request, exc: ResponseValidationError
    ) -> JSONResponse:
        # A program that returns a non-conforming body must still carry the envelope.
        return JSONResponse(
            status_code=500,
            content={"detail": "the service failed to process the request"},
        )

    return app


app = create_app()
