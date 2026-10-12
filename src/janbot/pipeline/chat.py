"""The ``/chat`` DSPy program: retrieve corpus chunks, answer and cite them.

A manual-prompt :class:`dspy.Module` — a docstring-instruction signature over
question + retrieved context, no compilation or optimization (that is
Milestone 2). Retrieval is a plain ``VectorStore.query(question, k=top_k)``;
the answer comes from an LM prediction over the retrieved context; citations
are the retrieved chunks' ``source_path`` metadata, so the response cites
exactly what it was grounded on. Strict derived-from checking and rejection of
uncited answers are later stories (3.4).

The LM is set once at construction time by the caller (``set_lm``), so a
request is a single program call.

Import order matters here: ``janbot.store`` (chromadb) must load before
``dspy``, which installs a lazy numpy proxy at import time and breaks numpy
when it lands first.
"""

from __future__ import annotations

from janbot.store import VectorStore

import dspy

from janbot.api.contract import ChatResponse, Citation


class EmptyRetrieval(ValueError):
    """Retrieval returned no chunks: the index holds no corpus context to answer from."""


class UnattributableContext(ValueError):
    """A retrieved chunk carries no ``source_path``: it cannot be cited."""


class GroundedAnswer(dspy.Signature):
    """Answer the question using only the provided corpus context."""

    question: str = dspy.InputField()
    context: str = dspy.InputField(desc="retrieved corpus chunks")
    answer: str = dspy.OutputField(desc="answer grounded in the context")


class ChatProgram(dspy.Module):
    """Retrieve ``top_k`` chunks, answer over them, and cite their sources."""

    def __init__(self, store: VectorStore, top_k: int) -> None:
        super().__init__()
        self._store = store
        self._top_k = top_k
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
        citations = [
            Citation(source=source)
            for source in dict.fromkeys(chunk["source_path"] for chunk in chunks)
        ]

        context = "\n\n".join(chunk["text"] or "" for chunk in chunks)
        prediction = self._answer(question=question, context=context)

        return ChatResponse(answer=prediction.answer, citations=citations)
