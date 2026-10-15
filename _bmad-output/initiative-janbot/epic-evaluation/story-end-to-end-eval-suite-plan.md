---
title: 'End-to-end eval suite'
type: 'feature'
ticket: 11
created: '2026-10-15'
status: done
baseline_revision: '338e953'
route: 'oneshot'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the recorded eval (`run_eval` → MLflow) is proven only by in-process unit tests with stub programs — nothing runs the recorded eval end to end the way an operator would, and nothing asserts the determinism promise (E5: repeated runs under the locked snapshot agree on the deterministic metrics) at the harness level.

**Approach:** one runnable e2e suite in `tests/e2e/` in two tiers. Keyless: drive `python -m janbot.eval` as a subprocess against a temp SQLite MLflow store twice (stub embedder + `DummyLM` via the CLI's injectable seams through a wrapper script), assert both runs record the same `retrieval_accuracy` / `citation_correctness` / `answer_coverage` / `retrieval_mrr` / `citation_precision` values and comparable run records. Keyed (skips without `OPENROUTER_API_KEY`, runs in `e2e-keyed.yml`): a small locked-snapshot eval over a fixed golden subset, run twice as two fresh eval processes, asserting the deterministic metrics — `retrieval_accuracy` and `citation_correctness` — agree between the runs, grounding-pinned like `test_determinism_e2e.py` rather than wording-pinned.

## Boundaries & Constraints

**Always:** the e2e suite imports no `janbot` internals (httpx/pytest/stdlib only, like the existing e2e suite); the keyed tier runs the real CLI (`python -m janbot.eval`) with the locked snapshot at the documented defaults; the keyless tier never makes a network call.

**Never:** no change to `src/janbot/eval` behavior (if a seam is missing, the wrapper-script approach absorbs it); no dataset change; no new CI workflow file (the existing two workflows already collect `tests/e2e`).

</frozen-after-approval>

## Code Map

- `tests/e2e/conftest.py:54` — `_serve` (uvicorn subprocess), `:89` `_run_cli` (CLI subprocess helper — the pattern for running the eval CLI), `:166` `_service_env`; helpers are non-importable from tests (re-declare locally or extend conftest).
- `tests/e2e/_support.py:11` — `API_KEY_ENV` / `QUESTION` shared constants; keyless-skip pattern in `test_chat_e2e.py:24`.
- `tests/e2e/test_determinism_e2e.py:50` — the keyed-skip + cold-run template to mirror; `DSPY_CACHEDIR` per-process from `conftest.py:316` `DETERMINISM_ENV`/`cold_service`.
- `src/janbot/eval/__main__.py:86` — `main(argv, env, *, embedder, lm_factory, judge)`; the seams are function args, not env vars — a subprocess needs a tiny wrapper script (like `make_index.py`) to inject the stub embedder/`DummyLM` factory keylessly.
- `tests/test_eval_runner.py:253` — how the CLI is driven keylessly in-process (stub embedder + `StubLMFactory` returning `DummyLM`); reuse the same shapes in the wrapper.
- `tests/e2e/make_index.py` — the existing non-test subprocess helper precedent; the new wrapper follows it.
- `eval/golden_dataset.yaml` — 38 items; keyed tier uses a fixed small subset (list of questions) to bound cost.
- `.github/workflows/ci.yml:36` and `e2e-keyed.yml:36` — both collect `tests/e2e`; no workflow change.

## Tasks & Acceptance

**Execution:**
- [ ] `tests/e2e/run_keyless_eval.py` -- a non-test subprocess wrapper that injects the stub embedder + `DummyLM` factory and calls `janbot.eval.__main__.main` -- the keyless driver (the `make_index.py` precedent).
- [ ] `tests/e2e/test_eval_e2e.py` -- keyless: run the wrapper twice against temp SQLite stores, assert both runs exit 0, record the same metric values, and the run records carry the params -- the keyless tier.
- [ ] `tests/e2e/test_eval_e2e.py` -- keyed: with a key, run `python -m janbot.eval` over a fixed golden subset twice (two fresh processes, each its own `DSPY_CACHEDIR`), assert `retrieval_accuracy` and `citation_correctness` agree run-to-run -- the determinism tier (skips keyless).

**Acceptance Criteria:**
- Given the keyless e2e tier, when it runs (no key), then both eval subprocesses exit 0, each records an MLflow run, and the two runs report identical metric values.
- Given the keyed tier with `OPENROUTER_API_KEY`, when it runs, then the two locked-snapshot eval runs agree on `retrieval_accuracy` and `citation_correctness`.
- Given no key, when the keyed tier runs, then it skips cleanly and the keyless suite stays green.

## Implementation Notes

Started oneshot: tests + one small wrapper script, no product code — the actual size (~200 lines across the two files) exceeded the ≤100-line estimate but stayed within the oneshot profile (mechanical, tests-only, no new seams).

- The wrapper (`run_keyless_eval.py`) self-contains its fixture: it writes the two-object corpus, the four-item golden dataset (3 pass-shaped items + one deterministic miss), and builds the index with the stub embedder, so the e2e module stays janbot-free. It strips `OPENROUTER_API_KEY` from the env the CLI sees, so the keyless tier stays keyless even under a keyed ambient.
- A `--split` passthrough was added to the wrapper after the first run (the val-split row initially evaluated all four items); `--split {all,train,val}` now forwards to the CLI, and the val row asserts the 2-item val population.
- Verification completed **including HITL**: a key was present in the environment and the user approved the real run — the keyed determinism tier passed (`test_two_locked_snapshot_eval_runs_agree_on_the_deterministic_metrics`, 2 fresh locked-snapshot processes over the val split, ~2 min), so both tiers are proven locally, not just in the weekly keyed workflow.
- Full suite: `328 passed` (325 prior + 3 new), metric values unchanged, no product code touched.

**Review refinements (quick lens, patched):** the keyed tier initially ran the real CLI at the ambient index path (vacuously green in CI — no `chroma_db/`) over `--split val` with a dead `KEYED_QUESTIONS` constant whose first question is not a golden item. The owner's decision (kept the frozen "fixed golden subset" text): the keyed tier now (a) builds a temp index from the **real** `public_profile_org` corpus via the ingest CLI subprocess and pins `JANBOT_CORPUS_PATH`/`JANBOT_INDEX_PATH`; (b) evaluates a fixed **five-item** golden subset (real questions/sources/splits, one multi-source item) authored by the test as **JSON** (valid YAML for the loader — the module keeps its stdlib/pytest-only boundary); (c) carries a **non-vacuity guard** — `retrieval_accuracy > 0` and `citation_correctness > 0` or the row fails loudly instead of passing as `0.0 == 0.0`. Also patched: the metric parser accepts only registered metric names; the keyless tier verifies the recorded run params (stdlib `sqlite3` read of the MLflow store); unused `json`/`yaml` imports resolved.

- Ticket alignment: entry 5.11's `hitl` was `false` while the plan marks the keyed verification row (hitl — it needs an operator key); set to `hitl = true`, matching the 5.15/5.16 precedent for keyed rows.

## Plan Change Log

## Review Triage Log

Review pass 1 (quick, pinned) — 6 findings: 1 high, 1 medium, 3 low (all patched), 1 false:
- the keyed tier ran the real CLI at the ambient index path — in CI (no `chroma_db/`) an empty store yields `0.0 == 0.0` vacuously — **high / patch** — the tier now builds a temp index from the real corpus via the ingest CLI subprocess and pins `JANBOT_CORPUS_PATH`/`JANBOT_INDEX_PATH`.
- `KEYED_QUESTIONS` was dead code (one question not in the dataset, one wrong split) and the tier ran `--split val` (15 items), not the plan's fixed subset — **medium / owner decision** — the owner refined: A's real-corpus index harness + B's subset at ~5 real items, JSON-authored, plus a mandatory non-vacuity guard; the frozen plan text stays ("fixed golden subset").
- the keyless tier never read the recorded run params the plan task requires — **low / patch** — stdlib `sqlite3` read of the MLflow store: distinct run ids recorded, `model_mode=eval`, config params present.
- unused `json`/`yaml` imports; `yaml` broke the suite's stdlib-only boundary — **low / patch** — cleaned; the subset dataset is authored as JSON (valid YAML for the loader), so no `yaml` import is needed.
- `citation_correctness` equality could flake (model-influenced) — **false** — the ticket's verify text explicitly requires failure-on-change between two locked-snapshot runs, and the merged `test_determinism_e2e.py` pins the same assertion class (grounded in source sets, never wording); the risk is documented in the module docstring.
- the metric parser accepted any `name: value (n=` line — **low / patch** — restricted to the registered metric names.

## Verification

**Commands:**
- `uv run pytest -q tests/e2e/test_eval_e2e.py` -- expected: keyless tier green, keyed tier skipped.
- `OPENROUTER_API_KEY=… uv run pytest -q tests/e2e/test_eval_e2e.py` (hitl) -- expected: keyed tier green (two agreeing locked-snapshot runs).
- `uv run pytest -q` -- expected: whole suite green, unchanged values.
