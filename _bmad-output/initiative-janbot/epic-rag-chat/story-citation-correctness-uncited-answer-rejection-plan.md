---
title: 'Citation correctness & uncited-answer rejection'
type: 'feature'
ticket: 4
created: '2026-10-12'
status: 'done'
baseline_revision: 'd75ba3c9fd44e11ad329edb96e00b07fd2a70419'
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

**Problem:** `/chat` citations are not proven derived-from: they name every retrieved chunk's source regardless of what the answer actually used, an LM answer with no grounding cannot be distinguished from a cited one, and `Citation.source` echoes the store's absolute `source_path` — leaking the server layout and the owner's `$HOME` (epic-ingestion retrospective carry, pinned in `deferred-work.md`).

**Approach:** The DSPy program claims its own sources: the answer generation names the context chunks it derived from (by source label), the program validates every claim against the retrieved chunks' `source_path` metadata, emits citations only from that metadata — rewritten to corpus-relative form so no absolute path can leave the port — and rejects an answer whose citations are empty or unverifiable rather than returning it (CAP-2; epic Done-when 2).

## Boundaries & Constraints

**Always:**
- Citation values in responses are emitted from chunk `source_path` metadata only. LM-claimed source strings are matched against the metadata-backed set and never passed through verbatim into a response.
- The derived-from match set is exactly the retrieved chunks' rewritten sources. A source that was indexed but not retrieved can never be cited.
- Fail-closed: an answer whose citations are empty, or unverifiable against the retrieved set, is rejected with the standard error envelope — never returned. (Decision 2026-10-12: an LM claim naming a source outside the retrieved set counts as unverifiable — reject, do not drop.)
- Citation form (decision 2026-10-12): `source` values are corpus-root-relative — the path relative to the configured corpus root (e.g. `profile.org`), never absolute.
- Context is composed as per-chunk blocks labeled with the rewritten source, so the model echoes exact source labels and never sees an absolute filesystem path.
- Rewriting happens at the citation boundary in `pipeline/` only; the store keeps absolute `source_path` values (no re-ingestion, no metadata rewrite).
- Preserve story 3.2/3.3 pins: `janbot.store` before `dspy` import order, whitespace-key boot gate, module-level `app = create_app()`, `GET /health`, strip-and-reject `question`, `citations` ≥ 1 at the schema, and the 422/503/500 `{detail}` envelope shapes.

**Never:**
- No changes to `store/`, `ingest/`, or `llm/` internals; chunk-id stability stays entry 8's review item.
- No new contract fields; the `{answer, citations[]}` shape is unchanged; no `min_length` on `answer` (story 3.3 ownership).
- No new route-level exception mapping beyond the existing kinds: the rejection rides the existing `ValueError` → 500 mapping.
- No DSPy compilation or prompt optimization (Milestone 2).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| HAPPY | valid question, indexed corpus, LM cites retrieved labels | 200 `ChatResponse`; citations in corpus-relative form, each from a retrieved chunk | No error |
| ERROR | LM claims no citations | answer rejected, never returned | 500, `{"detail": ...}` naming the uncited refusal |
| ERROR | LM names a source not among the retrieved chunks | answer rejected, never returned (fail-closed) | 500, `{"detail": ...}` naming the unverifiable claim |
| ERROR | chunk `source_path` outside the corpus root | fail-closed rewrite refusal | 500, `{"detail": ...}` (existing integrity kind) |
| EDGE | multiple retrieved chunks share one source | deduped citations, one entry per distinct source | No error |

</frozen-after-approval>

## Code Map

- `src/janbot/pipeline/chat.py` — enforcement point. `GroundedAnswer` (:36-41) gains a `citations` output field; `forward` (:53-74) composes labeled context (:71), validates LM claims between :72 and :74, raises a new `UncitedAnswer(ValueError)` for empty/unverifiable claims, reuses `UnattributableContext` for out-of-root sources; citation construction :66-69 moves to post-validation; docstring :8-9 ("later stories (3.4)") updated. Add a module-level `corpus_relative(root)` helper returning the rewrite callable.
- `src/janbot/api/main.py` — :71 builds `ChatProgram(store, top_k=...)`; pass the rewriter built from `config.corpus_path` (resolved absolute by `_resolve_path`, `config.py:81-86`). No other change — the 500 mapping at :87-88 already catches the new kind.
- `src/janbot/api/contract.py` — `Citation.source` description (:38) updated to the corpus-root-relative path form (AD-4 docs).
- `tests/test_chat.py` — `StubLMFactory` (:34-42) emits `citations`; happy-path citation pin (:100-107) updated from the absolute `located_path` form to the rewritten form; new rows: derived-from pin (two files indexed, `JANBOT_TOP_K=1`, assert only the retrieved file's source appears), forced uncited → 500 envelope, unknown-source claim → 500 envelope, leak pin (`str(tmp_path)` and leading `/` absent from the body).
- `tests/conftest.py` — `_chunk_id` (:40-42) builds production-style ids from `located_path`; reuse as-is (ids stay absolute).
- `tests/test_contract.py` — valid-construction example (:48-55) aligned to the corpus-root-relative citation form (cosmetic).
- `README.md` — Chat section: citations are corpus-relative; uncited answers rejected with the standard envelope.
- Do not touch: `store/`, `ingest/`, `llm/`, `config.py`.

## Tasks & Acceptance

**Execution:**
`- [x] `src/janbot/pipeline/chat.py` — citations output on the signature, labeled context, claim validation, metadata-backed rewritten citations, `UncitedAnswer` + out-of-root refusal — the derived-from enforcement point.
`- [x] `src/janbot/api/main.py` — wire the corpus-root rewriter into `ChatProgram` — config reaches the citation boundary.
`- [x] `src/janbot/api/contract.py` — `Citation.source` description to the corpus-root-relative form — contract docs match behavior.
`- [x] `tests/test_chat.py` — stub emits citations; happy-path pin updated; derived-from, forced-uncited, unknown-source, and leak-pin rows — every matrix row proven through the port.
`- [x] `tests/test_contract.py` — example citation form aligned — cosmetic consistency.
`- [x] `README.md` — document citation form and rejection semantics — docs match the contract.

**Acceptance Criteria:**
- Given a stubbed retrieval returning a known chunk, when `POST /chat`, then the answer cites that chunk's source in corpus-root-relative form — derived-from, not merely an indexed source.
- Given the model claims no citations, when the program runs, then the answer is rejected and the port returns 500 with a `{"detail"}` body naming the refusal.
- Given any 200 response, when its citations are inspected, then no value contains an absolute filesystem path (`$HOME`, tmp dir, or leading `/`).
- Given a chunk whose `source_path` lies outside the corpus root, when it is retrieved and cited, then the program refuses (500 envelope) rather than emitting an unrewritable path.
- Given the full suite, when run, then every story-3.2/3.3 pin (env-only routing, boot key gate, `/health`, 422/503/500 envelope shapes, schema pins) passes unchanged.

## Implementation Notes

<!-- Agent-owned. Append-only during implementation. -->

- 2026-10-12: Implemented per Code Map. `ChatProgram` gained a required `rewriter` param; `main.py` builds it as `corpus_relative(config.corpus_path)`. `GroundedAnswer` now has a `citations: list[str]` output field; validation order in `forward` is: empty retrieval → missing `source_path` → rewrite labels (out-of-root refuses via `UnattributableContext`) → predict → empty claims → unknown claims → dedup citations.
- 2026-10-12: Tests needed `JANBOT_CORPUS_PATH` (new `_chat_env` helper in `tests/test_chat.py`): the rewriter is built from `config.corpus_path`, so fixtures must point the corpus root at the tmp corpus they index — without it every rewrite correctly fails closed against the repo-default root (`public_profile_org`). Stub factory default claims `["profile.org", "projects.org"]`; per-test overrides cover the new rows.
- 2026-10-12: Added dedicated port tests for the out-of-root (matrix ERROR row 3 / acceptance criterion 4) and dedup (EDGE row) cases — they were demanded by the matrix/acceptance even though the test task's list names only the four other rows.
- 2026-10-12: Error messages echo only corpus-relative claim labels (safe, non-leaking); the out-of-root refusal names no paths at all, because chunk ids embed absolute located paths. DummyLM multi-field scripting (`{"answer", "citations"}`) verified against dspy 3.4.0 ChatAdapter (`format_field_with_value` → `parse_value` round-trips `list[str]`).
- 2026-10-12: Verification: `uv run pytest -q` → 105 passed (99 baseline pins unchanged + 6 new rows). Manual check ran in eval mode with the ambient `OPENAI_API_KEY` present (so one real gpt-4o-mini call): 200, citation `edeposit.org` — corpus-relative, no absolute path in the body. No lint/typecheck tooling is configured in the repo (pytest only).

## Plan Change Log

<!-- Append-only. Populated by step-04 during review loops. -->

## Review Triage Log

<!-- Append-only. Populated by step-04 on EVERY review pass. -->

### 2026-10-12 — quick lens

- **Verdict counts: 0 high / 2 medium / 2 low / 0 false / 0 maybe-false.** Four findings, all routed to patch; no intent_gap or bad_plan, no loopback.
- **Raw LM claims echoed into the 500 detail** (`src/janbot/pipeline/chat.py:116-120`) — **verdict: medium**. Verified: `unknown` is built from `prediction.citations` (LM-emitted strings) and interpolated into the `UncitedAnswer` message that becomes the `{"detail"}` body — a hallucinated absolute path would be reflected to the client, violating the frozen Always rule "LM-claimed source strings ... never passed through verbatim into a response". **route: patch** — raise with a message that does not interpolate raw claims; adjust the unknown-source test's detail assertions.
- **Bracketed label echo cannot validate** (`src/janbot/pipeline/chat.py:51,103-105,114-115`) — **verdict: medium**. Verified: context blocks display `[profile.org]` while the membership set holds bare labels, and the output-field description says "the exact [source] labels" — a model echoing the displayed bracketed form fails closed with 500 despite being grounded. **route: patch** — minimally normalize claims (strip surrounding whitespace and optional brackets) before matching.
- **"Indexed but not retrieved can never be cited" not directly proven** (`tests/test_chat.py:262-281`) — **verdict: low**. Verified: the TOP_K=1 pin asserts the retrieved source appears but never asserts rejection when the stub claims the indexed-but-unretrieved file; rejection rows use unindexed names only. Code is correct; coverage gap. **route: patch** — add the row (two files, TOP_K=1, claim the unretrieved-but-indexed file, assert 500).
- **Leak pin omits `$HOME`** (`tests/test_chat.py:379-400`) — **verdict: low**. Verified: AC 3 names `$HOME`, tmp dir, and leading `/`; the test covers tmp dir and leading `/` but never `str(Path.home())`. **route: patch** — add the home-dir absence assertion.

## Design Notes

- Why LM-claimed citations: the manual-prompt module has no other witness of derivation. The model names the sources it used; the program treats that as a claim, validates it against the retrieved metadata, and emits only metadata-backed values — the LM string never reaches the response verbatim. What cannot be proven (the model using a chunk it fails to name) stays out of scope for a manual prompt.
- Why labels are rewritten before the LM sees them: the absolute `source_path` must not reach the model context either — the rewrite serves privacy and gives the model short, copyable labels that match the emitted citations exactly.
- 500 for uncited/unverifiable answers: model-output integrity failure, consistent with the 3.3 matrix (503 = no grounding material; 500 = integrity). The rejection rides the existing `ValueError` mapping — no new route branch.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: all pass (99 baseline + new citation rows; every 3.2/3.3 pin unchanged)

**Manual checks (keyless, eval mode):**
- Start: `uv run uvicorn janbot.api.main:app`
- `curl -s -X POST localhost:8000/chat -H 'content-type: application/json' -d '{"question":"<real question>"}'` -- expected: 200; every `citations[].source` corpus-relative, no absolute path in the body
