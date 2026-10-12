# Review: PR #4 — citation derived-from & uncited-answer rejection (story 3.4)

**Target:** PR [#4](https://github.com/jstavel/janbot/pull/4) — head `story-3.4-citation-correctness` → base `main`, single commit `9b477f5` — "feat: enforce citation derived-from and reject uncited answers (story 3.4)".

## Block 1 — Intent

- [x] accepted

The frozen Intent below comes verbatim from the story-3.4 plan file ([story-citation-correctness-uncited-answer-rejection-plan.md](../epic-rag-chat/story-citation-correctness-uncited-answer-rejection-plan.md#L20-L45)):

> **Problem:** `/chat` citations are not proven derived-from: they name every retrieved chunk's source regardless of what the answer actually used, an LM answer with no grounding cannot be distinguished from a cited one, and `Citation.source` echoes the store's absolute `source_path` — leaking the server layout and the owner's `$HOME` (epic-ingestion retrospective carry, pinned in `deferred-work.md`).
>
> **Approach:** The DSPy program claims its own sources: the answer generation names the context chunks it derived from (by source label), the program validates every claim against the retrieved chunks' `source_path` metadata, emits citations only from that metadata — rewritten to corpus-relative form so no absolute path can leave the port — and rejects an answer whose citations are empty or unverifiable rather than returning it (CAP-2; epic Done-when 2).

Situating: story 3.3 finished the contract but citations were still metadata-of-everything-retrieved with absolute paths; this story makes derivation provable, adds fail-closed rejections, and closes the epic-ingestion retrospective carry (citation-path leak, pinned in [deferred-work.md](../deferred-work.md)). Human decisions baked in: unknown-source claims are rejected, not dropped; citation values are corpus-root-relative (e.g. `profile.org`). Sets up story 3.5 (determinism) and 3.6 (grounding boundary).

## Block 2 — Broad strokes

- [x] accepted

Entry points a reviewer opens first:

- [src/janbot/pipeline/chat.py](../../../src/janbot/pipeline/chat.py) — the enforcement point: the signature's citations output, labeled context, claim validation, metadata-backed citation emission.
- [src/janbot/api/main.py](../../../src/janbot/api/main.py) — the wiring: the rewriter built from `config.corpus_path` and passed into the program.
- [src/janbot/api/contract.py](../../../src/janbot/api/contract.py) — `Citation.source` documentation now describes the corpus-relative form.
- [tests/test_chat.py](../../../tests/test_chat.py) — the port rows: eight new tests covering the story's I/O matrix.
- [README.md](../../../README.md) — the Chat section's rewritten citation and rejection semantics.

## Block 3 — Slice: claim validation & derived-from enforcement

- [x] accepted

Mechanism: `forward` still refuses an empty retrieval and a source-less chunk exactly as before, then rewrites each retrieved chunk's source to its corpus-relative label and composes the context as per-chunk blocks labeled `[label]`. The prediction must name the labels it derived the answer from; the program normalizes every claim (surrounding whitespace plus one optional bracket pair), requires each normalized claim to be inside the retrieved label set, and raises `UncitedAnswer` when the claims are empty or unverifiable — the response then cites the normalized, deduped claims, which are by construction metadata-backed; raw LM strings never reach a response, and the rejection message names only a count, never the raw claims.

Places to look:

- The signature's citations output: [src/janbot/pipeline/chat.py:47-55](../../../src/janbot/pipeline/chat.py#L47-L55)
- Labeled context composition: [src/janbot/pipeline/chat.py:114-118](../../../src/janbot/pipeline/chat.py#L114-L118)
- Claim normalization: [src/janbot/pipeline/chat.py:78-87](../../../src/janbot/pipeline/chat.py#L78-L87)
- Claim validation and rejection: [src/janbot/pipeline/chat.py:120-134](../../../src/janbot/pipeline/chat.py#L120-L134)
- Metadata-backed citation emission: [src/janbot/pipeline/chat.py:136-137](../../../src/janbot/pipeline/chat.py#L136-L137)

## Block 4 — Slice: corpus-relative rewriting & fail-closed boundaries

- [x] accepted

Mechanism: `corpus_relative(root)` closes over the resolved corpus root and maps each absolute `source_path` to its relative form, raising `UnattributableContext` when a source lies outside the root — so no unrewritable path can reach a citation, and the model context never contains an absolute path either. `create_app` builds the rewriter from `config.corpus_path`; the uncited/unverifiable rejection rides the existing `ValueError` → 500 mapping, so no new route branch exists.

Places to look:

- The rewriter: [src/janbot/pipeline/chat.py:58-75](../../../src/janbot/pipeline/chat.py#L58-L75)
- The wiring: [src/janbot/api/main.py:70-74](../../../src/janbot/api/main.py#L70-L74)
- The out-of-root refusal test: [tests/test_chat.py:371-391](../../../tests/test_chat.py#L371-L391)
- The contract description: [src/janbot/api/contract.py:35-40](../../../src/janbot/api/contract.py#L35-L40)

## Block 5 — Slice: test rows (matrix coverage)

- [x] accepted

Mechanism: the stub LM factory now scripts `citations` alongside the canned answer, and per-test overrides drive the failure rows. The happy-path pin asserts corpus-relative citations; the derived-from pin (`JANBOT_TOP_K=1`) cites only the retrieved source; the indexed-but-unretrieved row proves a source that was indexed but not retrieved can never be cited (500); the bracketed-label row proves a bracketed echo still validates (200); forced uncited and unknown-claim rows assert 500 envelopes naming the refusal with the canned answer absent; the out-of-root row asserts refusal with no path echoed; the dedup row asserts one entry per distinct source; the leak pin asserts no tmp dir, corpus path, `$HOME`, or leading `/` in any 200 body.

Places to look:

- The stub factory: [tests/test_chat.py:35-50](../../../tests/test_chat.py#L35-L50)
- Derived-from pin: [tests/test_chat.py:262-282](../../../tests/test_chat.py#L262-L282)
- Indexed-but-unretrieved: [tests/test_chat.py:284-303](../../../tests/test_chat.py#L284-L303)
- Bracketed normalization: [tests/test_chat.py:305-324](../../../tests/test_chat.py#L305-L324)
- Uncited and unknown-claim rows: [tests/test_chat.py:326-369](../../../tests/test_chat.py#L326-L369)
- Out-of-root, dedup, and leak rows: [tests/test_chat.py:371-445](../../../tests/test_chat.py#L371-L445)

## Block 6 — Periphery

- [x] accepted

- README: the Chat section rewritten to corpus-relative citations, claim validation, and rejection semantics — [README.md:85](../../../README.md#L85).
- Plan file: tasks checked, implementation notes and the review triage log appended (4 quick-lens findings patched in-build) — [plan status](../epic-rag-chat/story-citation-correctness-uncited-answer-rejection-plan.md#L6).
- Verification record: 107 passed (99 baseline + 8 new); manual eval-mode check returned a corpus-relative citation with no absolute path — [plan, Implementation Notes](../epic-rag-chat/story-citation-correctness-uncited-answer-rejection-plan.md#L104-L112).

## Status

All blocks accepted: 6 of 6. Review complete: PR #4 merged (c41d353), story 3.4 marked done.
