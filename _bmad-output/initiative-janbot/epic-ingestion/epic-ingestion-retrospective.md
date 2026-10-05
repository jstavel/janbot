---
epic: epic-ingestion
date: 2026-10-05
verdict: accepted-with-open-items
criteria: declared
headless: false
---

# Retrospective — epic-ingestion (Org-mode ingestion & fail-closed scope)

## Epic summary

- **Epic:** `epic-ingestion` — "Org-mode ingestion & fail-closed scope" (`covers: CAP-4, CAP-5`), Milestone 1.
- **Tickets (build order):** `2.1` Config contract & corpus-root hardening — **done**; `2.2` Tracer bullet — **done**; `2.3` Full org subtree chunker — **done**; `2.4` Fail-closed scope filter — **done**; `2.5` Idempotent index rebuild + store hardening — **done**; `2.6` Refactor sweep — **done**; `2.7` End-to-end ingestion suite — **done**. `pending_tickets`: none; none left at `built`.
- **Criteria:** declared — `epic-ingestion.md` Done when (4 checks).

### Diff ranges (per plan baseline)

| Ticket | Range | Commits |
| --- | --- | --- |
| 2.1 | `085f5b32..2d1aa2d` | 1 |
| 2.2 | `2d1aa2d..2f4bc21` | 1 |
| 2.3 | `2f4bc21..3eec6ca` | 1 |
| 2.4 | `3eec6ca..422e55b` | 1 |
| 2.5 | `422e55b..3ca7ea8` | 1 |
| 2.6 | `3ca7ea8..138cb4a` | 1 |
| 2.7 | `138cb4a..0577151` | 1 |

### Evidence inventory

- Present: epic file; initiative Requirements; all seven plans (with Review Triage Logs, Implementation Notes, Verification); full commit/file-churn evidence (`git_evidence.py`); architecture spine and spec.
- **Narrowing:** the epic-level review diff (`085f5b32..HEAD`, src/ + tests/) excludes planning docs and `uv.lock`. `bmad-review` was not invoked as a separate run; the adversarial, edge-case, and verification-gap lenses ran inline and are recorded as such. Session logs are absent (process analysis rests on the plans).
- **External:** the real corpus lives outside the repo (`~/org/h1_horizon/public_profile_org/`, symlinked); tests use hermetic fixtures, so no test indexes real data.

## Findings

Each carries a source; dispositions: fix now (→ action item) / defer / accept-as-is. Lens findings are reports; the high-impact ones were probed by the lens, and the behavior check and per-story reviews corroborate the seams.

### Cross-story seams (adversarial lens)

- **The store has one global collection with no scope ownership.** `src/janbot/store/chroma.py:39,112-118` uses a fixed collection `janbot` and `query()` returns global top-k with no `where` filter; metadata carries only `source_path`/`breadcrumb` (`chroma.py:63-66`). The ingest reconcile deliberately preserves other corpora's chunks (`ingest/__init__.py`), yet `epic-rag-chat` must guarantee "no answer from outside `public_profile_org/`" — impossible with the current store. Contradicts `ARCHITECTURE.md` ("Collection per domain scope"). **Disposition: fix now (remediation) — epic-rag-chat.**
- **`source_path` is an absolute host path.** `src/janbot/ingest/org.py:97` + `chroma.py:80` store and return absolute paths; `epic-rag-chat`'s `Citation` would leak the server layout and the owner's `$HOME`. **Disposition: fix now (remediation) — epic-rag-chat (relativize/rewrite citations).**
- **Chunk ids embed a document-order ordinal** (`org.py:108`), so inserting a heading shifts every later id → the whole tail is re-embedded and delete/re-added; combined with the path-keyed reconcile (`ingest/__init__.py:52-57`), "which corpus owns a chunk" is a filesystem-path coincidence, not stored scope. **Disposition: fix now (remediation) — stabilize ids (source+breadcrumb hash) and store scope/reconcile by a scope key.**
- **`--index` is not resolved like config.** `src/janbot/ingest/__main__.py:28` forwards the raw `--index`; config resolves against `PROJECT_ROOT` (`config.py:70-75`), so a relative `--index` is CWD-relative and an empty `--index ""` writes into the CWD. **Disposition: fix now (remediation) — resolve/normalize CLI paths via config.**
- **`PROJECT_ROOT = parents[2]` only holds for a source checkout** (`config.py:49`); a wheel install anchors defaults under `site-packages`. Already noted as overridable. **Disposition: defer — document `JANBOT_PROJECT_ROOT` for deployment.**
- **No embedder/model identity is persisted.** The injectable seam lets the embedder change while the collection name/path stay fixed; only vector **dimension** is checked (by Chroma) — a same-dimension model/`hnsw:space` swap silently skews ranking (`chroma.py:59-66`). **Disposition: fix now (remediation) — persist embedder id + validate on open.**

### Robustness / correctness (edge-case lens)

- **An unreadable directory silently drops its files, then the reconcile deletes their chunks.** `rglob` returns nothing for a `chmod 000` subdir and `index_corpus` treats those chunks as stale (`ingest/__init__.py:52-57`) → silent data loss. An unreadable **file** instead raises and aborts the whole run (`org.py:98`). **Disposition: fix now (remediation) — refuse on an unreadable root/dir (never delete); make an unreadable file non-fatal.**
- **File-level `#+TITLE` and all prose before the first heading are never indexed** (`org.py:95-114` only chunks subtree nodes). **Disposition: fix now (remediation) — index a file-level title/preamble chunk.**
- **Whitespace-only heading yields an empty breadcrumb and a dangling `::` id** (`org.py:42-44,104-112`). **Disposition: defer (low) — normalize.**
- **Recursion depth:** `_subtree_text`/`_iter_subtree_nodes` recurse per level; a ~2000-level file raises `RecursionError`. **Disposition: defer (low) — iterative traversal or depth cap.**
- **A real file plus a symlink to it inside the root is indexed twice** (`scope.py:68`, no dedup by resolved identity). **Disposition: defer (low).**
- **Large corpora:** whole-collection `ids()`/`sources()` load every record into memory and ship the full stale list each run (`chroma.py:93-103`). **Disposition: defer — covered by the id/scope remediation and a later scaling pass.**

### Verification strength (verification-gap lens, mutation-probed)

- **Done-when 4's "corrupt" clause is unverified.** Idempotency tests assert only `ids()` equality; mutating `documents = chunk.text + "__CORRUPT__"` still passes all 59 tests, so content/embedding stability is undecided. **Disposition: fix now (remediation, tests).**
- **Done-when 2 is stub-only.** No test exercises `default_embedder`/`DefaultEmbeddingFunction` or `python -m janbot.ingest`; replacing `default_embedder` with `raise` still passes. **Disposition: fix now (remediation, tests) — exercise the CLI/default-embedder wiring without downloading.**
- **Done-when 3's refusal is only jointly verified.** `iter_org_files` and `index_corpus` both filter, so removing either alone passes; no test hands an out-of-scope path to `index_corpus`. **Disposition: fix now (remediation, tests).**
- **"changes no retrieval result" is narrowed** to an id-set diff plus one post-hoc query, not a ranked-result comparison (`test_ingestion_e2e.py:70-92`). **Disposition: fix now (remediation, tests).**
- **Breadcrumb for normalized headings is unpinned** (`#+TITLE`, TODO keywords, priorities dropped; `test_org_chunker.py` never asserts the empty-heading breadcrumb). **Disposition: defer — pin once the chunker contract for these is decided.**
- **Symlink-by-location is an accepted deviation.** `test_scope.py` asserts a symlinked public file (target outside) **is** indexed — the deliberate 2.4 policy (location governs). The literal wording "a path outside the public folder is refused" reads contradictorily. **Disposition: accept as-is (recorded decision); reconcile the epic/spec wording.**

## Behavior verification

Exercised end to end (not tests alone): a fresh corpus indexed with the stub embedder → 2 chunks; `query("Bg")` returned the chunk with its child text and source path; re-running produced the same chunk count and id set (idempotent). The **real** embedding model and the `python -m janbot.ingest` CLI were **not** executed (would download the ONNX model; the default corpus path does not exist in the repo) — recorded as the Done-when-2 evidence gap.

## Previous-retro follow-through

Previous retrospective: `epic-foundation/epic-foundation-retrospective.md` (verdict accepted-with-open-items, 11 action items).

| Item | Landed? | Evidence |
| --- | --- | --- |
| #1 corpus-root ownership decision | **Yes** | `epic-ingestion.md` decisions + 2.4 (`scope.py`) |
| #2 config production route/temperature/top-k | **No** | deferred to epic-rag-chat; not in config |
| #3 anchor corpus/index paths | **Yes** | `config.py` resolves to absolute; 2.1 tests |
| #4 declare embedding dependency | **Partial** | chose Chroma's built-in default (no sentence-transformers) — recorded decision |
| #5 harden `load_config` | **Yes** | 2.1 (blank/whitespace, mode normalize, snapshot) |
| #6 test hardening (literal contract, imports, subpackages) | **Yes** | 2.1 + 2.6 |
| #7 pin build backend | **Yes** | `pyproject.toml` `hatchling==1.32.4` |
| #8 CI hardening | **Yes** | `.github/workflows/ci.yml` |
| #9 fix ADR links | **Yes** | `ARCHITECTURE.md` |
| #10 push + observe CI | **Yes** | run `37313057726` green |
| #11 Done-when wording / console script | **Yes** (wording) | `epic-foundation.md` updated; console script still open |

## Action items (proposed; the human decides what to execute)

**For `epic-rag-chat` (remediation):**
1. Give the store scope ownership — stored scope/public flag + a `query` filter (or collection-per-scope) — so retrieval never answers from outside the public folder. (Also realizes "collection per domain scope".)
2. Relativize/rewrite citation `source_path` so responses do not leak absolute server paths/`$HOME`.
3. Stabilize chunk ids (source+breadcrumb hash) and store a scope key for reconcile, ending ordinal churn and path-coincidence ownership.

**Follow-up hardening (this epic's domain):**
4. Fail closed on an unreadable corpus root/dir (never delete its chunks); make an unreadable `.org` file non-fatal.
5. Index the file-level `#+TITLE`/preamble as a chunk.
6. Persist embedder identity + validate vector dimension/space on open.
7. Resolve `--index` (and reject empty) consistently with config; update the README so the default corpus path is not presented as runnable without `JANBOT_CORPUS_PATH`.

**Tests (Done-when evidence):**
8. Assert stored document/content stability across runs (not just ids).
9. Exercise the CLI entry point and `default_embedder` wiring without a model download.
10. Test `index_corpus` refusal with an out-of-scope path directly; compare ranked retrieval before/after a private file.

**Low / defer:** whitespace-heading normalization; recursion depth guard; symlink duplicate dedup; large-corpus scaling; packaged-install `JANBOT_PROJECT_ROOT` documentation; reconcile the epic/spec wording for symlink-by-location.

**Process lessons:** per-story reviews validate stories in isolation and missed exactly the cross-story seams (multi-corpus scope, citation path leak, id churn) and the Done-when *evidence strength* — add an explicit "prove each Done-when with a test that would fail if it regressed" step at epic close. Mutation testing by the verification lens proved high-value for the closing suite; keep it. Record accepted deviations (symlink-by-location) so later retros stop re-flagging.

## Acceptance verdict

**accepted-with-open-items** — criteria `declared`.

- Done-when 1–4 are met by the delivered mechanism: subtree chunks with breadcrumbs/properties/tags/child content; a populated, queryable ChromaDB index; outside paths refused and idempotent re-runs (behavior check + 59 tests). All seven tickets are finished.
- Open items are named and tracked (above); the most consequential are **for the next epic** (store scope ownership, citation paths, id stability) plus Done-when **evidence-strength** gaps (Done-when 2 stub-only) and robustness (unreadable dir → silent chunk deletion). None leaves a ticket unfinished.
- Strict reading: Done-when 2's real-embedding/CLI path undemonstrated means it is met only against the injected stub — a human may treat this as accepted-with-open-items (as recorded) or, if real-model evidence is required, **rejected** until item 9 runs.

## Open questions

- Store model: scope metadata + `where` filter on one collection, or collection-per-scope? (drives item 1)
- Should `#+TITLE`/preamble be a chunk on its own, or prepended to each top-level chunk? (drives item 5)
- Is symlink-by-location the permanent policy, and should the spec's "outside the public folder is refused" wording be reconciled to it? (drives the wording item)
