---
epic: epic-rag-chat
date: 2026-10-13
verdict: accepted-with-open-items
criteria: declared
headless: false
---

# Retrospective — epic-rag-chat (DSPy answer + citation pipeline via /chat)

## Epic summary

- **Epic:** `epic-rag-chat` — covers CAP-1, CAP-2, CAP-3, CAP-6. Nine tickets, all **done** (8 stories; no `pending_tickets`, none left at `built`).
- **Epic Done when** (declared in `epic-rag-chat.md`): 1) grounded answer to a real recruiter question; 2) every response cited, uncited rejected; 3) Pydantic-validated contract + malformed → standard envelope; 4) identical output at the locked snapshot, mode switch config-only; 5) no answer from outside `public_profile_org/`.
- **Ranges (baseline → next baseline; last → HEAD), per plan:**
  - 3.1 `731036f..616ac11` · 3.2 `616ac11..e3a9a54` · 3.3 `e3a9a54..d75ba3c9` · 3.4 `d75ba3c9..4110fa17` · 3.5 `4110fa17..3d64f580` · 3.6 `3d64f580..a4b4e312` · 3.7 `a4b4e312..a3d6b8e9` · 3.8 `a3d6b8e9..43fe42d` (last, inferred).
- **Evidence inventory:** epic file, initiative Requirements, all 8 plan files (Triage Logs, Implementation Notes, Verification) — present. `git_evidence.py` per range — present. **Session logs — absent** (no conversation records in-tree): process-lesson analysis is narrowed to what the plans/commits record. **Consolidated diff:** `/tmp/opencode/epic-rag-chat.diff` (3859 lines, `731036f..43fe42d`).
- **Note:** PRs #1–#5 merged with merge commits; PRs #6–#8 squash-merged (one commit each, at the user's request).

## Findings

### Aggregate views

- **Architecture delta — core imports the port package.** `src/janbot/pipeline/chat.py:33` does `from janbot.api.contract import ChatResponse, Citation`; architecture casts `api/` as the driving-adapter/port and `pipeline/` as core (`architecture-janbot.md:23-27`). The contract is shared, so this may be intended, but it is a new core→api edge. No import cycle exists: `store/chroma.py` re-implements containment rather than importing `ingest.scope` (`store/chroma.py:46-48`; `ingest/__init__.py:9`). *(checked, one observation.)*
- **Duplication map:**
  - Containment solved twice — `store/chroma.py:43` `_within_scope` vs `ingest/scope.py:34` `within`+`located_path:23`; rationale is only the circular import (`store/chroma.py:46-48`).
  - `StubLMFactory` defined twice with different shapes — `tests/test_chat.py:35` (DummyLM) vs `tests/test_llm.py:20`.
  - Identical "Import order matters" comment duplicated — `api/main.py:16-19` vs `pipeline/chat.py:18-21`.
  - `api_key` fail-fast duplicated — boot gate `api/main.py:64-71` and adapter guard `llm/__init__.py:71-76`.
  - Test constants re-declared — `tests/test_chat.py:27-29` vs `tests/test_llm.py:15-17`; `Embedder` alias re-declared in three test files instead of the conftest fixture (`tests/test_chat.py:25`, `tests/test_store_scope.py:17`); chunk stand-ins re-defined despite the `ChunkLike` protocol (`store/chroma.py:25`).
- **God-class / size growth — none.** Touched source files: `store/chroma.py` 208, `config.py` 166, `pipeline/chat.py` 138, `api/main.py` 98, `llm/__init__.py` 80, `api/contract.py` 50 lines. Largest grew +58 (`store/chroma.py`, 3.6). No god-class. *(checked, clean.)*
- **Pattern divergence:** containment enforced in `store/` (CAP-1 authorizes pipeline+store, `architecture-janbot.md:150`) though CAP-4 maps scope to `ingest/` (`:153`); private `_within_scope(Path)` vs public `within(root, path)`; the route's untyped `except ValueError` maps *any* future `ValueError` to 500 by class position (`api/main.py:90-93`).
- **Spec-to-implementation reconciliation:**
  - **DW1** — stub-only in the automated suite (`DummyLM`, `tests/test_chat.py:17,50-53`); the only live proof is the entry-2 HITL run, which the epic notes as its sole in-epic live evidence (`epic-rag-chat.md:54`). *not checked in the suite; HITL only.*
  - **DW2** — checked (derived-from pin `tests/test_chat.py:319-359`; uncited/unknown → 500 `:383-425`).
  - **DW3** — checked (schema + 422 envelope `tests/test_contract.py`, `tests/test_chat.py:147-156`).
  - **DW4** — checked but stub-only (`tests/test_chat.py:188-274`); real reproducibility open (`deferred-work.md`, keyed double-run carry).
  - **DW5** — checked (store scope `store/chroma.py:163-208`; `tests/test_store_scope.py`, `tests/test_scope.py:155-237`, port rows `tests/test_chat.py:428-477`).
  - **Superseded pins (recorded, not defects):** 3.2 zero-chunk 500 → 3.3 503; 3.3 sourceless 500 → 3.6 503.
  - **Boundary exceeded:** `public_profile_org/ai-fast-failback.org` was edited in-place (SYNOPSIS wording) inside the 3.6 squash commit `457bc70` — outside the epic Boundary (`api/`, `pipeline/`, `llm/`) and its named carries (`store/`+tests). README states the corpus is "updated only by re-extraction, never edited in place".
  - **Boundary narrowed (intended):** chunk-id stability deferred to its own ticket (`ingest/org.py` out of boundary; `deferred-work.md`).

### Cross-ticket lenses (adversarial / edge-case / verification-gap)

Run inline over `/tmp/opencode/epic-rag-chat.diff` (three lenses; `bmad-review` not invoked as a separate skill — recorded narrowing).

- **Two fail-closed guards disagree on a relative `source_path`; the store's verdict is CWD-dependent.** `store/chroma.py:57` normalizes with `Path(os.path.abspath(...))` (CWD-relative), while `pipeline/chat.py:69` uses `Path(source_path).relative_to(resolved_root)` with no absolutization. A chunk upserted with a relative `source_path` can pass the store guard (content enters the prompt) yet fail the rewriter → 500, whose detail falsely says the source "lies outside the corpus root". Contradicts the documented CWD-independence (`config.py:23-25`). Reachable only via non-ingest writers (the store accepts arbitrary metadata; tests' `ForeignChunk`/`SourcelessChunk` establish that threat model).
- **Serve-time corpus root is never cross-checked against the index's ingest provenance.** Ingestion writes through an *unscoped* store (`ingest/__init__.py`), serving scopes to `JANBOT_CORPUS_PATH` (`api/main.py:61`). A broader serve root silently changes the citation form (`public_profile_org/profile.org` instead of `profile.org`, README `:87`); a narrower one 503s everything. No story owned ingest↔serve alignment.
- **Non-`ValueError` pipeline exceptions escape the `{detail}` envelope.** `dspy.utils.exceptions.AdapterParseError` MRO is `DSPyError → Exception` (verified: **not** a `ValueError`) and can occur on a real-model parse failure — the route maps only `EmptyRetrieval`→503 and `ValueError`→500 (`api/main.py:90-93`), so it surfaces as a plain-text 500 with no `{detail}`, violating DW3 exactly in the mode the suite never runs.
- **Citation order is LM-claim order.** `pipeline/chat.py:137` builds citations via `dict.fromkeys(normalized)` (model claim order). Two runs with identical answer text but permuted claims produce different JSON — a nondeterminism channel the DW4 stub tests cannot see. Emitting in retrieval-`sources` order would be deterministic given retrieval.
- **`JANBOT_TEMPERATURE` accepts `nan`/`inf`.** Float-only parse (`config.py:115-124`; verified `nan` accepted) flows into LM kwargs in both modes (`llm/__init__.py:63-66`), silently voiding the eval determinism pin — the exact failure 3.5 exists to prevent — and can only fail at request time, outside the envelope mapping.
- **Client `question` echoed verbatim into `{detail}`.** `pipeline/chat.py:105,111,124,132` interpolate `{question!r}` into the detail (`api/main.py:91,93`). Story 3.4's review patched LM-claim echoes for this reason; the equally client-controlled question was left in.
- **Contract permits vacuous outputs.** `ChatResponse.answer` has no constraint and `Citation.source` no `min_length` (`contract.py:38,46`); an empty `answer` with one citation returns 200, and a chunk whose `source_path` equals the corpus root rewrites to `.` (`chat.py:69`).
- **`_within_scope` is not an exact mirror of `within`.** `store/chroma.py:46-47` claims it mirrors `ingest.scope.within`, but lacks the final `abspath(path)==abspath(root)` equality clause (`ingest/scope.py:51`); latent (production stores resolved paths).
- **3.4's rewriter guard has zero test coverage after 3.6.** `UnattributableContext`/`corpus_relative` appear in no test file; 3.6 repointed the out-of-root port row to the store-boundary 503 (`tests/test_chat.py:428-447`) and 3.3's sourceless row to 503 (`:298-316`), leaving both branches of the "second guard" untested. A regression in the rewriter or a wrong rewriter root (`api/main.py:75`) passes the whole suite.
- **The 3.6 store scope is never exercised with a real (non-stub) embedder, and its manual check has no completion record.** Every scope/port test injects the stub embedder (`tests/test_store_scope.py:6`); the shipped scoped over-fetch (`store/chroma.py:174-186`) against a real Chroma HNSW collection has never run.
- **The seed pin is asserted only against captured kwargs**, and `seed` is not a named `dspy.LM` parameter (it rides `**kwargs` to litellm) — whether it reaches the provider is unverified in-repo; the keyed double-run was never run (`deferred-work.md`).
- **Production routing path unproven against the real provider.** The routing test exercises both routes over HTTP but with `DummyLM` (`tests/test_chat.py:188-226`); the only live production run (3.2 HITL) predates the rewriter, seed, and store scope.
- **DW1's live evidence validates superseded code.** The 3.2 HITL run (raw absolute `source_path` echoes) and the 3.4 real check predate 3.5/3.6; no live run of the final assembled pipeline exists in the record.

## Behavior verification

Exercised the built service directly (`JANBOT_MODEL_MODE=eval uv run uvicorn janbot.api.main:app`, port 8077):
- `GET /health` → `200 {"status":"ok"}`.
- `POST /chat {"question":"   "}` → `422 {"detail":[...]}` — the standard envelope holds.
- `POST /chat {"question":"hello"}` → `500 {"detail":"the model claimed no sources for question 'hello'; refusing to return an unattributable answer"}` — a **live real-model call** (ambient key) against the repo `chroma_db` that retrieved context but returned no citations, and the fail-closed guard correctly rejected it. No grounded, cited recruiter answer was demonstrated (the question was not a real recruiter question; DW1's live proof remains the HITL gap).
- **Not exercised:** the real embedder (`default_embedder` downloads ONNX) and a grounded cited answer end to end; recorded as a gap. Verified supporting claims live: `AdapterParseError.__mro__` is not `ValueError`; `load_config({"JANBOT_TEMPERATURE":"nan"})` yields `nan`.

## Previous-retro follow-through

Previous epic: `epic-ingestion` — `epic-ingestion-retrospective.md` (verdict accepted-with-open-items). Its Action items and whether they landed in `epic-rag-chat`:

- **#1 Store scope ownership** → **landed** — `store/chroma.py:163-208` + `api/main.py:59-62` (story 3.6).
- **#2 Relativize citation `source_path`** → **landed** — `pipeline/chat.py:58-75,114` (story 3.4).
- **#3 Stabilize chunk ids + scope key** → **not landed** — deliberately deferred to its own ticket (`deferred-work.md`, "Sweep decisions 2026-10-13").
- **#4 unreadable root/dir fail-closed; #5 `#+TITLE`/preamble chunk; #6 persist embedder identity; #7 resolve `--index`; #8 content-stability test** → **no evidence found in this epic's ranges** (these were epic-ingestion-domain; whether they landed before that epic closed is outside this epic's evidence and not checked here).
- **#10 `index_corpus` refusal + ranked retrieval test** → **landed** — `tests/test_scope.py:155-237` (story 3.7, mutation-verified).
- **Process lesson "prove each Done-when with a test that would fail if it regressed"** → **partially adopted** — 3.7's tests are mutation-verified; the seed (3.5) and rewriter (3.4) guards still lack such a test.

## Action items (proposed; the human decides what to execute)

**Fix now (remediation — propose as stories/bugs for the dev loop):**
1. **Envelope robustness** — map non-`ValueError` pipeline/dspy errors (e.g. `AdapterParseError`) into the `{detail}` envelope so DW3 holds in real-model mode. *(owner: next hardening)*
2. **Citation ordering** — emit citations in retrieval-`sources` order, not LM-claim order, to close the DW4 nondeterminism channel. *(owner: next hardening)*
3. **Rewriter coverage + guard alignment** — add tests that fail if `corpus_relative` accepts an out-of-root path or is built from the wrong root; align the rewriter to absolutize `source_path` like the store does (or reject non-absolute at the store). *(owner: next hardening)*
4. **`JANBOT_TEMPERATURE` validation** — reject non-finite values at config load. *(owner: next hardening)*
5. **Serve↔ingest root alignment** — either cross-check the serve scope against index provenance or document the operational contract; pins the citation form. *(owner: config/ops)*
6. **In-place corpus edit** — `public_profile_org/ai-fast-failback.org` was edited in the 3.6 commit; restore via re-extraction or record an accepted deviation. *(owner: human)*

**Process lessons:**
7. Per-story reviews validate stories in isolation and again missed cross-story seams (ingest↔serve root, rewriter/store guard divergence, envelope coverage across the real-model path). Add an epic-close cross-ticket lens pass (as done here) as a standing gate.
8. `git add -A` swept an unrelated corpus edit into the 3.6 PR — stage only intended files per story.
9. Done-when evidence strength: the epic's own DW1/DW4 live proof is still HITL/keyed — `epic-verification` (CAP-7) is where the real end-to-end evidence must land; do not close the initiative without it.

**Defer (tracked):** chunk-id stability; scoped-query over-fetch optimization (`deferred-work.md`); seed-reaches-provider verification; vacuous-output constraints (`answer` empty, `source` `.`).

## Acceptance verdict

**accepted-with-open-items** — criteria `declared`.

- All nine tickets of `epic-rag-chat` are finished; `pending_tickets` is empty, so the verdict is not forced to *rejected*.
- DW2, DW3, DW5 are demonstrably met by tests; DW1 and DW4 are met against stubs/HITL as the epic scoped them (`epic-rag-chat.md:54` places the closing end-to-end suite in `epic-verification`).
- Named findings remain deferred/tracked (action items above) — chiefly the envelope gap on the real-model path, citation-order nondeterminism, and the untested rewriter guard. None leaves a ticket unfinished.
- Strict reading: DW1's "real recruiter question" and DW4's provider reproducibility are not demonstrated on the final shipped pipeline; a human may treat the epic as **rejected** until `epic-verification` supplies that evidence. No human decision overrides the machine verdict in this run.

## Open questions

- Should the serve scope be validated against the index's ingest provenance, or is "correct `JANBOT_CORPUS_PATH` at boot" an accepted operational contract?
- Reconcile the architecture note "Collection per domain scope" (superseded inline in `ARCHITECTURE.md:83`) — keep the single scoped collection, or revisit collection-per-scope?
- Are the vacuous-output cases (empty `answer`; `source="."`) in scope for the contract, or intentionally unconstrained?
