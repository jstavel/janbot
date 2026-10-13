# Walkthrough — PR #10: "emit citations in retrieval order for deterministic output"

Target: PR https://github.com/jstavel/janbot/pull/10 · branch `hardening-citation-ordering` · commit `62e6541`.

- [x] Block 1 — Intent
- [x] Block 2 — Broad strokes
- [x] Block 3 — Slice: the citation construction
- [x] Block 4 — Slice: proving the ordering
- [x] Block 5 — Periphery

## Block 1 — Intent

Source: pasted verbatim from the plan's frozen Intent section — [plan-citation-ordering.md](../plan-citation-ordering.md).

> **Problem:** citations are built in LM-claim order — `citations = [Citation(source=s) for s in dict.fromkeys(normalized)]`, where `normalized` is the order the model emitted its claims. Two runs with identical answer text but permuted claims therefore produce different JSON bodies, a nondeterminism channel that undermines DW4 ("same query at the locked snapshot returns identical output across runs") and that the stub determinism tests cannot see. Recorded in the epic-rag-chat retrospective.
>
> **Approach:** emit citations in **retrieval-`sources` order** — deduped, and filtered to the validated claim set — so that given identical retrieval the response is identical regardless of the model's claim order. The set of cited sources, the dedup rule, and the validation are unchanged.

## Block 2 — Broad strokes

One function in [src/janbot/pipeline/chat.py](../../../src/janbot/pipeline/chat.py) plus two tests. Open these spots:

- [chat.py:137](../../../src/janbot/pipeline/chat.py) — the citation construction.
- [tests/test_chat.py:591](../../../tests/test_chat.py) — the ordering test.
- [tests/test_chat.py:627](../../../tests/test_chat.py) — the repeated-claim test.

## Block 3 — Slice: the citation construction

- [chat.py:137](../../../src/janbot/pipeline/chat.py) — `cited = set(normalized)` then iterate `dict.fromkeys(sources)` (retrieval order, deduped) filtered to `cited`. The cited set, dedup, and rejection logic are unchanged; only the order comes from retrieval.

## Block 4 — Slice: proving the ordering

- [test_chat.py:591](../../../tests/test_chat.py) — a corpus built so retrieval rank (`zulu.org`) ≠ label sort order (`alpha.org`); two apps claim the sources in opposite orders and must emit identical bodies in retrieval order (fails if the code sorts, or uses claim order).
- [test_chat.py:627](../../../tests/test_chat.py) — a repeated claim still yields one citation per distinct source.

## Block 5 — Periphery

- [chat.py:11](../../../src/janbot/pipeline/chat.py) — the module docstring now says citations are emitted in retrieval order.
- [plan-citation-ordering.md](../plan-citation-ordering.md) — the plan (`built`); Triage Log records the three test-strength fixes.
