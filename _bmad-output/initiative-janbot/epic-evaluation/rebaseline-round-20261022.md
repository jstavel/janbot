# Re-baseline round 2026-10-22 — one corpus state, one index, one pre-registered gate

**Task:** `task-rebaseline-round.md` · **Plan:** `task-rebaseline-round-plan.md` ·
**Status:** extract, index, pre-registration, reference, cache and the gemini
re-measure **done**; the deploy (owner-run) is **pending** (see §Pending).

The three divergences this round closes: the `~/org` view (`339359e`) was ahead of
the extract, the 120-item dataset (`c4786e1c…`) was ahead of the baked cache
(`a8bd69dc…`), and the live demo could not cite the objects that describe the
actual agentic work. This note records what landed, what it was verified against,
and what remains.

## 1. The extract became a script (the deficit closes)

`tools/extract_public_profile.py` (stdlib-only) + `tools/extract_translations/`
(the versioned English translations: `intent-based-delegation.org`,
`growth-in-any-role.org`, `style-references-as-intent.org`). The script parses the
view's `[[id:…]]` selection **at the pinned commit**, byte-copies each selected
object (extract filename = the object's internal filename; `:ID:` preserved), and
for a Czech object emits the English translation with the
`:SOURCE-ID:`/`:SOURCE-SHA256:` pins **injected** — the sha256 of the object file
at the pinned commit; the translation artifact carries placeholders, never a
hand-written pin. It emits the two generated sections from the view and the
`MANIFEST` (commit pin, count line, sorted per-file sha256, excludes itself).

**Validation fixture (byte-green):** `--check --commit 05b11a7…` regenerates the
previous round's extract exactly — 62 files byte-equal (59 byte-copied objects +
the two generated sections + MANIFEST). The transforms reproduce the last round;
nothing was invented.

**Edge-case matrix, verified on a synthetic mini-corpus** (`/tmp` fixture, not
committed): a Czech `:TITLE:`/`:SYNOPSIS:` without a translation artifact is a
hard error naming the object (CZECH GUARD); the injected `:SOURCE-SHA256:` equals
the object file's sha256 at the pin (PIN); regeneration is byte-equal twice
(DETERMINISM); an extract file outside the view's selection fails `--check`
(ORPHANS); a hand-written pin or a wrong `:ID:` in a translation artifact is a
hard error. Czech detection is mechanical: a lowercase Czech-only letter
(`čďěňřšťůž`) in `:TITLE:`/`:SYNOPSIS:` — uppercase acronyms embedded in English
synopses (`OSVČ` in `nagios-snmp-monitoring`) stay English, which is what makes
the `05b11a7` fixture byte-green.

Commits: `c8279d5` (the script), plus a `--write` mkdir fix.

## 2. The extract regenerated at pin `339359e`

62 objects (the view's full selection) + `public-proof-map.org` + `thesis-map.md`
= **64 content files**, + `MANIFEST` (pin `339359e29484e2c57a1a546ccd8e19ae94571238`,
count line `# files: 64 — 62 objects + …`). Committed on the branch as janbot **`1aae1d8`**. The cache artifact's
`corpus_commit` is the repository HEAD at cache-run time (`a7752a0…`, which
contains the extract); the durable content pin is the MANIFEST's `~/org` commit
`339359e`. The 59 previously extracted objects are
byte-identical to their objects at both `05b11a7` and `339359e` (verified); the
two generated sections are byte-identical to the previous round (the view's
Thesis map and Public proof map sections did not change between the pins).

**Pinning rule (README):** the janbot commit SHAs in this note are branch
provenance for review and will be rewritten on merge; per the README they are
**not** durable references. The durable pins are the `~/org` commit `339359e`,
the dataset sha `c4786e1c…`, the run ids, and the cache artifact's own metadata.

**The three Czech objects enter as pinned English translations:**
`growth-in-any-role.org`, `intent-based-delegation.org`,
`style-references-as-intent.org` — each carries the object's `:ID:` plus
`:SOURCE-ID:`/`:SOURCE-SHA256:` pointing at the Czech object at the pin. The
objects themselves stay Czech (per `corpus/README.org`: objects are the Czech
write model; the extract is the English read model).

**Finding — the third stale-pointer-class error in this round's inputs** (the
pattern the plan names): the task's "61 objects / 63 files" was derived from the
stale extract's inventory instead of from the view. The view's selection is 62
unique ids (`05b11a7` selects 59 — exactly the previous extract; `339359e` adds
`style-references-as-intent`, `intent-based-delegation`, `growth-in-any-role`).
Owner decision (2026-10-22): corrected to **62 objects / 64 content files** and
recorded here. Same fix as `c6ced445`-from-memory and the eDeposit false-premise
item: **derive numbers from the current artifact, never from memory or from the
previous state.**

## 3. Index rebuilt

`uv run python -m janbot.ingest` over the new extract: **440 chunks / 63
sources** (was 417/60), identity `930e0a3d9fda676dcb6e9eb000b5cf4d9c5f5a221c8cbfc26af44f3f8e55c649`,
embedder `all-MiniLM-L6-v2@913d7300…` (unchanged). Verified path-independent:
a build from a copy of the corpus at another path produces the identical
identity. Startup scope guard passes: `create_app` does not refuse and
`out_of_scope_sources` is empty; the three new objects are present as sources;
no chunk cites a source the extract lacks (the index was built from the extract
tree itself). `chroma_db/` is gitignored — the image bakes its own at build.

Retrieval spot-check on the rebuilt index (hybrid/chunks, k=4): *"How do you
delegate work to an AI agent?"* now ranks `intent-based-delegation.org` first
(0.531) and *"What motivates you to grow in a role?"* ranks
`growth-in-any-role.org` second — the objects the demo could not cite before.
*"Do you know agentic workflow?"* still ranks the pre-existing sources
(`spec-first-pitch.org`, `procedure-drift.org`) — consistent with the dataset
item's own `expected_sources` (`janbot-ai-agent.org`, `spec-first-pitch.org`);
the new objects are citable, the dataset item is untouched by design.

## 4. Gate re-registered BEFORE measuring

`gate-rule.md` gained the **n = 55 pre-registration** (commit **`7161460`**),
frozen before any measurement, arithmetic shown: gate-eligible **n = 55** (val 69
− 14 `should_refuse`, verified against `eval/golden_dataset.yaml`,
sha256 `c4786e1c9e3f6f5c677b3ecbbee8fbc03ff19628b9bcf374aea958fc9cd9af20`); at
the outgoing reference's own p projected to n = 55 —
**citation_correctness accept ≥6 / regress ≤5** (5/55 = 0.0909 ≤ 0.0948;
6/55 = 0.1091 exceeds it), **faithfulness accept ≥4 / regress ≤3** (3/55 = 0.0545
≤ 0.0554 — exactly the noise-carry the task warns about; the frozen n=49 floor
≤2 must not be carried forward). Principle untouched: 1.5σ per metric at the
reference's own p, symmetric floor, fixed populations. `156b5d1a` is stated historical for the new instrument (corpus `05b11a7`,
dataset `a8bd69dc…`, 106 items); `c6ced445` is older still (dataset `1c3864bd…`,
91 items).

**Owner sign-off:** given with the plan approval (`approve and continue`) before
the reference run; the frozen threshold commit `7161460` predates the run. The
sign-off line was committed with the registration, so the commit time does not
by itself prove the ordering — the threshold commit does.

## 5. The new reference is measured and registered

The owner approved the plan carrying the n = 55 pre-registration before any
measurement; the frozen threshold commit `7161460` predates the run. Reference
run:

```sh
JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 uv run python -m janbot.eval --split val
```

- **Run id:** `e1a0fa4ef96f4f47b37dcea1e0bfba36` (MLflow, `sqlite:///mlflow.db`,
  experiment `janbot-eval`), artifact `run-e1a0fa4e-output.txt`.
- **Config:** eval mode, snapshot `openai/gpt-4o-mini-2024-07-18` (shipped
  default), judge pinned `anthropic/claude-haiku-4.5`, `chunks`, k=4, hybrid,
  θ=0.26, `program=baseline`, `output_guard=on`; dataset `c4786e1c…` (120 items,
  train 51 / val 69, val `should_refuse` 14); corpus `339359e`, index 440/63.
- **Measured (n = 55):** `citation_correctness` **0.6182** (34/55),
  `faithfulness` **0.8545** (47/55), `answer_coverage` 0.9636 (53/55),
  `citation_precision` 0.6348, `public_references` 0.9636,
  `retrieval_accuracy` 0.6545, `retrieval_mrr` 0.7121, `refusal_pass_rate` 1.0
  (n=14), `spurious_refusal_rate` 2/55. Diagnostics: 0 hard errors, 2 in-corpus
  declines, 0 judge failures.
- **Registration:** `gate-rule.md` now points at `e1a0fa4e` with run
  id/config/n=55; the frozen floors are the pre-registration (citation ≥6/≤5,
  faithfulness ≥4/≤3). `156b5d1a` and `c6ced445` are stated historical.
  This is a **re-baseline, not a verdict**; the principle is untouched.

## 6. The baked cache is regenerated

One production run on the new index and the 120-item dataset:

```sh
JANBOT_MODEL_MODE=production JANBOT_RETRIEVAL_MODE=hybrid \
JANBOT_RETRIEVAL_WINDOW=chunks JANBOT_TOP_K=4 \
JANBOT_RELEVANCE_THRESHOLD=0.26 JANBOT_OUTPUT_GUARD=on \
uv run python -m janbot.eval --split val --cache-out cache/answers-9f51134f4ac94c8396b093761e394814.json
```

- **Run id:** `9f51134f4ac94c8396b093761e394814`; **55** non-refusal answers.
- **Artifact metadata:** `dataset_sha256` `c4786e1c…`, `corpus_commit`
  `a7752a0…`, `corpus_sha256` `40966e97…`, `requested_model` `openrouter/auto`,
  `output_guard` on.
- `Containerfile` `--source` repointed to the new artifact; the old artifact is
  removed (git history keeps it). `python -m janbot.guardrails.build_cache
  --source … --corpus-commit a7752a0…` validates: **55 entries written**.
  (The cache run needs `JANBOT_FIRESTORE_PROJECT` and a `JANBOT_CACHE_PATH` only
  because the API module builds its default app at import time in production
  mode; the eval app itself receives the no-op limiter and does not serve.)

## 7. Deploy plan verified — the apply is the owner's

`terraform validate` passes. `terraform plan` with `-var image_tag=7e2d69e` (the
round's commit) shows exactly the named changes and nothing else:

- `docker_registry_image.janbot` **replaced** (`:dev` → `:7e2d69e`; triggers
  `cache`, `containerfile`, `corpus`, `dataset`, `src` all changed);
- `google_cloud_run_v2_service.janbot` **updated in place**: the image digest
  moves, `JANBOT_RATE_LIMIT` 10 → 20, `startup_cpu_boost` false → true. The last
  two are the E3 config already in the code, not drift — the plan surfaces them
  because the deployed revision predates that commit;
- `Plan: 1 to add, 1 to change, 1 to destroy` (the replace), plus the
  `image_digest` output.

**The apply is owner-run.** After it, the cold start is measured per the runbook:
wait ≥15 min for the instance to be idle, then time one baked-question request
and record the seconds beside the ~50 s pre-change number in
`epic-gcp-deploy/run-e3-public.md`. A docs-only commit after this plan does
not change any image trigger, so the apply may use the final HEAD sha as its
`image_tag`; no source, corpus, cache or Containerfile byte moves.

## Pending (the owner's remaining steps)

1. **Owner applies** the verified plan above, then records the post-apply cold
   start beside ~50 s in `epic-gcp-deploy/run-e3-public.md`.

