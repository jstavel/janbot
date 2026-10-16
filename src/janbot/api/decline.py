"""The deterministic decline-reason classifier: a small, auditable HR/screening lexicon.

Every decline carries a ``reason`` — ``"personal"`` for a personal/HR question the
public profile should not answer, ``"out_of_corpus"`` for a question the corpus
simply does not cover. The selection must be deterministic (E3), so it is a
case-insensitive match over a recorded lexicon, not an ad-hoc keyword rule and not
a model call: the same question always yields the same reason.

The lexicon is HR/screening-only. It names the screening topics a public profile
should not answer from — salary, notice period, relocation, security clearance,
dietary restrictions, driving licence, children, religion, marital status, date of
birth, arrest and smoking (``smoker``/``smoking``). It is fail-open: an unlisted
or private-preference question (for example, one's favourite music genre)
classifies as ``"out_of_corpus"``, so widening the lexicon is a deliberate,
measured act rather than a side effect.
"""

from __future__ import annotations

import re
from typing import Literal

DeclineReason = Literal["personal", "out_of_corpus"]
"""Why a decline declined: a personal/HR question, or a question outside the corpus."""

_PERSONAL_TERMS: tuple[str, ...] = (
    r"\bsalary\b",
    r"\bnotice period\b",
    r"\brelocat",
    r"\bclearance\b",
    r"\bdiet",
    r"\blicen[cs]e\b",
    r"\bchild",
    r"\breligio",
    r"\bmarital\b",
    r"\bbirth\b",
    r"\barrest",
    r"\bsmok(?:er|ing)\b",
)

_PERSONAL_PATTERN = re.compile("|".join(_PERSONAL_TERMS), re.IGNORECASE)


def classify_decline_reason(question: str) -> DeclineReason:
    """Classify ``question`` over the recorded HR/screening lexicon.

    Deterministic by construction: a question matching any recorded personal/HR
    term is ``"personal"``; every unlisted question falls open to
    ``"out_of_corpus"``. No model is called.
    """
    if _PERSONAL_PATTERN.search(question):
        return "personal"
    return "out_of_corpus"
