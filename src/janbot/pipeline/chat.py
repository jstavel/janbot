"""The ``/chat`` DSPy program: retrieve corpus chunks, answer and cite them.

A manual-prompt :class:`dspy.Module` — a docstring-instruction signature over
question + retrieved context, no compilation or optimization (that is
Milestone 2). Retrieval is a plain ``VectorStore.query(question, k=top_k)``;
each retrieved chunk enters the prompt as a block labeled with its
corpus-root-relative source. The answer comes from an LM prediction that also
names the source labels it derived the answer from; the program rewrites each
retrieved chunk's ``source_path`` to its corpus-root-relative label, treats
those names as claims, validates them against the rewritten labels, and emits
citations only from them, in retrieval order — so no absolute path can leave the port.
An answer claiming no sources is the decline signal (:class:`UncitedAnswer`): the
pipeline cannot ground it, so the port answers with an insufficiency reply. An
answer naming sources outside the retrieved set is a fabricated cited answer and
is refused (:class:`FabricatedCitation`) rather than declined.

The LM is set once at startup by the caller via ``set_lm``, so a request is a
single program call.

Import order matters here: ``janbot.store`` (chromadb) must load before
``dspy``, which installs a lazy numpy proxy at import time and breaks numpy
when it lands first (verified 2026-10-13: importing ``dspy`` before
``chromadb`` fails with ``TypeError: data type 'bool' not understood``).
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
    """The model claimed no sources: the pipeline cannot ground the answer, so it declines."""


class FabricatedCitation(ValueError):
    """The model named a source outside the retrieved set: a fabricated cited answer, refused."""


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

    Containment is judged by the *located* path — the containing directory is
    resolved while the final component is left intact — matching the store's
    retrieval scope, so the two guards cannot disagree. Fail-closed: a
    non-absolute source, or one located outside ``root``, raises
    :class:`UnattributableContext`, so no unrewritable path can reach a citation.
    """
    resolved_root = Path(root).resolve()

    def rewrite(source_path: str) -> str:
        absolute = Path(source_path)
        if not absolute.is_absolute():
            raise UnattributableContext(
                "a retrieved chunk's source_path is not absolute; "
                "cannot rewrite it to a corpus-relative citation"
            )
        try:
            located = absolute.parent.resolve() / absolute.name
            return str(located.relative_to(resolved_root))
        except (ValueError, OSError, RuntimeError) as exc:
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
    """Retrieve ``top_k`` chunks, answer over them, and cite the sources the answer derived from.

    The corpus-relative sources the last ``forward`` retrieved are recorded on the
    program as ``last_retrieved_sources`` — an additive observation seam for the
    eval harness. It is ``None`` until a call observes retrieval, an empty list
    when the query returned no chunks, and the rewritten sources otherwise; it
    reflects the *retrieved* set, never the citations. The ``/chat`` contract and
    behavior are unchanged.
    """

    def __init__(self, store: VectorStore, top_k: int, rewriter: Callable[[str], str]) -> None:
        super().__init__()
        self._store = store
        self._top_k = top_k
        self._rewriter = rewriter
        self._answer = dspy.Predict(GroundedAnswer)
        self.last_retrieved_sources: list[str] | None = None

    def forward(self, question: str) -> ChatResponse:
        self.last_retrieved_sources = None
        chunks = self._store.query(question, k=self._top_k)
        if not chunks:
            self.last_retrieved_sources = []
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
        self.last_retrieved_sources = list(sources)
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
            raise FabricatedCitation(
                f"the model made {len(unknown)} unverifiable source claim(s) for question {question!r}; "
                "the claims name sources outside the retrieved chunks — "
                "refusing to return the unverifiable answer"
            )

        cited = set(normalized)
        citations = [
            Citation(source=source)
            for source in dict.fromkeys(sources)
            if source in cited
        ]
        return ChatResponse(answer=prediction.answer, citations=citations)
