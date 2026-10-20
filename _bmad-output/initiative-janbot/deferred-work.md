# Deferred work

## Resolved

- source_plan: `_bmad-output/initiative-janbot/epic-ingestion/story-config-contract-corpus-root-hardening-plan.md`
  summary: Define the symlink policy for the fail-closed scope filter before entry 2.4 builds it, since `config` canonicalizes paths with `.resolve()` while the public corpus folder holds symlinked files.
  status: **resolved** — delivered by `epic-ingestion` story 2.4 (symlink-aware fail-closed scope filter, `src/janbot/ingest/scope.py`).

## Carry-over to epic-rag-chat (2026-10-12, pinned so they do not disappear)

- **Store scope ownership.** `VectorStore.query` returns global top-k with no scope filter; safe today only because fail-closed ingestion keeps the collection purely public. Owned by `epic-rag-chat` entry **3.6** (Grounding boundary) — add a scope/top-k guarantee at the store boundary, per epic-rag-chat Done-when 5.
- **DW3 evidence-strength gap.** Refusal is only jointly verified and "no retrieval change" is not a ranked comparison; removing either scope filter alone would go uncaught. Owned by `epic-rag-chat` entry **3.7** (Scope/refusal evidence hardening) — direct-refusal test handing an out-of-scope path to `index_corpus` plus a ranked-comparison assertion.
- **Citation-path and chunk-id stability carries** from the epic-ingestion retrospective (citation path leak, id stability) land in `epic-rag-chat` entry **3.4** (Citation correctness) and the epic's review.

## Closed by remediation (2026-10-12)

- **Symlink-by-location wording.** Accepted policy (location governs) now reconciled into `spec-janbot.md` CAP-4 and `epic-ingestion.md` Done-when 3 with a dated `Decision:` line in the epic Notes. No open item remains.

## Carry-over (2026-10-13)

- source_plan: `_bmad-output/initiative-janbot/epic-rag-chat/story-determinism-at-the-locked-snapshot-plan.md`
  summary: CHANGELOG.md `[Unreleased]` gains no entry for the new `JANBOT_SEED` variable, the new `Config.seed` field, or the eval `build_lm` seed pin.
  evidence: The repo states "All notable changes to this project are documented in this file", but the section is stale since story 2.1 (`git log -- CHANGELOG.md` ends at `2d1aa2d`) and stories 3.1–3.4 added no entries either — a pre-existing repo-wide gap, not caused by this change.

- source_plan: `_bmad-output/initiative-janbot/epic-rag-chat/story-determinism-at-the-locked-snapshot-plan.md`
  summary: Keyed eval-mode double-run not performed — real provider-level reproducibility of the locked snapshot is not demonstrated.
  evidence: The plan's `## Verification` lists the keyed manual check but it was never run; the automated determinism rows use the stub `DummyLM`, which proves no per-request nondeterminism but not provider reproducibility (plan `## Design Notes`). It backs the ticket's own `verify` ("two runs … identical under the locked snapshot"). Run: start the app in eval mode with `OPENROUTER_API_KEY` set, post the same question twice, diff the bodies.
  status: **resolved** — delivered by `epic-verification` story 4.4 (`tests/e2e/test_determinism_e2e.py`): two cache-cold eval service runs (pinned snapshot, temperature `0`, seed `0`), one `POST /chat` each, grounding the answer in the same corpus sources (keyed/hitl). Answer *text* is not asserted byte-identical — the provider does not guarantee it at temperature 0.

## Sweep decisions (2026-10-13, epic-rag-chat story 3.8)

- source_plan: `_bmad-output/initiative-janbot/epic-rag-chat/story-refactor-sweep-plan.md`
  summary: Chunk-id stability — ids embed a document-order ordinal, so inserting a heading re-ids the tail; the fix is a content hash (source+breadcrumb) plus a scope-key reconcile.
  evidence: Not cleanup-only: it changes chunk ids → requires a re-index, edits `ingest/org.py` (outside the epic-rag-chat boundary), and rewrites ingestion tests. The epic decided it was a review item, not an entry. Deserves its own ticket; do not fold into a cleanup sweep.

- source_plan: `_bmad-output/initiative-janbot/epic-rag-chat/story-refactor-sweep-plan.md`
  summary: Scoped `VectorStore.query` over-fetches the whole collection when scoped; narrowing the fetch is a deferrable optimization.
  evidence: The scope guarantee is correct today; only cost scales with corpus size. `store/` is outside the 3.8 cleanup boundary, and this is performance, not correctness.

## Deferred from the epic-rag-chat retrospective (2026-10-13)

- source_plan: none
  summary: Citation ordering — emit citations in retrieval-`sources` order rather than LM-claim order, to close the DW4 nondeterminism channel.
  evidence: `src/janbot/pipeline/chat.py:137` builds citations via `dict.fromkeys(normalized)` in model-claim order; recorded in the epic-rag-chat retrospective. Split out of the fix-now set; the lead goal is envelope robustness.
  status: **resolved** — the code now emits citations in retrieval order (`src/janbot/pipeline/chat.py:147-152`, `dict.fromkeys(sources)`), so the claim-order nondeterminism channel is closed. Confirmed by the `epic-verification` refactor sweep (story 4.6).

- source_plan: none
  summary: Rewriter guard coverage + alignment — tests for `corpus_relative`, and align its `source_path` absolutization with the store's.
  evidence: `UnattributableContext`/`corpus_relative` appear in no test after 3.6; the store's `_within_scope` uses `os.path.abspath` (`store/chroma.py:57`) while the rewriter uses `relative_to` with no absolutization (`pipeline/chat.py:69`). Recorded in the epic-rag-chat retrospective. Split out of the fix-now set.
  status: **resolved** — `corpus_relative` now absolutizes via the located path and fail-closes, matching the store's scope (`src/janbot/pipeline/chat.py:59-80`); delivered by the hardening PR #12 (`0cfc7ce`).

- source_plan: none
  summary: Reject non-finite `JANBOT_TEMPERATURE` (nan/inf) at config load.
  evidence: `src/janbot/config.py:115-124` parses float only; `load_config({'JANBOT_TEMPERATURE':'nan'})` yields `nan` (verified), silently voiding the 3.5 eval determinism pin. Recorded in the epic-rag-chat retrospective. Split out of the fix-now set.
  status: **resolved** — `load_config` now rejects non-finite `JANBOT_TEMPERATURE` (`src/janbot/config.py:126`); delivered by the hardening PR #11 (`eab9b80`).

- source_plan: none
  summary: Serve↔ingest corpus-root alignment — cross-check the serve scope against index provenance, or document the operational contract.
  evidence: Ingestion writes through an unscoped store (`ingest/__init__.py`) while serving scopes to `JANBOT_CORPUS_PATH` (`api/main.py:61`); a mismatched root silently changes the citation form or 503s everything. Recorded in the epic-rag-chat retrospective (open question). Split out; design decision.
  status: **resolved** — the startup cross-check refuses to serve an index holding out-of-scope chunks (`src/janbot/api/main.py:60-72`); delivered by the hardening PR #13 (`1338643`). The broader-serve-root direction remains tracked separately below.

- source_plan: none
  summary: `public_profile_org/ai-fast-failback.org` was edited in-place inside the 3.6 PR — **resolved: reverted** (the original "working groups formed" is correct), 2026-10-13.
  evidence: Commit `457bc70` (story 3.6) changed the SYNOPSIS line; the wrong edit has been reverted, so the corpus again matches its pre-3.6 state.

- source_plan: `_bmad-output/initiative-janbot/plan-serve-ingest-root-alignment.md`
  summary: The startup cross-check does not catch a serve corpus root *broader* than the ingest root (all indexed chunks stay in scope; only the citation label shifts).
  evidence: `out_of_scope_sources()` flags only stored chunks outside `config.corpus_path`; the index records no ingest-root provenance. Covering that direction needs persisted provenance (option C, edits `ingest/`). Low harm: the index holds only the public corpus, so no out-of-corpus content can be retrieved; only the label form changes.

## Reverted edits (2026-10-13)

- `public_profile_org/ai-fast-failback.org` — the in-place SYNOPSIS change that rode into the 3.6 commit `457bc70` ("working group formed") was **reverted**: the original "working groups formed" is correct (initiative-wide, not from the one idea). The corpus again matches its pre-3.6 state. Source: `epic-rag-chat/epic-rag-chat-retrospective.md` action item 6.

## Review defers (2026-10-14, epic-evaluation story 5.1 — eval tracer)

- source_plan: `_bmad-output/initiative-janbot/epic-evaluation/story-tracer-bullet-seed-dataset-run-the-pipeline-record-a-metric-plan.md`
  summary: The new eval tests import `dspy.utils` before `janbot.store`, a latent numpy-proxy hazard that only survives because `mlflow.tracking` loads numpy in between.
  evidence: `python -c "import pytest, yaml; from dspy.utils import DummyLM; import janbot.store"` fails (`TypeError: data type 'bool' not understood`) while the same sequence with the mlflow import between succeeds. Not introduced here — it mirrors the pre-existing `tests/test_chat.py` pattern.

- source_plan: `_bmad-output/initiative-janbot/epic-evaluation/story-tracer-bullet-seed-dataset-run-the-pipeline-record-a-metric-plan.md`
  summary: The new `janbot.eval` package, its CLI, `MLFLOW_TRACKING_URI`, and the `mlflow`/`pyyaml` deps are undocumented in README/ARCHITECTURE/CHANGELOG.
  evidence: `.github/PULL_REQUEST_TEMPLATE.md` requires doc updates; `CHANGELOG.md` `[Unreleased]` is already stale repo-wide (see the 2026-10-13 carry-over above), and the README package layout / Configuration table name no eval entry. Deferred to a docs pass or the epic's closing sweep.

## Deferred from the golden-question brainstorm (2026-10-14)

- source_plan: `_bmad-output/initiative-janbot/brainstorm-golden-dataset-questions/.memlog.md`
  summary: Four proposed golden items are not yet corpus-grounded: (1) a proof-map — "which projects can I inspect, and where" with the full URLs; (2) a self-proving JanBot item — "anything I can use right now"; (3) a weakest-proof/honesty item naming the CoreNet/Twisted work as having no public artifact; (4) a remote-stance item carrying the customer-facing nuance (Brno 1–2×/week, Prague 1×/month, "customers pay our bills").
  evidence: The corpus is immutable per `~/org/corpus/README.org` (update = new object), and none of these facts exists in `public_profile_org/` — each needs a new corpus object before an item can be grounded. The owner is still adding questions.

- source_plan: `_bmad-output/initiative-janbot/brainstorm-golden-dataset-questions/.memlog.md`
  summary: Two public-surface backlog items raised by the brainstorm — complete the LinkedIn profile as a JanBot-citable reference (backlog 7) and publish the CV publicly via a git-crypt repo + Pages (backlog 8) — plus the URL allow-list (backlog 9) they feed.
  evidence: recorded so the family is visible; the LinkedIn/CV URLs become allow-list entries once live.
- source_plan: `_bmad-output/initiative-janbot/epic-evaluation/story-refusal-item-class-and-refusal-metrics-plan.md`
  summary: gate-rule.md must be re-pointed at the new reference (run 9c7260da, dataset sha 531186fe…) — the 5.13 re-baseline superseded e635c2bf but the task forbade touching gate-rule.md.
  evidence: the epic-evaluation Notes entry (2026-10-15, entry 13) records the supersession; `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md:7-9` still names e635c2bf with the old dataset sha 4656f824…, so a future gate comparison against the written rule would use the superseded run.
  status: **resolved** (2026-10-15) — the gate rule's reference pointer now names `9c7260da` (dataset sha `531186fe…`); the rule body is unchanged (a reference-pointer update, not a rule change), justified because the re-baseline reproduced every pre-existing metric identically (`citation_correctness`/`faithfulness`/`retrieval_accuracy` 0.7333 ×3, n=15). See the epic-evaluation Notes entry (2026-10-15, gate reference re-point).

## Someday (2026-10-15)

- source_plan: `_bmad-output/initiative-janbot/epic-ingestion/story-source-diverse-retrieval-window-plan.md` (2.11)
  summary: Per-source chunk cap <= N (MMR-style relevance/diversity, e.g. N=2) — keeps source diversity WITHOUT strict dedup's within-source depth loss.
  evidence: 2.11's strict dedup (run 0c01ba33) regressed faithfulness 0.7333 -> 0.4667 (item 22 lost its second edeposit.org subtree -> a new reference failure); the follow-up probe is deterministic (free, no model) — over {23,25,29,32} and the 2.11-destabilised {14,17,19,22,36}.
  status: **someday** — no blocker; do when there is capacity. Not scheduled.

## Review defers (2026-10-16, epic-graceful-decline story 7.3 — decline reason)

- source_plan: `_bmad-output/initiative-janbot/epic-graceful-decline/story-decline-variants-a-personal-question-reply-plan.md`
  summary: The full test suite needs more open file descriptors than the common default soft limit (1024); on such a shell the store tests fail with `OSError: [Errno 24] Too many open files` and the suite looks red when it is not. The store tests may not be closing their Chroma clients.
  evidence: Reproduced — `ulimit -n 1024` gives EMFILE failures in `tests/test_store_similarity.py` / `tests/test_store_window.py` (plus an EMFILE during pytest's temp-dir cleanup); `ulimit -n 16384` (and the dev default 524288) gives **464 passed / 0 failed**. This is **not** a correctness defect and **not** order-sensitivity — a reproducibility/hygiene item (hypothesis: unclosed Chroma clients in the store tests). Do not fix in 7.3.

- source_plan: `_bmad-output/initiative-janbot/epic-evaluation/story-metric-population-inconsistency-errored-items-are-coverage-m-plan.md`
  summary: Full suite is red when the shell's file-descriptor soft limit is low; the store tests fail with SQLite CANTOPEN. Pre-existing, not a metric-population defect.
  evidence: Reproduced 2026-10-20 with `ulimit -n 1024`: **21 failed / 493 passed**, all in `tests/test_store_scope.py`, `tests/test_store_similarity.py`, `tests/test_store_window.py`; first error `chromadb.errors.InternalError: error returned from database: (code: 14) unable to open database file`. Store files alone pass (30 passed); `test_store_window.py` + `test_eval_runner.py` pass (44 passed); it is an ordering/state interaction, not store logic. With `ulimit -n 16384` the full suite is **514 passed**. Same 21 failures on parent `1eeb890`. Not fixed in this round (mixes themes); the README carries the qualification so no artifact claims an unqualified green.


## Maybe (2026-10-18) — recorded, deliberately unscheduled

**"Maybe" is ranked below *Someday*: the owner is not convinced he will ever pick this up.**
Written down only so a future session does not rediscover it from scratch. Do not plan around
this entry, do not let it compete with E2/E3, and do not open a ticket for it.

- source_plan: none (raised in conversation, 2026-10-18)
  summary: **Conversational JanBot** — let JanBot *discuss* rather than answer once: remember the previous turn ("and what about that incident?"), ask back before answering (the "one minute, or five minutes?" move), drill down on request, and eventually hold a position on the corpus' own attitudes. Owner's verdict: a different league, only after the first version of JanBot is finished.
  evidence: The current design is single-turn by construction and this is **not a missing flag** — `src/janbot/api/main.py:123` calls `program(question=request.question)` (one field, one LM call, no state), the service is stateless per instance by design (ADR-007: Cloud Run, scale-to-zero), and `src/janbot/api/contract.py:100` (`_enforce_citation_status_consistency`) requires an `answered` reply to carry at least one citation, so a clarifying question — which grounds in nothing — is *structurally* impossible today. AD-1 ("no other public interface without a superseding decision") makes any field added to `ChatRequest` a decision, not a commit. A grep of `spec-janbot/`, `backlog/`, ARCHITECTURE, README finds **zero** mentions of multi-turn / conversation history / follow-up: this is unexplored territory, not deferred scope, which is exactly why it belongs in "Maybe" and not in an epic. The real reason it is a different league: it does not merely change code, it **invalidates the measuring instrument** (a golden item is an `(question, expected answer, sources)` triple; a discussion needs trajectories) and changes the *kind of claim about Jan* the product makes — today he is **described**, a discussing JanBot would be **played**.
  evidence (what stays true regardless, so it need not be re-derived): a deterministic, model-free probe (`VectorStore.query(k=5)` over `public_profile_org/`) shows that **duration words do not route retrieval** — `"Tell me about yourself in one minute."` and `"...in five minutes."` return essentially the same set as the bare question (spec-first-pitch, personal-intro, foundational-books) — while **content keys do**: `"...the short version."` → `personal-intro` ×2, and `"Tell me about your career story."` → `departure-narrative`, `career-trajectory` ×2, `spec-first-philosophy`. Consequence for the "1 min / 5 min" idea: it is deliverable **entirely client-side** at widget time (the widget asks, then sends a *content key*, not a duration) with the `/chat` contract untouched — so it never needed the discussion capability at all. Two further findings worth keeping: (a) discussion would **not** require opinions — the corpus already carries stances (`attitudes`/personal-intro, `spec-first-philosophy`, `departure-narrative`, `foundational-books`), so a grounded discussion answers with a **cited position**, and the existing per-turn citation requirement (`UncitedAnswer` → decline) is a structural defence rather than an obstacle; and (b) the ADR-009 over-claiming gap is **multiplicative** under multi-turn (accumulating context + a recruiter steering turn by turn), which the already-adopted deterministic output-level guard (option (c), reads the *answer*) covers better than a question-side control would.
  evidence (cheapest instrument, if this is ever picked up): a "dovetail set" — 5–8 two-turn scenarios whose second turn is genuinely ambiguous alone (`"and what about that incident?"`, `"tell me more about it"`) — scored as `retrieval_accuracy` **on turn 2**. Deterministic, no judge, no model call, no cost. It makes "discussion" measurable before it is built.
  **Conditional trigger on ADR-009, control 4 (only if this entry is ever picked up):** the control reads "maximum *question* length"; the acceptance test is "a question over the cap is rejected (4xx) and never reaches retrieval". The moment a `history` field enters `ChatRequest` — the cheapest way to keep the server stateless, since history travels in the request rather than a Firestore session — that AC stops covering the surface: an unbounded history is a prompt-size and cost vector spread across many turns, not one oversized question. Control 4 would then have to bound the **total payload**, and `ChatRequest.question` currently carries no `max_length` at all (`src/janbot/api/contract.py:39`), so even the single-question cap is still to be built in E2. **This is not a defect today** (no `history` field exists, so the AC matches the shipped shape); it is a note about when its wording expires.
  status: **maybe** — unowned, unscheduled, no blocker, not planned. Revisit only if the owner ever says so, and then as a fresh decision (spec + ADR), not as a task pulled off a list.
