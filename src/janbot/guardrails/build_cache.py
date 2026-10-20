"""Validate a recorded answer cache and write the baked artifact.

Run at image build time (no OpenRouter key, no model call)::

    python -m janbot.guardrails.build_cache \
        --source cache/answers-<run>.json \
        --out cache/answers.json

The source is the artifact written by ``python -m janbot.eval --cache-out`` from
one pinned production-config run. This command validates its provenance and every
entry (through :func:`janbot.guardrails.cache.parse_cache`), **fails if the
current golden dataset sha256 differs from the recorded one**, and writes the
canonical baked document. A mismatch means the cache no longer describes the
frozen dataset the service was evaluated against.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from janbot.config import PROJECT_ROOT
from janbot.eval.dataset import load_golden_dataset
from janbot.guardrails.cache import (
    CacheError,
    build_document,
    corpus_sha256,
    parse_cache,
)

DEFAULT_DATASET = PROJECT_ROOT / "eval" / "golden_dataset.yaml"
DEFAULT_CORPUS = PROJECT_ROOT / "public_profile_org"


def dataset_sha256(path: str | Path) -> str:
    """Return the sha256 of the dataset file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_source(
    source: str | Path,
    *,
    dataset: str | Path = DEFAULT_DATASET,
    corpus: str | Path = DEFAULT_CORPUS,
    expected_corpus_commit: str | None = None,
) -> dict:
    """Return the validated source document, failing on any provenance mismatch."""
    source_path = Path(source)
    if not source_path.is_file():
        raise CacheError(f"cache source not found: {source_path}")
    document = json.loads(source_path.read_text(encoding="utf-8"))
    cache = parse_cache(document)
    metadata = cache.metadata

    if metadata.get("model_mode") != "production":
        raise CacheError(
            "cache source was not recorded in production model mode; "
            f"got {metadata.get('model_mode')!r}"
        )
    if metadata.get("requested_model") != "openrouter/auto":
        raise CacheError(
            "cache source was not recorded against openrouter/auto; "
            f"got {metadata.get('requested_model')!r}"
        )
    recorded_sha = metadata.get("dataset_sha256")
    current_sha = dataset_sha256(dataset)
    if recorded_sha != current_sha:
        raise CacheError(
            "cache dataset sha256 mismatch: recorded "
            f"{recorded_sha!r}, current {current_sha!r} — regenerate the cache "
            "from the frozen dataset"
        )
    recorded_corpus_sha = metadata.get("corpus_sha256")
    current_corpus_sha = corpus_sha256(corpus)
    if recorded_corpus_sha != current_corpus_sha:
        raise CacheError(
            "cache corpus sha256 mismatch: recorded "
            f"{recorded_corpus_sha!r}, current {current_corpus_sha!r} — "
            "regenerate the cache from the frozen corpus"
        )
    corpus_commit = metadata.get("corpus_commit")
    if not isinstance(corpus_commit, str) or not corpus_commit.strip():
        raise CacheError("cache source has no corpus_commit")
    if expected_corpus_commit is not None and corpus_commit != expected_corpus_commit:
        raise CacheError(
            f"cache corpus commit mismatch: recorded {corpus_commit!r}, "
            f"expected {expected_corpus_commit!r}"
        )

    val_questions = {
        item.question.strip()
        for item in load_golden_dataset(dataset, split="val")
        if not item.should_refuse
    }
    foreign = [
        entry.question
        for entry in cache.entries.values()
        if entry.question not in val_questions
    ]
    if foreign:
        raise CacheError(
            f"cache carries {len(foreign)} question(s) outside the val "
            f"non-refusal set, first: {foreign[0]!r}"
        )
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m janbot.guardrails.build_cache")
    parser.add_argument("--source", required=True, help="recorded cache artifact")
    parser.add_argument("--out", required=True, help="baked cache artifact to write")
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET),
        help=f"golden dataset to pin (default: {DEFAULT_DATASET})",
    )
    parser.add_argument(
        "--corpus",
        default=str(DEFAULT_CORPUS),
        help=f"corpus tree to pin (default: {DEFAULT_CORPUS})",
    )
    parser.add_argument(
        "--corpus-commit",
        default=None,
        help="require this corpus commit in the cache metadata",
    )
    args = parser.parse_args(argv)

    try:
        document = validate_source(
            args.source,
            dataset=args.dataset,
            corpus=args.corpus,
            expected_corpus_commit=args.corpus_commit,
        )
    except (CacheError, OSError, json.JSONDecodeError) as exc:
        print(f"build-cache: {exc}", file=sys.stderr)
        return 1

    baked = build_document(
        {key: value for key, value in document["metadata"].items() if key != "version"},
        document["entries"],
    )
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(baked, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"build-cache: wrote {len(baked['entries'])} entries from run "
        f"{baked['metadata']['run_id']} to {out_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
