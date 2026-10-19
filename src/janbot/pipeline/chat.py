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
pipeline cannot ground it, so the port answers with an insufficiency reply. A
retrieval whose best chunk is below the configured relevance threshold is the
other decline signal (:class:`LowRelevance`), raised before the LM call. An
answer naming sources outside the retrieved set is handled by the deterministic
output guard (ADR-010): the fabricated labels are dropped and a valid answer is
kept; if no valid label remains, or the guard itself errors, the response
declines through the existing uncited path. A citation outside the retrieved set
can still never leave the port.

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
from janbot.guardrails import apply_output_guard


class EmptyRetrieval(ValueError):
    """Retrieval returned no chunks: the index holds no corpus context to answer from."""


class UnattributableContext(ValueError):
    """A retrieved chunk carries no ``source_path``, or one outside the corpus root: it cannot be cited."""


class UncitedAnswer(ValueError):
    """The model claimed no sources: the pipeline cannot ground the answer, so it declines."""


class FabricatedCitation(ValueError):
    """A citation outside the retrieved set survived the guard: a fail-closed invariant."""


class LowRelevance(ValueError):
    """The best retrieved chunk is below the relevance threshold: the corpus cannot ground the question."""


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
    """Strip whitespace and an optional surrounding ``[ ]`` pair (context labels)."""
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

    ``last_raw_answer``, ``last_raw_citations``, ``last_guard_action`` and
    ``last_normalized_citations`` are the output guard's additive observation seam: the
    prediction before the guard, the labels the model cited before D1, the action, and how
    many alias labels were normalized. They never alter the response; with the guard disabled
    the raw values equal the final ones.

    ``relevance_threshold`` is the low-relevance decline gate: when it is
    non-zero and the best retrieved chunk's ``similarity`` falls below it,
    ``forward`` raises :class:`LowRelevance` *before* the LM call, so the decline
    is a deterministic function of the embeddings alone. The constructor default
    ``0.0`` disables the gate; the shipped configuration default is the measured
    ``0.26``.
    """

    def __init__(
        self,
        store: VectorStore,
        top_k: int,
        rewriter: Callable[[str], str],
        relevance_threshold: float = 0.0,
        guard_enabled: bool = True,
    ) -> None:
        super().__init__()
        self._store = store
        self._top_k = top_k
        self._rewriter = rewriter
        self._relevance_threshold = relevance_threshold
        self._guard_enabled = guard_enabled
        self._answer = dspy.Predict(GroundedAnswer)
        self.last_retrieved_sources: list[str] | None = None
        self.last_retrieved_context: str | None = None
        self.last_raw_answer: str | None = None
        self.last_raw_citations: list[str] | None = None
        self.last_guard_action: str | None = None
        self.last_normalized_citations: int | None = None

    def forward(self, question: str) -> ChatResponse:
        self.last_retrieved_sources = None
        self.last_retrieved_context = None
        self.last_raw_answer = None
        self.last_raw_citations = None
        self.last_guard_action = None
        self.last_normalized_citations = None
        chunks = self._store.query(question, k=self._top_k)
        if not chunks:
            self.last_retrieved_sources = []
            self.last_retrieved_context = ""
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

        if self._relevance_threshold != 0.0:
            best_two = sorted(
                (chunk["similarity"] for chunk in chunks), reverse=True
            )[:2]
            if best_two and all(
                similarity < self._relevance_threshold for similarity in best_two
            ):
                raise LowRelevance(
                    f"the two best retrieved chunks have similarities {best_two!r} "
                    f"below the relevance threshold {self._relevance_threshold!r} "
                    f"for question {question!r}; the corpus cannot ground the question"
                )

        context = "\n\n".join(
            f"[{source}]\n{chunk['text'] or ''}" for source, chunk in zip(sources, chunks, strict=True)
        )
        self.last_retrieved_context = context
        prediction = self._answer(question=question, context=context)

        claims = list(prediction.citations or [])
        self.last_raw_answer = prediction.answer
        self.last_raw_citations = list(claims)
        retrieved = set(sources)

        if not self._guard_enabled:
            self.last_guard_action = "disabled"
            self.last_normalized_citations = 0
            if not claims:
                raise UncitedAnswer(
                    f"the model claimed no sources for question {question!r}; "
                    "refusing to return an unattributable answer"
                )
            normalized = [_normalize_claim(claim) for claim in claims]
            unknown = [claim for claim in normalized if claim not in retrieved]
            if unknown:
                raise FabricatedCitation(
                    f"the model made {len(unknown)} unverifiable source claim(s) for "
                    f"question {question!r}; the claims name sources outside the "
                    "retrieved chunks — refusing to return the unverifiable answer"
                )
            cited = set(normalized)
            citations = [
                Citation(source=source)
                for source in dict.fromkeys(sources)
                if source in cited
            ]
            return ChatResponse(answer=prediction.answer, citations=citations)

        guard_result = apply_output_guard(
            answer=prediction.answer,
            citations=claims,
            retrieved_chunks=[
                {"source": source, "text": chunk["text"] or ""}
                for source, chunk in zip(sources, chunks, strict=True)
            ],
        )
        self.last_guard_action = guard_result.action
        self.last_normalized_citations = guard_result.normalized_count
        if guard_result.declined:
            raise UncitedAnswer(
                f"the output guard declined the answer for question {question!r}: "
                f"{guard_result.reason}"
            )
        if not guard_result.answer.strip() or not guard_result.citations:
            self.last_guard_action = f"declined: {guard_result.rule or 'D1'}"
            raise UncitedAnswer(
                f"the output guard left no grounded answer for question {question!r}; "
                "refusing to return an unattributable answer"
            )

        unknown = [label for label in guard_result.citations if label not in retrieved]
        if unknown:
            self.last_guard_action = "declined: D1"
            raise FabricatedCitation(
                f"the output guard emitted {len(unknown)} citation(s) outside the "
                f"retrieved set for question {question!r}; refusing to return the "
                "unverifiable answer"
            )

        cited = set(guard_result.citations)
        citations = [
            Citation(source=source)
            for source in dict.fromkeys(sources)
            if source in cited
        ]
        return ChatResponse(answer=guard_result.answer, citations=citations)
