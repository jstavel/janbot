"""LLM-as-a-judge: score an answer's faithfulness to the golden expected answer.

The judge closes the hallucination gap: retrieval and citation are measured, but
nothing yet scores whether an *answer* invents facts. Given an item's golden
``expected_answer`` and the model's answer, the judge returns a :class:`Verdict`
— a label (:data:`FAITHFUL` or :data:`HALLUCINATED`) plus a short rationale.

The verdict is a label, never asserted byte-for-byte: the provider is not
byte-deterministic, so only the label is scored (the rationale is logged). The
judge is an injectable callable (:data:`Judge`), so the suite stubs it and stays
keyless; the real judge wraps a configured LM (``JANBOT_JUDGE_MODEL``) built by
:func:`janbot.llm.build_judge_lm`.

``dspy`` is imported lazily inside :func:`build_judge`, never at module import:
``janbot.eval.metrics`` imports this module, and the eval CLI must keep the
documented store-before-``dspy`` import order (``dspy`` installs a lazy numpy
proxy that breaks numpy when it lands before ``chromadb``). The pure core —
``Verdict``, the label constants and :func:`parse_verdict` — needs no ``dspy``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

FAITHFUL = "faithful"
HALLUCINATED = "hallucinated"

JUDGE_INSTRUCTION = """\
Judge whether the candidate answer is faithful to the reference answer.

Return "faithful" when every factual claim in the candidate answer is supported
by the reference answer: paraphrase, summarising and omission are all fine.
Return "hallucinated" when the candidate answer invents a fact, name, number,
date, source or relationship the reference answer does not support — including
a confident claim that contradicts the reference.
Return exactly one label: faithful or hallucinated."""

JUDGE_RATIONALE_HINT = "one short sentence justifying the verdict"


@dataclass(frozen=True)
class Verdict:
    """One judged answer: the faithfulness label and the judge's short rationale."""

    label: str
    rationale: str = ""


Judge = Callable[[str, str], Verdict]
"""An injectable judge: ``judge(expected_answer, answer) -> Verdict``."""


_NEGATIONS = ("not", "no", "non", "never", "without", "un")


def _negated(text: str, token: str) -> bool:
    """Whether ``token`` in ``text`` is preceded by a negation word (within a short window)."""
    index = text.find(token)
    if index == -1:
        return False
    window = text[max(0, index - 12) : index].replace("-", " ")
    return any(word.startswith(negation) for word in window.split() for negation in _NEGATIONS)


def parse_verdict(raw: str) -> str:
    """Normalize a judge's raw verdict text to a label, failing closed on anything else.

    A label embedded in a short sentence is tolerated (``"Faithful."`` or
    ``"Verdict: hallucinated"``), but a negated or ambiguous verdict fails closed
    (raises) rather than being read as its opposite: ``"not hallucinated"`` is
    never scored as :data:`HALLUCINATED`, and ``"not faithful"`` is never scored
    as :data:`FAITHFUL`. The caller records such an item as unjudged.
    """
    text = raw.strip().lower().strip(" \t\r\n.!\"'`")
    affirms_faithful = "faithful" in text and not _negated(text, "faithful")
    affirms_hallucinated = "hallucinat" in text and not _negated(text, "hallucinat")
    if affirms_hallucinated and not affirms_faithful:
        return HALLUCINATED
    if affirms_faithful and not affirms_hallucinated:
        return FAITHFUL
    raise ValueError(f"unrecognized judge verdict: {raw!r}")


def _faithfulness_signature() -> type:
    """Build the DSPy judge signature (imported lazily; see the module docstring)."""
    import dspy

    class Faithfulness(dspy.Signature):
        __doc__ = JUDGE_INSTRUCTION

        expected_answer: str = dspy.InputField(
            desc="the golden reference answer the candidate is judged against"
        )
        answer: str = dspy.InputField(desc="the candidate answer to judge")
        verdict: str = dspy.OutputField(
            desc="exactly one label: faithful or hallucinated"
        )
        rationale: str = dspy.OutputField(desc=JUDGE_RATIONALE_HINT)

    return Faithfulness


def build_judge(lm: Any, *, predictor_factory: Callable[..., Any] | None = None) -> Judge:
    """Wrap ``lm`` into an injectable :data:`Judge` callable.

    The default predictor is ``dspy.Predict`` over the judge signature; tests may
    inject a factory, and callers inject a stub :data:`Judge` outright so no test
    constructs or calls a real model.
    """
    factory = predictor_factory
    if factory is None:
        import dspy

        factory = dspy.Predict
    predict = factory(_faithfulness_signature())
    predict.set_lm(lm)

    def judge(expected_answer: str, answer: str) -> Verdict:
        prediction = predict(expected_answer=expected_answer, answer=answer)
        label = parse_verdict(str(prediction.verdict))
        rationale = str(getattr(prediction, "rationale", "") or "").strip()
        return Verdict(label=label, rationale=rationale)

    return judge
