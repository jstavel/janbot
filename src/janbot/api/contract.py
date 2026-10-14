"""The ``/chat`` HTTP contract: the single Pydantic source of truth (AD-4).

Every caller reaches JanBot only through ``POST /chat`` carrying a
:class:`ChatRequest`, and receives a :class:`ChatResponse` whose ``status``
discriminates an ``answered`` reply — whose :class:`Citation` entries name the
corpus sources that ground the answer — from an ``insufficient`` reply, which
declines to answer from the public corpus and carries no citations.
Documentation and client codegen derive from these models; nothing else in the
codebase defines the same shape.

The models are shape-complete and self-validating: a blank question is rejected
here, and so is a status that contradicts its citations — an ``answered`` reply
must cite at least one source, and an ``insufficient`` reply must cite none.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

INSUFFICIENT_ANSWER = "I don't have that in the public profile I answer from."
"""The fixed line JanBot returns when it cannot ground the question in the public corpus."""


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
    """A grounded answer with its citations, or an explicit insufficiency reply.

    ``status`` discriminates the two shapes: an ``answered`` reply requires at
    least one citation naming the corpus sources it derived from, while an
    ``insufficient`` reply declines to answer from the public corpus and carries
    none. The decline is an ordinary 200 reply, not an error.
    """

    status: Literal["answered", "insufficient"] = Field(
        default="answered",
        description=(
            'Whether the reply answers from the corpus ("answered") or declines '
            'to answer from it ("insufficient").'
        ),
    )
    answer: str = Field(
        description=(
            "The answer grounded in the cited corpus sources, or the fixed "
            "insufficiency line when the reply declines."
        )
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description=(
            "One citation per distinct corpus source that grounded an answered "
            "reply; empty on an insufficiency reply."
        ),
    )

    @model_validator(mode="after")
    def _enforce_citation_status_consistency(self) -> ChatResponse:
        """Reject an ``answered`` reply with no citations, or an ``insufficient`` reply that carries some."""
        if self.status == "answered" and not self.citations:
            raise ValueError("an answered response requires at least one citation")
        if self.status == "insufficient" and self.citations:
            raise ValueError("an insufficient response must not carry citations")
        return self
