---
title: 'Detection and the refusal-gate split'
type: 'feature'
ticket: 2
created: '2026-10-15'
status: done
baseline_revision: 'd9c4711'
route: 'full'
route_source: 'auto'
risk: 'high'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** entry 1 delivered the decline *shape*, but detection is not real. 5.13 measured **`refusal_pass_rate` 0.3333** — the locked snapshot **answered** the salary and managed-Kubernetes questions (only notice-period declined; `spurious_refusal_rate` 0.0). The scoped store always returns a full top-k window, so a decline is **not** "retrieval returned nothing" — it is the model's judgement "can I answer from this context?", and it fails 2 of 3. Detection must be **relevance-based**, not emptiness-based.

**Approach:** settle the recorded `unknown` (the detection method) **by measurement**, ordering the candidates by **E3-compliance, not cost**:
- **(b) retrieval relevance threshold — measured first.** It is the **only robustly deterministic candidate**: it runs *before* the LM call, so the decline outcome is a function of the embeddings, not the model. It needs a **thin store extension** — expose the top similarity (Chroma already returns the distance; `query` discards it), a principled relevance signal generally useful for diagnostics (the probes, the per-source cap, the embedder swap) — recorded as a **store-owned extension** (epic-ingestion), not a 7.2 hack. It produces a **new decline signal** (`LowRelevance`) added to the API's `(EmptyRetrieval, UncitedAnswer) → insufficient` mapping **and** the eval runner's decline mapping, so the decline **shape** is identical to production.
- **(a) prompt-level — second.** The decision stays with the model, so its **outcome is not deterministic** (the fixed prompt is; the model's decline is not). It **may fail E3 and be dropped on that ground**, not merely on cost.
- **(c) classifier — last resort** (cost + determinism).

**Criterion:** `refusal_pass_rate` UP with `spurious_refusal_rate` FLAT (do not buy declines with false declines — the symmetric-floor logic), plus the in-corpus gate metrics (`citation_correctness`/`faithfulness`) not regressed. **n=3 caveat, on record:** `refusal_pass_rate`'s population is **3 val items**, so "UP" is +1 item — exact (no run noise) but a coarse sample of the out-of-corpus population, the same "breadth gates" limit as the gate at n=15, only coarser. **7.2 cannot author more refusal items** (golden items are `epic-evaluation`'s boundary), so the win is **directional, not decidable**, until entry 20 grows class 8 — and the record must say so.

## Boundaries & Constraints

**Always:** candidates ordered (b) → (a) → (c), each measured on the val split under the locked snapshot against `9c7260da`; the criterion is the pair; the winner verified deterministic across two runs (E3) — **a candidate that cannot be deterministic is dropped, whatever its ratio**; the decline shape is identical to production (any new signal maps to the same `insufficient` reply); the gate split is preserved; the choice and every candidate's numbers are recorded in the epic Notes, with the n=3 win labelled directional.

**Never:** no dataset change (authoring class-8 items is epic-evaluation's); no gate-rule change; no metric-definition change; no optimization stage (8/9); no change to the decline shape or the `/chat` contract.

**Decision (order + determinism):** (b) first — the only robustly deterministic candidate (pre-LM, embedding-driven); (a) second — the model owns the decision, so its outcome may not be deterministic and the candidate is measured with that risk explicit; (c) last. The store score extension is owned by the store (ingestion), recorded as such.

## Code Map

- `src/janbot/store/chroma.py:224-269` — `query` returns `[{id, text, source_path, breadcrumb}]` with **no similarity score**; the top distance is already available from Chroma and discarded — the **store extension**: return it (the principled relevance signal for (b) and for diagnostics).
- `src/janbot/pipeline/chat.py:126-171` — `forward`: where the relevance gate (b) sits *before* the LM call (`:147`); the `EmptyRetrieval`/`UncitedAnswer` (decline) vs `FabricatedCitation` (refused) split.
- `src/janbot/pipeline/chat.py:38-52` — the exception family; a new `LowRelevance` decline signal joins it (candidate (b)).
- `src/janbot/api/main.py:120-123` — the decline mapping `(EmptyRetrieval, UncitedAnswer) → insufficient`; the new signal is added here so the reply shape is unchanged.
- `src/janbot/eval/runner.py` — the 5.13 decline mapping (only `EmptyRetrieval`/`UncitedAnswer` → the `insufficient` outcome); **the new signal must be added here too**, or the eval records a low-relevance decline as an error.
- `src/janbot/pipeline/chat.py:54-62` — `GroundedAnswer`'s instruction (candidate (a)).
- `src/janbot/eval/metrics.py` — `refusal_pass_rate` / `spurious_refusal_rate` (the measurement predicate).
- `_bmad-output/initiative-janbot/epic-graceful-decline/epic-graceful-decline.md` — E1–E3, the `api/`+`pipeline/` boundary (the store extension is flagged as store-owned).
- Reference: MLflow run `9c7260da` (`refusal_pass_rate` 0.3333, `spurious_refusal_rate` 0.0, in-corpus gate metrics 0.7333 ×3, n=15).

## Tasks & Acceptance

**Execution:**
- [x] `src/janbot/store/chroma.py` -- expose the top similarity (the discarded Chroma distance) -- the store-owned relevance signal (b) needs. *(Done: the `similarity` key in both query paths; ordering/scope/k unchanged.)*
- [x] `src/janbot/pipeline/chat.py`, `src/janbot/api/main.py`, `src/janbot/eval/runner.py` -- the relevance gate: a `LowRelevance` decline below a swept θ, mapped to the same `insufficient` reply in both the API and the eval runner -- candidate (b), the decline shape unchanged. *(Done.)*
- [x] measure candidate (b) across θ on the val split (keyed; hitl) -- pick the θ meeting the criterion; record the sweep and the n=3 caveat. *(Done: the no-model probe fixed the θ band (0.2528, 0.2787); the keyed run at θ=0.26 — MLflow `bc1b2f55` — confirmed `refusal_pass_rate` 0.667 with `spurious_refusal_rate` 0.0.)*
- [x] `src/janbot/pipeline/chat.py` -- candidate (a), only if (b) fails: a strengthened decline instruction -- measured with the E3 risk explicit; dropped if its outcome is not deterministic. *(Not run: (b) met the criterion; (a) remains the unmeasured fallback, its E3 risk on record.)*
- [x] candidate (c), only if (a)/(b) fail: a classifier -- the last resort. *(Not run, same reason.)*
- [x] verify the winner: the gate split (in-corpus cites, fabricated refused, out-of-corpus declines) and **two identical runs** (E3) -- correctness + determinism. *(Done: the second run `54b67a9f` declines the same two items.)*
- [x] record the chosen method, the numbers, the rejected candidates, and the directional (n=3) label in the epic Notes -- the decision record. *(Done in `epic-graceful-decline.md`.)*

**Acceptance Criteria:**
- Given each candidate, when the val split runs under the locked snapshot, then `refusal_pass_rate` / `spurious_refusal_rate` are recorded and the in-corpus gate metrics are compared to `9c7260da`; the n=3 result is reported as directional.
- Given the adopted method, when measured, then `refusal_pass_rate` rises with `spurious_refusal_rate` flat (0.0) and no in-corpus gate-metric regression — the pair, not one side.
- Given the adopted method, when the same out-of-corpus question runs twice under the locked snapshot, then it declines the same way (E3); a candidate whose outcome is not deterministic is dropped.
- Given an in-corpus question, then it still returns a cited answer; given a fabricated cited answer, then it is still refused (the gate split); given a low-relevance decline, then the reply shape is the identical `insufficient` reply.
- Given the epic Notes, then the method, its numbers, every rejected candidate, and the directional caveat are recorded.

## Implementation Notes

- Candidate (b) adopted: `JANBOT_RETRIEVAL_THRESHOLD`... — the knob is `JANBOT_RELEVANCE_THRESHOLD` (default **0.26**, the measured θ, shipped); the gate runs before the LM call; `LowRelevance` joins the API's and the eval runner's decline mappings (the shape is production-identical). Candidate (a)/(c) not run — (b) met the criterion.
- **The shipped default surfaced a second-order finding**: with the gate armed, the **BootstrapFewShot compile** gated low-similarity train items (the stub-embedder test failed its pairs-coverage assertion). Fix: the compile **disables the relevance gate** (`_disable_relevance_gate`) — the compile must attempt every train item; the gate is a runtime `/chat` behaviour. A focused test compiles with the threshold armed at 0.9 and asserts full pairs coverage.
- The full verification after the review patches: `uv run pytest -q` → **432 passed**.

## Plan Change Log

- 2026-10-15 (review pass 1): the shipped default was adopted (`DEFAULT_RELEVANCE_THRESHOLD = 0.26`) after the review found the inert default did not deliver the epic's done-when; negative thresholds now fail fast; the runner docstrings updated. Known-bad state avoided: a "detection is real" story whose default still answered out-of-corpus questions. KEEP: the (b)-first candidate order, the n=3 directional label, the store-owned similarity extension, and the compile-path gate disable.

## Review Triage Log

Review pass 1 (quick, pinned) — 8 findings: 5 patched, 2 doc-reconciled, 1 patch (self-inflicted, found by the full run):
- the shipped default left detection OFF (the epic's done-when unmet; the inert default was an implementation choice, not a plan mandate) — **high / patch** — `DEFAULT_RELEVANCE_THRESHOLD = 0.26` shipped, README/tests updated; the adoption is recorded in the epic Notes with the directional caveat.
- the decision-record θ interval included (0.2787, 0.279), which would decline an in-corpus item — **low / patch** — corrected to (0.2528, 0.2787).
- "no θ declines the Kubernetes item without six in-corpus items" undercounted — **low / patch** — nine sit below 0.5111.
- candidates (a)/(c) were never measured while the plan's Always/AC said each candidate is measured — **low / patch (doc)** — the Execution's "only if (b) fails" governs; (b) met the criterion so (a)/(c) were not run; the Notes record it and the AC wording is reconciled here.
- the ticket's recorded `unknown` (the detection method) was left set although the story settles it — **low / patch** — cleared in the ticket store.
- a negative `JANBOT_RELEVANCE_THRESHOLD` armed the decline path while being effectively inert — **low / patch** — fail fast on negatives, with a test.
- the store extension was built inside 7.2 without an epic-ingestion ticket — **low / patch (doc)** — recorded as a store-owned extension in the epic-ingestion Notes (the change is disclosed and used beyond 7.2).
- the runner docstrings omitted the new params — **low / patch** — added.
- (found by the full run) the shipped gate broke the BootstrapFewShot compile's pairs coverage — **high / patch** — the compile disables the relevance gate (a runtime behaviour), with a focused test.

## Design Notes

- **Candidate order is E3-compliance.** (b) is the only candidate whose *outcome* is deterministic — it runs before the LM call and is embedding-driven, so the same question declines the same way across runs. (a) keeps the decision with the model: a fixed prompt is deterministic, but the model's decline is not, so (a) is the **least** E3-compliant candidate and may be dropped on that ground. (c) inherits (a)'s determinism risk and adds cost.
- **n=3 power, acknowledged.** `refusal_pass_rate` over 3 val items takes values {0, 0.333, 0.667, 1.0} — a +1-item step is exact but a 3-item sample of the out-of-corpus population. This is the gate's "breadth gates optimization" limit, coarser; 7.2's win is therefore **directional**, and a decidable one requires entry 20 to grow class 8 (7.2's boundary excludes golden items).
- **The store extension is principled.** Chroma already computes the distance and `query` discards it; exposing the top similarity is the right relevance signal for (b) and useful generally (the deterministic probes, the per-source cap, the embedder swap). It is a store-owned change (epic-ingestion), recorded as such — not a 7.2 shortcut.
- **One decline shape.** A new `LowRelevance` signal joins `EmptyRetrieval`/`UncitedAnswer` in **both** the API's and the eval runner's decline mapping, so production and the eval observe the identical `insufficient` reply.

## Verification

**Commands:**
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- per θ / candidate: `refusal_pass_rate` / `spurious_refusal_rate` + the gate metrics recorded in MLflow, compared to `9c7260da` (directional at n=3).
- a second identical run of the winner (hitl) -- expected: the same declines (E3 determinism).
- `uv run pytest -q` -- expected: green; the gate split covered (in-corpus cites, fabricated refused, out-of-corpus/low-relevance declines).
