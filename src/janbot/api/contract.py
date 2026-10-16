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

from janbot.api.decline import DeclineReason, classify_decline_reason

INSUFFICIENT_ANSWER = (
    "I answer only from my public profile — for anything beyond it, "
    "please contact Jan Stavel directly."
)
"""The fixed line JanBot returns when it cannot ground the question in the public corpus.

One text serves both decline reasons (personal/HR and out-of-corpus): the
human-visible reply is unified, and only the response's ``reason`` metadata
distinguishes them.
"""


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
    reason: DeclineReason | None = Field(
        default=None,
        description=(
            'Why an insufficiency reply declined: "personal" for a personal/HR '
            'question the public profile should not answer, "out_of_corpus" for a '
            "question the corpus does not cover; null on an answered reply."
        ),
    )

    @model_validator(mode="after")
    def _enforce_citation_status_consistency(self) -> ChatResponse:
        """Reject an ``answered`` reply with no citations or a decline reason, or an ``insufficient`` reply that carries citations."""
        if self.status == "answered" and not self.citations:
            raise ValueError("an answered response requires at least one citation")
        if self.status == "answered" and self.reason is not None:
            raise ValueError("an answered response must not carry a decline reason")
        if self.status == "insufficient" and self.citations:
            raise ValueError("an insufficient response must not carry citations")
        return self


def decline(question: str) -> ChatResponse:
    """Build the unified insufficiency reply for ``question``, classifying its reason.

    The answer text is the single :data:`INSUFFICIENT_ANSWER` constant for both
    reasons; only ``reason`` distinguishes a personal/HR decline from an
    out-of-corpus one. Classification is deterministic and makes no model call.
    This is the single shared decline-construction site: every production
    caller routes its decline through it.
    """
    return ChatResponse(
        status="insufficient",
        answer=INSUFFICIENT_ANSWER,
        citations=[],
        reason=classify_decline_reason(question),
    )
