"""The ``/chat`` HTTP contract: the single Pydantic source of truth (AD-4).

Every caller reaches JanBot only through ``POST /chat`` carrying a
:class:`ChatRequest`, and receives a :class:`ChatResponse` whose
:class:`Citation` entries name the corpus sources that ground the answer.
Documentation and client codegen derive from these models; nothing else in the
codebase defines the same shape.

The models are shape-complete and self-validating: a blank question and an
answer with zero citations are rejected here, never downstream.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    """A recruiter's question."""

    question: str = Field(
        description="The question to answer from the public corpus."
    )

    @field_validator("question")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        """Strip surrounding whitespace, rejecting a question that is all blank."""
        stripped = value.strip()
        if not stripped:
            raise ValueError("question must not be blank")
        return stripped


class Citation(BaseModel):
    """One corpus source that grounds an answer."""

    source: str = Field(
        description="Corpus-root-relative path of the corpus document that grounds the answer."
    )


class ChatResponse(BaseModel):
    """A grounded answer plus the sources it cites."""

    answer: str = Field(description="The answer grounded in the cited corpus sources.")
    citations: list[Citation] = Field(
        min_length=1,
        description="At least one citation per distinct corpus source that grounded the answer.",
    )
