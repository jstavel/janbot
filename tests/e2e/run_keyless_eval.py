"""Drive the recorded eval keylessly as a subprocess (the e2e keyless tier).

The eval CLI's injectable seams (``embedder``/``lm_factory``) are function
arguments, not environment variables, so a subprocess cannot set them. This
wrapper — a non-test module, like ``make_index.py`` — runs in its own
interpreter and calls :func:`janbot.eval.__main__.main` with the stubs
injected, so the e2e test module never imports ``janbot`` itself.

Everything it drives is offline and deterministic: a two-object corpus it
writes itself, an index built with the same deterministic stub embedder the
eval queries with, a four-item golden dataset, and a ``DummyLM`` factory that
returns one canned cited answer for every call. ``OPENROUTER_API_KEY`` is
removed from the environment the CLI sees, so the tier stays keyless even when
the ambient environment carries a key.

Usage::

    python tests/e2e/run_keyless_eval.py --corpus DIR --index DIR \
        --dataset FILE --tracking-uri URI [--experiment NAME]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path
from typing import Any

from janbot.ingest import index_corpus

from dspy.utils import DummyLM

CORPUS_OBJECTS = {
    "search.org": "* Search\nThe corpus is searched with distributed, scoped retrievers.\n",
    "testing.org": "* Testing\nThe stack is tested at every layer, port first.\n",
}

DATASET_ITEMS = [
    {
        "question": "What search infrastructure has been built?",
        "expected_answer": "Distributed, scoped retrievers over the corpus.",
        "expected_sources": ["search.org"],
        "split": "train",
    },
    {
        "question": "How is testing approached?",
        "expected_answer": "Tests at every layer of the stack.",
        "expected_sources": ["testing.org"],
        "split": "train",
    },
    {
        "question": "What search infrastructure exists?",
        "expected_answer": "Distributed, scoped retrievers over the corpus.",
        "expected_sources": ["search.org"],
        "split": "val",
    },
    {
        "question": "How are projects managed?",
        "expected_answer": "Not covered by this fixture corpus.",
        "expected_sources": ["management.org"],
        "split": "val",
    },
]

CANNED_ANSWER = {"answer": "Grounded in the fixture corpus.", "citations": ["search.org"]}

_STUB_DIM = 64


def _stub_embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic bag-of-words embedder; no model, stable across runs."""
    vectors: list[list[float]] = []
    for text in texts:
        vector = [0.0] * _STUB_DIM
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            index = int(hashlib.sha256(token.encode()).hexdigest(), 16) % _STUB_DIM
            vector[index] += 1.0
        vectors.append(vector)
    return vectors


class _CitedDummyLMFactory:
    """LM factory returning the same canned cited answer for every call."""

    def __call__(self, **kwargs: object) -> DummyLM:
        return DummyLM([dict(CANNED_ANSWER) for _ in range(64)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="run_keyless_eval.py")
    parser.add_argument("--corpus", required=True)
    parser.add_argument("--index", required=True)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--experiment", default="janbot-eval-e2e")
    parser.add_argument("--split", choices=("all", "train", "val"), default="all")
    args = parser.parse_args(argv)

    corpus = Path(args.corpus)
    corpus.mkdir(parents=True, exist_ok=True)
    for name, text in CORPUS_OBJECTS.items():
        (corpus / name).write_text(text, encoding="utf-8")

    dataset = Path(args.dataset)
    dataset.parent.mkdir(parents=True, exist_ok=True)
    dataset.write_text(_dataset_yaml(), encoding="utf-8")

    index_corpus(corpus, Path(args.index), embedder=_stub_embedder)

    env = {
        **os.environ,
        "JANBOT_CORPUS_PATH": str(corpus),
        "JANBOT_INDEX_PATH": str(args.index),
        "JANBOT_MODEL_MODE": "eval",
        "MLFLOW_TRACKING_URI": args.tracking_uri,
    }
    env.pop("OPENROUTER_API_KEY", None)

    from janbot.eval import __main__ as eval_cli

    return eval_cli.main(
        [
            "--dataset",
            str(dataset),
            "--experiment",
            args.experiment,
            "--split",
            args.split,
        ],
        env=env,
        embedder=_stub_embedder,
        lm_factory=_CitedDummyLMFactory(),
    )


def _dataset_yaml() -> str:
    import yaml

    return yaml.safe_dump(DATASET_ITEMS, sort_keys=False)


if __name__ == "__main__":
    sys.exit(main())