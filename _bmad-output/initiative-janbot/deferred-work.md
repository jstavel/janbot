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
