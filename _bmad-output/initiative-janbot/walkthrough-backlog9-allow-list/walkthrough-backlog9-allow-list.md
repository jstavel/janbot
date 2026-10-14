---
# Walkthrough: public-reference allow-list (backlog 9)

Target: `0deef43` — independent backlog story; not part of an epic.

Current block: 6.

## Block 1 — Intent — [x] accepted

**Problem:** JanBot answers may name projects; the owner's rule is that an answer surfaces the full public URL when a project has one, and never invents one. Nothing enforces or measures that today — the eval has no public-reference check, and an invented or wrong-owner URL would pass unnoticed.

**Approach:** a static, versioned allow-list of valid public URLs (harvested from the corpus `:PUBLIC:` drawers, inline `[[url]]` links, URL-leading bullets and the generated proof map), plus an eval check with the owner's asymmetry: a URL not on the list is unverifiable (failure), and a URL present in an item's expected answer but missing from the model answer is incomplete (failure). Eval-only; `/chat` untouched.

(source: the frozen Intent of the [plan](../../backlog/story-public-reference-allow-list-plan.md))

## Block 2 — Broad strokes — [x] accepted

A self-contained eval-layer feature: harvest the corpus into a URL allow-list, then score each answer against it. Open in order:

- [src/janbot/eval/public_urls.py](../../../src/janbot/eval/public_urls.py) — the URL contract and the allow-list generator.
- [src/janbot/eval/metrics.py](../../../src/janbot/eval/metrics.py) — the `public_references` metric.
- [src/janbot/eval/runner.py](../../../src/janbot/eval/runner.py) — per-item failure reporting.
- [eval/public_urls.yaml](../../../eval/public_urls.yaml) — the generated allow-list.
- [tests/test_eval_public_urls.py](../../../tests/test_eval_public_urls.py) — the contract's proof.

## Block 3 — Slice: the URL contract — [x] accepted

[src/janbot/eval/public_urls.py](../../../src/janbot/eval/public_urls.py) defines when a reference counts. `normalize_reference` strips scheme, `www.`, `.git`, `#fragment`, `?query` and trailing punctuation; `extract_urls` pulls references out of text (bare domains only when they carry a path or match a listed host, so prose tokens like `WebDriver.io` do not count); `is_public_reference` accepts an exact match, a deeper path under a listed entry, or a listed dedicated pathless host — but not a shared host like `github.com`.

## Block 4 — Slice: the metric and per-item flagging — [x] accepted

[src/janbot/eval/metrics.py](../../../src/janbot/eval/metrics.py) registers `public_references`: an off-list URL fails as unverifiable, an expected URL missing from the answer fails as incomplete, no URLs passes. [src/janbot/eval/runner.py](../../../src/janbot/eval/runner.py) carries the failing item/URL through `RunResult.reference_failures`, and [src/janbot/eval/__main__.py](../../../src/janbot/eval/__main__.py) prints a `reference:` line per failure.

## Block 5 — Slice: generation and isolation — [x] accepted

`harvest_public_urls`/`generate_allow_list` (and the `python -m janbot.eval.public_urls` CLI) build [eval/public_urls.yaml](../../../eval/public_urls.yaml) from the corpus, so the list never drifts by hand. The walker is local — the module imports no `janbot.ingest`/`janbot.store`, keeping the eval package import-isolated.

## Block 6 — Periphery — [x] accepted

- [tests/test_eval_public_urls.py](../../../tests/test_eval_public_urls.py), [tests/test_eval_runner.py](../../../tests/test_eval_runner.py) — the contract and the flagging.
- [CHANGELOG.md](../../../CHANGELOG.md) — the new metric and artifact.
- [plan](../../backlog/story-public-reference-allow-list-plan.md) — the build plan (with the review loopback).
---
