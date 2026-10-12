"""The ``/chat`` DSPy program: retrieve corpus chunks, answer and cite them.

A manual-prompt :class:`dspy.Module` — a docstring-instruction signature over
question + retrieved context, no compilation or optimization (that is
Milestone 2). Retrieval is a plain ``VectorStore.query(question, k=top_k)``;
each retrieved chunk enters the prompt as a block labeled with its
corpus-root-relative source. The answer comes from an LM prediction that also
names the source labels it derived the answer from; the program treats those
names as claims and validates them against the retrieved chunks'
``source_path`` metadata, then emits citations only from that metadata —
rewritten to corpus-root-relative form so no absolute path can leave the port.
An answer claiming no sources, or naming sources outside the retrieved set, is
rejected rather than returned.

The LM is set once at construction time by the caller (``set_lm``), so a
request is a single program call.

Import order matters here: ``janbot.store`` (chromadb) must load before
``dspy``, which installs a lazy numpy proxy at import time and breaks numpy
when it lands first.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from janbot.store import VectorStore

import dspy

from janbot.api.contract import ChatResponse, Citation


class EmptyRetrieval(ValueError):
    """Retrieval returned no chunks: the index holds no corpus context to answer from."""


class UnattributableContext(ValueError):
    """A retrieved chunk carries no ``source_path``, or one outside the corpus root: it cannot be cited."""


class UncitedAnswer(ValueError):
    """The model claimed no verifiable sources: the answer is not provably derived from the retrieved context."""


class GroundedAnswer(dspy.Signature):
    """Answer the question using only the provided corpus context."""

    question: str = dspy.InputField()
    context: str = dspy.InputField(desc="retrieved corpus chunks, each block labeled with its [source]")
    answer: str = dspy.OutputField(desc="answer grounded in the context")
    citations: list[str] = dspy.OutputField(
        desc="the exact [source] labels of the context blocks this answer is derived from"
    )


def corpus_relative(root: Path) -> Callable[[str], str]:
    """Build the citation rewriter: absolute ``source_path`` -> corpus-root-relative label.

    Fail-closed: a source located outside ``root`` raises
    :class:`UnattributableContext`, so no unrewritable path can reach a citation.
    """
    resolved_root = Path(root).resolve()

    def rewrite(source_path: str) -> str:
        try:
            return str(Path(source_path).relative_to(resolved_root))
        except ValueError as exc:
            raise UnattributableContext(
                "a retrieved chunk's source_path lies outside the corpus root; "
                "cannot rewrite it to a corpus-relative citation"
            ) from exc

    return rewrite


def _normalize_claim(claim: str) -> str:
    """Strip surrounding whitespace and an optional surrounding ``[ ]`` pair.

    Context labels sources as ``[source]``; a model may echo either the
    bracketed or the bare form, so both must match the retrieved source set.
    """
    normalized = claim.strip()
    if len(normalized) >= 2 and normalized.startswith("[") and normalized.endswith("]"):
        normalized = normalized[1:-1].strip()
    return normalized


class ChatProgram(dspy.Module):
    """Retrieve ``top_k`` chunks, answer over them, and cite the sources the answer derived from."""

    def __init__(self, store: VectorStore, top_k: int, rewriter: Callable[[str], str]) -> None:
        super().__init__()
        self._store = store
        self._top_k = top_k
        self._rewriter = rewriter
        self._answer = dspy.Predict(GroundedAnswer)

    def forward(self, question: str) -> ChatResponse:
        chunks = self._store.query(question, k=self._top_k)
        if not chunks:
            raise EmptyRetrieval(
                f"retrieval returned 0 chunks for question {question!r}; "
                "refusing to answer without corpus context"
            )

        if any(not chunk["source_path"] for chunk in chunks):
            raise UnattributableContext(
                f"a retrieved chunk has no source_path for question {question!r}; "
                "cannot cite every grounded chunk"
            )

        sources = [self._rewriter(chunk["source_path"]) for chunk in chunks]
        context = "\n\n".join(
            f"[{source}]\n{chunk['text'] or ''}" for source, chunk in zip(sources, chunks, strict=True)
        )
        prediction = self._answer(question=question, context=context)

        claims = list(prediction.citations or [])
        if not claims:
            raise UncitedAnswer(
                f"the model claimed no sources for question {question!r}; "
                "refusing to return an unattributable answer"
            )
        retrieved = set(sources)
        normalized = [_normalize_claim(claim) for claim in claims]
        unknown = [claim for claim in normalized if claim not in retrieved]
        if unknown:
            raise UncitedAnswer(
                f"the model made {len(unknown)} unverifiable source claim(s) for question {question!r}; "
                "the claims name sources outside the retrieved chunks — "
                "refusing to return the unverifiable answer"
            )

        citations = [Citation(source=source) for source in dict.fromkeys(normalized)]
        return ChatResponse(answer=prediction.answer, citations=citations)
