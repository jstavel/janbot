# Task — re-baseline round: one corpus state, one index, one registered reference

**Priority:** high (blocks the published demo's honesty) · **Type:** corpus round
· **Owner-run:** the `terraform apply` and the new reference's sign-off.

## Why now — three divergences, one round

| Layer | State |
|---|---|
| `views/work-profile` (SSOT) | **ahead** — five re-filings, a new *Mentoring & people* section, a *Career stories* section, four project subsections, `:FEATURED:` (commit `339359e` in `~/org`) |
| `eval/golden_dataset.yaml` | **ahead** — 120 items, class 7/8 closed, `dataset_sha256` `c4786e1c…` |
| `public_profile_org/` + chroma index | **behind** — 59 objects, the old section structure, no `growth-in-any-role`, no `intent-based-delegation` |
| baked cache | **behind** — `dataset_sha256 a8bd69dc…`; the image build refuses it |
| `measurement-gemini-2.5-flash-val.md` | **superseded** — measured on the 106-item instrument |

Visible consequence, reported by the owner on the live demo: *"Do you know agentic
workflow?"* answers from adjacent chunks and cannot cite the two objects that now
describe the actual agentic work. This round is what makes the new structure and
the new instrument real.

## Definition of done (each with its evidence)

1. **A repeatable extract procedure exists — and it is a script, not a commit
   message.** The known deficit ("re-extract has no procedure or script; the only
   trace is a commit message") closes here. It takes `~/org/corpus/objects` +
   `views/work-profile/index.org` and emits the extract, deterministically.
2. **The extract is regenerated: 63 files** — 61 objects + `public-proof-map.org` +
   `thesis-map.md`. `MANIFEST` records the `~/org` commit pin and a per-file
   `sha256`, and the header's file count matches reality.
3. **The two new Czech objects enter as English translations with source pins.**
   `growth-in-any-role` and `intent-based-delegation` are Czech in `objects/`
   (per `corpus/README.org`: objects are the Czech write model). Their extract
   copies carry `:SOURCE-ID:` and `:SOURCE-SHA256:` pointing at the object — do
   **not** translate the objects themselves. The three re-filed objects
   (`openshift-kubernetes-bridge`, `intranet-pattern`, `linux-from-scratch`,
   `cpp-memory-allocator`, `perl-clojure-gateway`) are already English and only
   change section, not content.
4. **Index rebuilt from the new extract.** Record the chunk count; the app's
   startup scope guard (`out_of_scope_sources`) must pass, and no chunk may cite
   a source the extract does not contain.
5. **Gate thresholds re-registered *before* the new reference is measured.**
   Gate-eligible val is now **55** (val 69 minus 14 `should_refuse`); at the
   previous `n` the frozen "≥ 3 items" floor was inside 1.5σ, so carrying it
   forward would accept noise. Apply `gate-rule.md`'s own formula at n=55, freeze
   the result as a **new pre-registration**, then measure. The principle stays
   frozen (1.5σ, symmetric floor, metrics, populations); only the n-specific
   item thresholds are re-registered.
6. **A new reference is measured and registered** on the 120-item dataset with
   the reference judge pinned (`anthropic/claude-haiku-4.5`), `gate-rule.md`
   pointed at it, and `DECISIONS.md`/round notes updated. State plainly that
   `156b5d1a` and `c6ced445` are historical, and why.
7. **The baked cache is regenerated from the new index and the new dataset**
   (one production run, `RUNBOOK.md` §4). `cache/*.json` metadata must show the
   new `dataset_sha256` and the new corpus digest.
8. **Deploy, then re-measure the cold start.** `terraform plan` first, owner
   applies; rate 20/10 min, `startup_cpu_boost`, new image digest. Post-apply
   cold-start seconds are recorded beside the ~50 s pre-change number.
9. **`gemini-2.5-flash` re-measured on the new instrument** as the current
   decision input, superseding `effd4854`; the citation-precision dip belongs in
   that record.

## Constraints

- **One corpus state in the round.** Do not produce two indexes or two extracts;
  the previous round must be merged before the next re-baseline is computed.
- **No prompt, guard or model change.** Production keeps `openrouter/auto`; the
  model decision stays open until the new-instrument measurement exists.
- **No new objects and no new re-filings** beyond what the view already decided.
  `stepping-a-blocked-learner` stays out of the view on purpose (owner decision:
  personal teaching story, not work profile).
- **No squash-merge** for this branch: the round's documentation pins SHAs.

## Non-goals

The `jstavel-profile` renderer, SSE streaming, and the widget's suggested
questions are separate initiatives; none of them belongs in this round.

## Order (dependencies are real, not stylistic)

```
extract procedure → extract → MANIFEST → index rebuild
   → gate re-registration (frozen) → new reference measured
   → cache regenerated → plan → apply → cold start measured
   → gemini re-run (decision input)
```
