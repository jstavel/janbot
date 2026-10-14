# Review log: walkthrough-pr24-eval-tracer

Target: PR #24 (commit 25ea4e2, branch eval-5.1-tracer)

## 1 — Orientation — target identified

- Action: identified target as PR #24 / commit 25ea4e2 (epic-evaluation story 5.1, eval tracer); located the build plan.
- Result: review opened; block 1 (Intent) presented.
- Open: blocks 2–7 not yet reviewed.

## 2 — Block 1 Intent — accepted

- Action: presented the plan's frozen Intent verbatim; reviewer accepted without changes.
- Result: block 1 accepted; moved to block 2 (Broad strokes).

## 3 — Block 2 Broad strokes — Test move

- Action: ran the eval keyless end to end (stub embedder + DummyLM, temp SQLite MLflow store) via `python -m janbot.eval` two ways: happy path (8-item seed, stub-cited) and all-items-fail (empty index).
- Result: happy path exit 0, MLflow run FINISHED with params {model_mode eval, snapshot gpt-4o-mini-2024-07-18, temperature 0.0, seed 0} and metric answer_coverage 1.0. All-fail run exit 1, each failed item printed with its error, metric 0.0. Empty dataset refused with ValueError naming the path.
- Evidence: commands in /tmp/opencode/eval_demo.py and /tmp/opencode/eval_fail_demo.py; source src/janbot/eval/__main__.py, src/janbot/eval/dataset.py.
- Open: real locked-snapshot run through OpenRouter (needs OPENROUTER_API_KEY + chroma_db index) not performed; seed dataset content unverified against real retrieval (owner corrects in 5.2).

## 4 — Block 2 Broad strokes — accepted

- Action: block 2 accepted after the Test move; moved to block 3 (dataset contract).

## 5 — Block 3 dataset contract — Test move

- Action: ran tests/test_eval_dataset.py (8 passed) and a direct loader demonstration of each failure path.
- Result: seed loads 8 items with expected_sources; missing file → FileNotFoundError naming path; empty doc → ValueError naming path; non-list → ValueError; missing question/sources → ValueError naming index 0.
- Evidence: `uv run pytest -q tests/test_eval_dataset.py -v`; inline python demo in session.
- Note: user asked which provider is used — confirmed everything routes through OpenRouter (one invoice); DummyLM only in unit tests. Recorded intent: judge model in 5.5 must also route through OpenRouter.

## 6 — Block 3 dataset contract — accepted

- Action: block 3 accepted after the Test move; moved to block 4 (runner + metric interface).

## 7 — Block 4 runner + metrics — Thoughts, accepted

- Action: gave forward-looking thoughts (global metric registry + persistent stub; broad per-item except; global MLflow state; determinism lives in the caller). No blockers.
- Result: block 4 accepted; moved to block 5 (CLI). Notes recorded for entry 5.3 (metric registry / drop stub).

## 8 — Block 5 CLI — accepted

- Action: presented the CLI; answered the DEFAULT_MODEL_SNAPSHOT question (locked eval snapshot, routed via OpenRouter).
- Result: block 5 accepted; moved to block 6 (tests + review fixes).

## 9 — Block 6 tests — accepted

- Action: presented the test files and the three review fixes with their covering tests.
- Result: block 6 accepted; moved to block 7 (periphery).

## 10 — Block 7 periphery — accepted; wrap-up

- Action: presented periphery; answered MLflow persistence / where knowledge lives / what a compiled program is.
- Result: block 7 accepted — all blocks done. Recorded two decisions in the epic Notes: persist the compiled program (5.8/5.9) as an MLflow artifact; judge model (5.5) routes via OpenRouter.
- Open: wrap-up — commit walkthrough artifacts + epic Notes; merge PR #24.
