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

- source_plan: none
  summary: Reject non-finite `JANBOT_TEMPERATURE` (nan/inf) at config load.
  evidence: `src/janbot/config.py:115-124` parses float only; `load_config({'JANBOT_TEMPERATURE':'nan'})` yields `nan` (verified), silently voiding the 3.5 eval determinism pin. Recorded in the epic-rag-chat retrospective. Split out of the fix-now set.

- source_plan: none
  summary: Serve↔ingest corpus-root alignment — cross-check the serve scope against index provenance, or document the operational contract.
  evidence: Ingestion writes through an unscoped store (`ingest/__init__.py`) while serving scopes to `JANBOT_CORPUS_PATH` (`api/main.py:61`); a mismatched root silently changes the citation form or 503s everything. Recorded in the epic-rag-chat retrospective (open question). Split out; design decision.

- source_plan: none
  summary: `public_profile_org/ai-fast-failback.org` was edited in-place inside the 3.6 PR — **resolved: reverted** (the original "working groups formed" is correct), 2026-10-13.
  evidence: Commit `457bc70` (story 3.6) changed the SYNOPSIS line; the wrong edit has been reverted, so the corpus again matches its pre-3.6 state.

- source_plan: `_bmad-output/initiative-janbot/plan-serve-ingest-root-alignment.md`
  summary: The startup cross-check does not catch a serve corpus root *broader* than the ingest root (all indexed chunks stay in scope; only the citation label shifts).
  evidence: `out_of_scope_sources()` flags only stored chunks outside `config.corpus_path`; the index records no ingest-root provenance. Covering that direction needs persisted provenance (option C, edits `ingest/`). Low harm: the index holds only the public corpus, so no out-of-corpus content can be retrieved; only the label form changes.

## Reverted edits (2026-10-13)

- `public_profile_org/ai-fast-failback.org` — the in-place SYNOPSIS change that rode into the 3.6 commit `457bc70` ("working group formed") was **reverted**: the original "working groups formed" is correct (initiative-wide, not from the one idea). The corpus again matches its pre-3.6 state. Source: `epic-rag-chat/epic-rag-chat-retrospective.md` action item 6.
