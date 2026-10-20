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
from janbot.config import (
    GUARDRAILS_ON,
    MODEL_MODE_PRODUCTION,
    OUTPUT_GUARD_ON,
    load_config,
)
from janbot.guardrails.cache import AnswerCache, load_cache
from janbot.guardrails.limits import (
    QUOTA_EXCEEDED,
    RATE_LIMITED,
    STORE_ERROR,
    FirestoreLimits,
    Limiter,
)
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


class _BodyTooLarge(Exception):
    """The request body exceeded the configured cap before it was parsed."""


async def _send_error(send, status_code: int, detail: str) -> None:
    import json

    body = json.dumps({"detail": detail}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json"),
        (b"content-length", str(len(body)).encode("ascii")),
    ]
    await send({"type": "http.response.start", "status": status_code, "headers": headers})
    await send({"type": "http.response.body", "body": body})


class BodySizeLimitMiddleware:
    """Reject an oversized ``/chat`` body before FastAPI parses it.

    A declared ``Content-Length`` is checked first; a chunked body is counted as
    it is received and aborted once the cap is crossed. The OpenAPI contract is
    unchanged — this is an HTTP bound, not a Pydantic field.
    """

    def __init__(self, app, *, max_bytes: int, path: str = "/chat") -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.path = path

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http" or scope.get("path") != self.path:
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared is not None:
            try:
                length = int(declared)
            except ValueError:
                await _send_error(send, 400, "invalid content-length")
                return
            if length > self.max_bytes:
                await _send_error(send, 413, "request body too large")
                return

        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLarge:
            await _send_error(send, 413, "request body too large")


def _client_ip(request: Request) -> str:
    """The caller's IP: the **last** ``X-Forwarded-For`` hop, normalized.

    Cloud Run appends the peer it saw to any client-supplied header, so the last
    value is the trusted hop; the first is caller-controlled. Normalizing with
    ``ipaddress`` collapses equivalent IPv6 spellings to one counter key.
    """
    from ipaddress import ip_address

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        last = forwarded.split(",")[-1].strip()
        try:
            return ip_address(last).compressed
        except ValueError:
            pass
    peer = request.client.host if request.client else "unknown"
    try:
        return ip_address(peer).compressed
    except ValueError:
        return peer



def create_app(
    env: Mapping[str, str] | None = None,
    *,
    embedder: Embedder | None = None,
    lm_factory: LMFactory = dspy.LM,
    limiter: Limiter | None = None,
    cache: AnswerCache | None = None,
    require_cache: bool = True,
) -> FastAPI:
    """Build the app: config -> store -> LM -> program, then wire the port.

    ``env`` replaces the process environment (tests pass a mapping so ambient
    variables cannot leak in); ``embedder`` and ``lm_factory`` choose the
    driven adapters — the production store embedder and ``dspy.LM`` when
    omitted. A blank or whitespace-only ``OPENROUTER_API_KEY`` counts as
    absent.

    ``limiter`` and ``cache`` are test seams for the shared counters and the
    baked cache. Production leaves them unset: the Firestore limiter is built
    from ``JANBOT_FIRESTORE_PROJECT`` and the cache is loaded from
    ``JANBOT_CACHE_PATH``. There is no other ``/chat`` path around the layer.

    Raises:
        ValueError: if the resolved configuration is invalid, if
            ``JANBOT_PROGRAM_PATH`` is set but does not name a file, if the model
            mode is ``production`` and no ``OPENROUTER_API_KEY`` is present, if
            ``JANBOT_CACHE_PATH`` names a missing/invalid artifact, or if the
            index holds chunks whose ``source_path`` lies outside
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

    guardrails_on = config.guardrails == GUARDRAILS_ON
    if guardrails_on:
        if cache is None and config.cache_path is not None:
            cache = load_cache(config.cache_path)
        if limiter is None:
            limiter = FirestoreLimits.from_config(config)
        if config.model_mode == MODEL_MODE_PRODUCTION and limiter is None:
            raise ValueError(
                "the guardrail layer is on in production but no Firestore "
                "project is configured; refusing to start without the shared "
                "rate/quota counters"
            )
        if (
            require_cache
            and config.model_mode == MODEL_MODE_PRODUCTION
            and cache is None
        ):
            raise ValueError(
                "the guardrail layer is on in production but no answer cache is "
                "configured; refusing to start without the baked cache"
            )

    app = FastAPI(title="JanBot")
    app.state.program = program
    app.state.cache = cache if guardrails_on else None
    app.state.limiter = limiter if guardrails_on else None
    app.state.config = config

    if guardrails_on:
        app.add_middleware(
            BodySizeLimitMiddleware, max_bytes=config.max_body_bytes, path="/chat"
        )

    def _guard_denied(decision) -> HTTPException:
        if decision.reason == STORE_ERROR:
            return HTTPException(
                status_code=503,
                detail="the guardrail store is unavailable",
            )
        return HTTPException(
            status_code=429,
            detail=(
                "too many requests"
                if decision.reason == RATE_LIMITED
                else "the daily model-call quota is exhausted"
            ),
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: Request, payload: ChatRequest) -> ChatResponse:
        active_cache = app.state.cache
        active_limiter = app.state.limiter

        if guardrails_on and len(payload.question) > config.max_question_chars:
            raise HTTPException(
                status_code=422,
                detail=(
                    "question exceeds the maximum length of "
                    f"{config.max_question_chars} characters"
                ),
            )

        if active_limiter is not None:
            decision = active_limiter.check_rate(_client_ip(request))
            if not decision.allowed:
                raise _guard_denied(decision)

        if active_cache is not None:
            cached = active_cache.lookup(payload.question)
            if cached is not None:
                return cached

        if active_limiter is not None:
            decision = active_limiter.consume_quota()
            if not decision.allowed:
                raise _guard_denied(decision)

        try:
            return app.state.program(question=payload.question)
        except (EmptyRetrieval, LowRelevance, UncitedAnswer):
            return decline(question=payload.question)
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
