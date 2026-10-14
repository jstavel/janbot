---
title: 'Serve ↔ ingest corpus-root alignment'
type: 'chore'
ticket: ''
created: '2026-10-13'
status: 'built'
baseline_revision: '32bd3fa048c97590d40baaa8deea111a7d22eae5'
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

**Problem:** ingestion writes through an **unscoped** store (`src/janbot/ingest/__init__.py:49`), so the index carries no record of which corpus root built it, while serving scopes to whatever `JANBOT_CORPUS_PATH` the process got (`src/janbot/api/main.py:60-62`) and rewrites citations relative to that root. A serve root that differs from the ingest root is therefore undetected: a **broader** serve root silently changes the citation form (`public_profile_org/profile.org` instead of `profile.org`) and can expose content from outside the intended public folder; a **narrower** one silently 503s every request. No story owned the ingest↔serve alignment. Recorded in the epic-rag-chat retrospective (open question).

**Approach:** decide how the two roots are held consistent (options below), then implement the chosen guard/documentation.

## Boundaries & Constraints

**Always:**
- Whatever is chosen, the two roots are either provably consistent or the mismatch is surfaced (fail-fast or documented), never silent.
- No change to retrieval ranking, the `/chat` contract, or the model-mode behaviour.
- Preserve the 3.1–3.8 pins and the retro hardening (1–4).

**Never:**
- No change to the ingestion *scope policy* (what is indexed is untouched); at most, record provenance.
- No new route or contract field.

Decision (2026-10-13): option A — `create_app` performs a **startup cross-check**: it fails fast (`ValueError`) if any indexed `source_path` lies outside `config.corpus_path`, so an index built from a different (narrower or foreign) root is surfaced instead of silently shifting the citation form or 503-ing everything.

</frozen-after-approval>

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (146 baseline + new startup-check rows)

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-13: `src/janbot/store/chroma.py` — added `VectorStore.out_of_scope_sources()` (empty when unscoped). `src/janbot/api/main.py` — `create_app` fails fast when it returns non-empty; docstring `Raises` updated; error message reworded. `tests/test_chat.py` adds a startup-failure row (out-of-scope chunk in the index). README documents the check.
- Mutation-verified: removing the startup check fails the new row. `uv run pytest -q` → 147 passed.
- Residual recorded in `deferred-work.md`: a serve root *broader* than the ingest root stays undetected (option A's scope; needs persisted provenance).

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-13 — quick lens

- **Verdict counts: 0 high / 0 medium / 5 low / 0 false / 0 maybe-false.** Two patches, two accepted (documented), one recorded as a residual.
- **Broader serve root stays silent** — **verdict: low**. Real but harmless (the index holds only the public corpus, so no out-of-corpus content is retrievable; only the label form shifts). **route: patch** — narrowed the wording; residual recorded in `deferred-work.md`.
- **Guard rejects a shared multi-corpus index** — **verdict: low**. JanBot serves one corpus (`public_profile_org` is "the ONLY indexed corpus"); the guard makes a misconfigured serve index explicit. Ingestion's shared-index capability is unaffected (its tests pass). **route: accept as-is**.
- **`create_app` `Raises` docstring not updated** — **verdict: low**. **route: patch** — updated.
- **README "every indexed chunk" overclaims** (a sourceless chunk is dropped from `sources()`) — **verdict: low**. **route: patch** — reworded to "every indexed chunk which records a source".
- **Guard runs only at startup** — **verdict: low**. Inherent to the chosen "startup cross-check" scope. **route: accept as-is**.

