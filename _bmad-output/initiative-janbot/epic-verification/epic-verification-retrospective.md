---
epic: epic-verification
date: 2026-10-13
verdict: accepted-with-open-items
criteria: declared
headless: false
---

# epic-verification — Retrospective

## Epic summary

**Epic:** `epic-verification` — "End-to-end tests & CI" (covers CAP-7). Outcome: every change to JanBot is verified by an automated, deterministic endpoint suite that turns red when the contract or grounding breaks. Done-when: (1) a pytest+httpx suite exercises `/chat` over HTTP; (2) contract shape, ≥1-citation rule, malformed-input error handling; (3) a determinism test passes twice at `temperature=0`; (4) green in CI on every push, a broken contract turns it red; (5) imports no Python-internal modules.

**Tickets** (all `done`; `pending_tickets` empty):

| ref | title | status | range (plan `baseline_revision` → next baseline) |
|-----|-------|--------|--------------------------------------------------|
| 4.1 | Port-only e2e harness (tracer bullet) | done | `43ae815` → `d3a0672` |
| 4.2 | Contract & error-envelope coverage through the port | done | `d3a0672` → `98c6511` |
| 4.3 | Grounding coverage through the port | done | `98c6511` → `1a3d45c` |
| 4.4 | Determinism at the locked snapshot | done | `1a3d45c` → `fc33f63` (+ follow-up fix in the 4.5 range) |
| 4.5 | CI wiring + broken-contract negative | done | `fc33f63` → `0bdf934` |
| 4.6 | Refactor sweep | done | `0bdf934` → `3b44025` (HEAD, inferred) |

Tickets still at `built`: none (all closed to `done` via `bmad-walkthrough` acceptance).

**Evidence inventory**

- Epic file: `epic-verification/epic-verification.md` (Done-when declared → `criteria: declared`).
- Initiative requirements: `initiative-janbot.md` → `spec-janbot.md` CAP-7 (and CAP-6, re-scoped by the 4.4 fix).
- Entries: `tickets.py find 4.1…4.6` (descriptions/verify/covers). 4.3 and 4.4 were re-scoped mid-epic; their `verify` text was updated (4.3 → startup refusal + sourceless 503; 4.4 → same-source grounding).
- Story files: none (no ticket had a reviewed/refined story file).
- Plans: one per ticket; each carries a Review Triage Log + Verification; 4.4 gained a Plan Change Log (post-merge re-scope).
- Diff ranges/commits: `git_evidence.py` per the ranges above. **Attribution caveat:** story 4.4's follow-up fix (`9b2fbaf`, `751c76c`) landed after 4.5's recorded baseline, so it appears inside the 4.5 range; attributed to 4.4 here, not 4.5.
- Walkthrough narratives + logs: `walkthrough-pr14/15/16/17/18/19/20-*` (7 reviews; PRs #14–#20).
- Session logs: `.agent-shell/transcripts/2026-10-13-*.md` (build sessions, available).
- Previous retrospective: `epic-rag-chat/epic-rag-chat-retrospective.md`.

**Missing evidence:** none material. No story files (expected); session logs present.

## Findings

Scope note: the three code lenses (adversarial, edge-case-hunter, verification-gap) were run **inline** over the code diff (`43ae815..HEAD -- tests/ .github/ README.md`) — the lens-subagent launch was cancelled, so this is the narrowed inline scope the workflow permits. The aggregate views were derived by one delegated subagent and each finding below was re-checked against the primary source.

### Verification lens (highest value)

- **F1 — the keyed rows never run in CI, so Done-when 1 and 3 are unverified in the normal verification path.** `test_chat_e2e.py:26-29` and `test_determinism_e2e.py:52-55` `skipif` without `OPENAI_API_KEY`; CI runs `uv run pytest` keyless, so the happy path and the determinism row **skip** on every push. The epic's headline — "an automated suite that turns red when the contract or grounding breaks" — holds in CI only for the keyless rows (422/503, grounding-refusal, contract self-test). *gap_shape: broken-verification-gap.* Source: `test_chat_e2e.py:26-29`, `test_determinism_e2e.py:52-55`, `.github/workflows/ci.yml`, `epic-verification.md` Done-when 1/4. **Disposition: accept as-is** — this is the epic's recorded hitl decision (`epic-verification.md:50`), but the caveat is worth stating: green CI is not full verification.

### Spec-to-implementation reconciliation

- **F2 — the epic decision note still says the fixture index is "committed", but the harness builds it at session setup and never commits it.** `epic-verification.md:52` ("entry 1 owns building and **committing** the fixture index") contradicts shipped `conftest.py:10-13` ("not committed: a ChromaDB index bakes absolute `source_path` values") and the 4.1 plan's Change Log (the review renegotiated this). Stale record. Source: `epic-verification.md:52` vs `tests/e2e/conftest.py:10-13`, `story-port-only-e2e-harness-…plan.md` Plan Change Log. **Disposition: fix now (spec reconciliation).**
- **F5 — `make_index.py` imports `janbot.store` inside `tests/e2e/`; `test_response_contract.py` imports `janbot.api.contract`.** Both are intentional (subprocess helper; in-`tests/` self-test) and documented, but they sit against Done-when 5's "imports no Python-internal modules", which is true of the *e2e modules* only. Source: `tests/e2e/make_index.py:28`, `tests/test_response_contract.py:20`, `epic-verification.md:33`. **Disposition: accept as-is** (documented deviation).

### Duplication / size (aggregate)

- **F3 — the e2e harness duplicates several small things, and `conftest.py` grew to 341 lines.** Repeated: `OPENAI_API_KEY_ENV`+skipif (`test_chat_e2e.py:21,26-29` ‖ `test_determinism_e2e.py:30,52-55`), the `QUESTION` literal (both), the 503 `{detail}` envelope block (`test_contract_e2e.py:42-45` ‖ `test_grounding_e2e.py:48-51`), and the `subprocess.run` boilerplate (`conftest.py:75-87` ‖ `:99-110`). `conftest.py` holds 8 fixtures plus port/process/index helpers. Story 4.6 deliberately scoped most dedup out (the skipif-to-fixture move risks breaking the keyless-no-index build). Source: the cited lines; `git_evidence.py` conftest churn (~+395/-54). **Disposition: defer** (tracked cleanup).

### Robustness residuals (accept)

- **F4 — the retry and the log assertions rest on fragile strings.** `_serve`'s retry keys on the substring "address already in use" and does not confirm the responder is the spawned process; `_start_service_expecting_exit` asserts on log substrings ("1 chunk(s) whose source_path lies outside"). A uvicorn message change or a local port thief would slip either. Source: `tests/e2e/conftest.py:68-70,190-223`, `tests/e2e/test_grounding_e2e.py:26-36`. **Disposition: accept as-is** (narrow; the build reviews already softened the docstring claim).

## Behavior verification

- **Keyless suite (epic final state):** `env -u OPENAI_API_KEY uv run pytest -q` → **158 passed, 2 skipped**; `tests/e2e` → 6 passed, 2 skipped. Every keyless row is exercised.
- **Keyed rows (run this session):** 4.1 happy path passed; 4.4 determinism **flaked ~4/5 runs before its fix** (byte-identical bodies vs provider wording variance — captured pair `…and evaluation before starting JanBot.` vs `…and evaluation.`, same `profile.org`), and is **8/8 green after the fix** (same-source grounding, `9b2fbaf`). This is the epic's one runtime observation of a real-model path.
- **CI:** `main` CI green on every epic push/PR (PRs #14–#20 all `success`).
- Production runtime behavior was **not changed** by this epic (`git diff --name-only 43ae815..HEAD -- src/` is empty); the changed "flow" is the verification path, exercised above.

## Previous-retro follow-through

Previous epic `epic-rag-chat` (verdict accepted-with-open-items). Its action items and whether they landed before/with `epic-verification`:

- **#1 Envelope robustness** → **landed** — `hardening-chat-error-envelope` (PR #9, `3e21e59`).
- **#2 Citation ordering (retrieval order)** → **landed** — PR #10, `40eb40d`; re-confirmed by the 4.6 sweep (`pipeline/chat.py:147-152`).
- **#3 Rewriter coverage + guard alignment** → **landed** — PR #12, `0cfc7ce`.
- **#4 `JANBOT_TEMPERATURE` finite validation** → **landed** — PR #11, `eab9b80`.
- **#5 Serve↔ingest root alignment** → **landed** — PR #13, `1338643`.
- **#6 Reverted in-place corpus edit** → **landed** — `68554da`.
- **#8 "stage only intended files"** → **no evidence of a dedicated change**; practice held in this epic (per-story explicit staging).
- **#9 "epic-verification is where the real end-to-end evidence must land"** → **landed** — this epic delivers the port-only suite; the keyed half remains hitl (F1).
- **Deferred (chunk-id stability; scoped-query over-fetch)** → **still open** in `deferred-work.md` (not this epic's scope).

## Action items

Proposed; the human decides what to execute.

**Fix now (spec reconciliation):**
1. **Reconcile `epic-verification.md:52`** — the fixture-index decision note said "committed"; changed to "built at session setup, not committed" (matching `conftest.py:10-13` and the 4.1 plan Change Log). *(owner: maintainer)* — **applied 2026-10-13.**

**Defer (tracked):**
2. **Optional keyed CI job** — a scheduled/manual workflow that runs `tests/e2e` with a key so Done-when 1/3 are exercised by machine, not only by recorded manual runs. Closes the F1 caveat without keying every push. *(owner: next CI change)*
3. **e2e harness dedup follow-up** — factor the shared key model-key skip (via a marker or a `require_model_key` fixture that does not defeat the keyless-no-index property), the `QUESTION` literal, the 503-envelope assertion, and the `subprocess.run` boilerplate; consider splitting `conftest.py`'s port/process helpers from its fixtures. *(owner: next verification change)*

**Accept as-is (recorded so later runs stop re-flagging):** F1 (keyed rows hitl), F5 (helper imports), F4 (string-keyed robustness).

**Process lessons:**
- **P1 — a hitl row whose real behavior only appears with a key must be exercised with a key at least once before "done".** 4.4's byte-identical assertion passed two reviews and a walkthrough, then flaked ~4/5 keyed runs; only running it keyed exposed it. The reviews reasoned about the code, not the live model.
- **P2 — the epic-close cross-ticket lens pass (this retrospective) is the right gate** (epic-rag-chat lesson #7, now standing practice); it surfaced F1/F2, neither visible inside a single story.

## Acceptance verdict

**accepted-with-open-items** — criteria `declared`.

- All six tickets are finished; `pending_tickets` is empty, so the verdict is not forced to *rejected*.
- Done-when 1, 3 delivered (keyed; skips in CI — F1); 2 delivered keyless; 4 delivered (test job + `contract-negative` job); 5 holds for the e2e modules (F5 documents the helper exceptions). No production code changed.
- Named findings remain deferred/tracked (F2 fix-now; F3, and the keyed-CI item, deferred). None leaves a ticket unfinished.
- Strict reading: CI green does not exercise the model-dependent rows (F1), so "verified in CI" covers the deterministic half of the epic. A human may prefer that caveat recorded as an open item rather than accepted.

## Open questions

- Should the keyed rows run in CI (added cost + secret) or is "keyless CI + recorded keyed runs" the intended contract? This decides whether F1 stays accepted or becomes a follow-up story.
