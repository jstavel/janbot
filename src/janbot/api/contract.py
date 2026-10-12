"""The ``/chat`` HTTP contract: the single Pydantic source of truth (AD-4).

Every caller reaches JanBot only through ``POST /chat`` carrying a
:class:`ChatRequest`, and receives a :class:`ChatResponse` whose
:class:`Citation` entries name the corpus sources that ground the answer.
Documentation and client codegen derive from these models; nothing else in the
codebase defines the same shape.
"""

from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    """A recruiter's question."""

    question: str


class Citation(BaseModel):
    """One corpus source that grounds an answer."""

    source: str


class ChatResponse(BaseModel):
    """A grounded answer plus the sources it cites."""

    answer: str
    citations: list[Citation]
