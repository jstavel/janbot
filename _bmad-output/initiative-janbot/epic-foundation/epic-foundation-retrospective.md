---
epic: epic-foundation
date: 2026-10-05
verdict: accepted-with-open-items
criteria: declared
headless: false
---

# Retrospective — epic-foundation (Workspace, tooling & CI baseline)

## Epic summary

- **Epic:** `epic-foundation` — "Workspace, tooling & CI baseline" (initiative `initiative-janbot`, Milestone 1).
- **Tickets:** `1.1` Project scaffold & runnable skeleton — **done**; `1.2` Configuration loading — **done**; `1.3` CI workflow — **done**. `pending_tickets`: none. No ticket left at `built`.
- **Criteria:** declared — `epic-foundation.md` Done when (4 checks).

### Diff ranges (per plan baseline)

| Ticket | Baseline | Range | Commits |
| --- | --- | --- | --- |
| 1.1 | `NO_VCS` (unborn repo) | none recorded | best-effort: `2dcb61f` (scaffold), `cbe5b7b` (planning) |
| 1.2 | `b0693022…` | `b0693022..6795fc75` | `abb7e37` (config), `6795fc7` (planning) |
| 1.3 | `6795fc75…` | `6795fc75..1236631` | `1236631` (CI) |

### Evidence inventory

- Present: epic file; initiative Requirements; entries (`tickets.py status`); all three plans; commits and per-file churn (`git_evidence.py`); ARCHITECTURE.md and the spec/decisions as context.
- **Missing:** a recorded commit/diff evidence for ticket 1.1 — its plan's `baseline_revision` is `NO_VCS`, so no range exists (recorded, not hidden).
- **Missing:** session logs for the tickets — process-lesson analysis is limited to what the plans and diffs show (the plans carry Implementation Notes and Review Triage Logs, which stand in).
- **Narrowing:** the review diff at `/tmp/janbot_epic.diff` (25.7 KB) covers the hand-written code/config/docs only — `uv.lock` and planning artifacts are excluded. The `bmad-review` skill was not invoked as a separate run; the adversarial, edge-case, and verification-gap lenses were run inline over that diff and are recorded as such.

## Findings

Grouped by view/lens; each carries a source and a disposition (fix now → action item / defer / accept as-is).

### Architecture delta (aggregate)

- **Corpus root: one boundary, two owners.** `src/janbot/config.py:37,69` makes the fail-closed corpus root env-tunable (`JANBOT_CORPUS_PATH` → `corpus_path`), while AD-3 (`architecture-janbot.md`, AD-3) and the spec Constraints fix the indexed set to the literal `public_profile_org/` and place the boundary in the ingestion pipeline. If `epic-ingestion` roots its whitelist at `config.corpus_path`, the env var moves the whitelist anywhere; if it hardcodes the literal, `corpus_path` is an unused second owner. **Disposition: fix now (spec reconciliation) — resolve at epic-ingestion inception.**
- **`Config` under-covers AD-5.** `src/janbot/config.py:45-48` carries only mode/snapshot/corpus/index. AD-5 and `spec-janbot.md` CAP-6 require a production route (`openrouter/auto` or a fallback sequence) and `temperature=0` for eval; the spine's Consistency Conventions also list `top-k` as a config tunable. No field/var exists, so `llm/` must hardcode or overload `model_snapshot`. **Disposition: fix now (remediation) — extend in epic-rag-chat.**
- **Unanchored paths.** `src/janbot/config.py:69-70` returns raw relative `Path`s resolved against the process CWD; the index writer (ingestion) and reader (`store/`) can run from different CWDs, silently opening/minting different `chroma_db` dirs. **Disposition: fix now (remediation) — anchor to a project root in epic-ingestion.**
- **Embedding dependency undeclared.** `pyproject.toml:11-18` pins fastapi/uvicorn/pydantic/dspy/chromadb/orgparse but no embedding package, while the spine's Stack lists `sentence-transformers` / `all-MiniLM-L6-v2`. "Pinned Milestone 1 dependencies" is therefore incomplete for the ingestion epic. **Disposition: fix now (remediation) — declare in epic-ingestion.**
- **Build backend unlocked.** `pyproject.toml:27` — `requires = ["hatchling"]` is unpinned and absent from `uv.lock` (`grep` → 0), so `uv sync --locked` still fetches an arbitrary hatchling in the isolated build env. **Disposition: defer (low) — E1 reproducibility nit.**
- **No duplication, no cycles, no god-class.** Largest files: `tests/test_config.py` 105 lines, `config.py` 71; no cross-ticket duplication; imports are acyclic and the package layout matches the spine's Structural Seed. **Disposition: accept as-is.**
- **Inert ignore line.** `.gitignore:9` — `.bmad-output/` matches nothing (the real folder is `_bmad-output/`). Harmless. **Disposition: defer (low cleanup).**

### Adversarial lens

- **`ARCHITECTURE.md:35,51`** — the ADR-002 / ADR-004 links point at `…/tree/main/_bmad-output` (a folder listing), not `…/spec-janbot/decisions.md`. **Disposition: fix now (remediation, docs).**
- **`tests/test_smoke.py:14-18`** — version metadata assertions couple the test layer to driven-adapter versions, which AD-7 declares invariant; `uv sync --locked` already fixes versions. (Deliberate fix from story 1.1's review.) **Disposition: accept as-is (intentional drift tripwire).**

### Edge-case lens

- **Blank/whitespace env collapses the scope guarantee.** `src/janbot/config.py:69` — `JANBOT_CORPUS_PATH=""` yields `Path(".")` (the repo root) and `"  "` a literal whitespace path; empty string is not treated as unset, and values are not stripped. **Disposition: fix now (remediation) — treat empty as unset, strip, validate.**
- **Mode matching is brittle.** `src/janbot/config.py:59-60` — `"Production"`, `" production"`, `"production\n"`, and empty `""` all raise, rather than normalizing or falling back to the documented default. **Disposition: fix now (remediation) — normalize/trim, empty → default.**
- **Snapshot unvalidated.** `src/janbot/config.py:68` — blank `JANBOT_MODEL_SNAPSHOT` propagates as the model id with no fail-fast, unlike mode. **Disposition: fix now (remediation).**
- **`/health/` (trailing slash)** returns `307`; standard FastAPI behavior, health probes normally follow it. **Disposition: accept as-is.**
- **CI trigger/credential hardening.** `.github/workflows/ci.yml:3-5,15` — bare `push`/`pull_request` (no branches/concurrency/timeout) and `actions/checkout` default `persist-credentials: true` write a token into `.git/config` while running repo-controlled tests. `permissions: contents: read` bounds it. **Disposition: defer (low).**

### Verification-gap lens

- **Done when 4 unobserved.** No CI run exists (`gh run list --workflow=CI` → none; commits unpushed). The workflow's refs do resolve (`git ls-remote` for `checkout@v7` and `setup-uv@v10.2.0`). **Disposition: fix now (process) — verify on first push.**
- **Done when 1 wording.** Bare `uv run` errors ("Provide a command…"); the service starts via `uv run uvicorn janbot.api.main:app` (verified). `pyproject.toml` has no `[project.scripts]`. The criterion is met in substance, imprecise in wording. **Disposition: fix now (spec reconciliation, epic wording).**
- **Tests assert against module constants, not the documented contract.** `tests/test_config.py:24,45,56,66,75,83,92` reference `MODEL_MODE_ENV`/`DEFAULT_*` constants and no `JANBOT_` literal appears in `tests/`; renaming the prefix or changing a default keeps all 12 tests green while the README table silently breaks. **Disposition: fix now (remediation, tests).**
- **`test_dependencies_importable`** compares metadata strings and never imports the packages (`tests/test_smoke.py:13-18`), so a metadata-present-but-import-broken package passes. **Disposition: fix now (remediation, tests).**
- **Spine subpackages and uvicorn never exercised.** `pipeline/`, `ingest/`, `store/`, `llm/` are never imported by any test and `uvicorn` is untested, so Done when 2's "imports resolve" and Done when 1's startup are only partly evidenced. **Disposition: fix now (remediation, tests).**
- **Lock freshness only checked by CI.** `uv.lock` ↔ `pyproject.toml` consistency is enforced solely by the never-run `uv sync --locked`. **Disposition: defer (low) — covered once CI runs; or add `uv lock --check`.**

## Behavior verification

Exercised end to end (not just tests): started the real service with `uv run uvicorn janbot.api.main:app --port 8137` and issued `curl /health` → **HTTP 200 `{"status":"ok"}`**; ran `load_config({})` → the four documented defaults. The CI workflow was **not** exercised — no remote/push exists, recorded as the Done-when-4 gap.

## Previous-retro follow-through

None — this is the first epic retrospective in the initiative; there is no previous `epic-*-retrospective.md` to check.

## Action items (proposed; the human decides what to execute)

Remediation and spec-reconciliation items; owners in parentheses.

1. Decide the fail-closed corpus-root ownership and align `config` with AD-3/the spec — fixed literal vs validated root. (human, at epic-ingestion inception)
2. Extend the config contract (production route/fallback, `temperature`, `top-k`) before the LLM adapter is built. (epic-rag-chat)
3. Anchor `corpus_path`/`index_path` to a project root so writer and reader agree. (epic-ingestion)
4. Declare and pin the embedding dependency (`all-MiniLM-L6-v2` / `sentence-transformers`). (epic-ingestion)
5. Harden `load_config`: empty/whitespace env = unset, strip values, normalize mode, validate blank snapshot. (follow-up story on config)
6. Harden tests to assert the documented contract: literal `JANBOT_*` names and defaults, an actual dependency import, the spine subpackages, and service startup. (follow-up story)
7. Pin the build backend (hatchling) or add a lock-freshness check. (follow-up)
8. CI hardening: `persist-credentials: false`, `concurrency`, `timeout-minutes`. (follow-up, low)
9. Fix the `ARCHITECTURE.md` ADR links to point at `spec-janbot/decisions.md`. (human, docs)
10. Push and observe the first CI run green — closes Done when 4. (human)
11. Reconcile `epic-foundation.md` Done when 1 wording with the documented start command. (human, spec)

**Process lessons** (prevent the next one): a story's frozen Intent should not lock a data contract (the four `Config` fields) that the architecture spine already says will grow — derive the contract from the spine, not the story. Tests should assert the *documented public* contract (literal names/defaults), not the module's own constants, or they give false confidence. A Done-when that depends on an external observation (a CI run) needs an explicit "observe after first push" item, never an assumed pass.

## Acceptance verdict

**accepted-with-open-items** — criteria `declared`.

- Done when 1–3 are demonstrably met: `uv sync` clean and the service starts via the documented command (behavior check, HTTP 200); the layout matches the spine; config defaults and overrides load (12 tests pass).
- Done when 4 (CI green on a push) is **delivered but unobserved** — the workflow exists and its action refs resolve, but no run has executed because the repo is unpushed. Recorded as the primary open item (#10); **not silently accepted**.
- Named findings above remain deferred/tracked. No ticket of this epic is unfinished.
- Strict reading: if Done when 4's first green run is required *before* acceptance, this retrospective is instead **rejected** pending item #10 — the human decides.

## Open questions

- Should `JANBOT_CORPUS_PATH` be able to move the fail-closed whitelist at all? (drives action item #1)
- Does Milestone 1 want a `[project.scripts]` entry (e.g. `janbot`) so "run the service" is a first-class command? (drives #11)
