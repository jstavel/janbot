---
title: 'Golden dataset breadth toward the gate power'
type: 'feature'
ticket: 20
created: '2026-10-15'
status: 'draft'
baseline_revision: '134509b'
route: 'full'
route_source: 'auto'
risk: 'high'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** the optimization gate is **undecidable at n=15** — all three retrieval levers landed within the 1.5σ floor (top_k +1, hybrid +2) or beyond it in the wrong direction (source-diverse REJECT −4), and the refusal gate shipped. `gate-rule.md`'s own rule says **breadth gates optimization** (~100 val items to detect a ~5% effect). The audit adds the shape: the val carries grounding pressure (union Z=8) but the classes are thin (5 weakness, 7 adversarial, 8 refusal, 10 voice), **only one of 15 val items is multi-source**, and 7.2 exposed class 8's thinness plus the likely **ill-posed** managed-Kubernetes item (similarity 0.5111 — corpus-adjacent to the K8s bridge object).

**Approach:** **option (i) — grow the dataset so the gate-eligible val n ≈ 100** (the ten-class grid; not accumulated), stratified into both splits, ≥ ~10 val per class, sources spread across the corpus, every expected source in `public_profile_org/`. The **gate-eligible n is val minus `should_refuse`** (`citation_correctness`/`faithfulness` exclude declined items), so the ~100 target is gate-eligible items and class 8's ≥10 refusal val items sit **outside** it. Author in **per-class batches the owner approves** (the golden items are the owner's content — hitl). **Fix class 8**: author more refusal items and **decide the EKS item** (fix its phrasing to a cleanly out-of-corpus question, reclassify it in-corpus if the K8s bridge object actually answers it, or drop it). Verify the target by the **measured-N method**: a deterministic **context-sensitivity screen** over the val items (window changes across top_k 4/6, dense/hybrid, chunks/sources — free, no model, and it **over-predicts**), then **confirm the grounding-pressure count in a keyed val run**, iterating authoring until the confirmed count is **≥ ~14 (2× the re-instantiated ~7-item floor)**. Finish with a **re-baseline AND a re-instantiation of the gate rule**: the **principle stays frozen** (1.5σ, symmetric floor, gate metrics, populations), but its **n-specific thresholds are re-registered** for the new gate-eligible n — at gate-eligible **n=100**, σ = √(0.73·0.27/100) ≈ 0.044, 1.5σ ≈ 0.067, so **accept ≥ 7 items (0.07), regression allowed ≤ 6 (0.06)** — recorded as a **NEW PRE-REGISTRATION** frozen **before** the n=100 reference is measured (it precedes the result, so it is not post-hoc). The frozen "≥ 3 items" at n=15 is **inside** 1.5σ at n=100 and would accept noise, so carrying it forward is self-defeating. Options (ii) the 3×12 fallback and (iii) accept "no decision" are recorded but not chosen — (ii) cures run-variance, not item-level binomial noise, and the diagnosed misses are deterministic retrieval, so repeats add nothing for this bottleneck.

## Boundaries & Constraints

**Always:** growth is **distributed across the ten classes** (the grid), each class stratified into **both** train and val, **≥ ~10 val per class**, sources spread across the corpus (not all JanBot), every expected source present in `public_profile_org/`; the owner approves the authored items (hitl); the measured-N method decides the count (screen → keyed confirm → iterate to **≥ ~14**); the **gate-eligible n is val minus `should_refuse`** and 1.5σ is computed on **that**, not the total val; the re-baseline records a new reference **and re-registers the gate rule's n-specific thresholds** (the principle — 1.5σ, symmetric floor — stays frozen; the instantiation is a **new pre-registration frozen before the reference is measured**).

**Never:** no change to the gate rule's **principle** (1.5σ, symmetric floor, gate metrics, populations) — but the n-specific thresholds **are** re-instantiated: this is **not** a pointer-only update (5.13 was a same-n re-baseline; breadth changes n, so the n-derived thresholds must be re-registered); no metric-definition change; no optimization stage (8/9 stay gated — breadth is their precondition, not a restart); no refusal-gate or `/chat` change.

## Code Map

- `eval/golden_dataset.yaml` — the 41 items today (23 train / 18 val; 3 are `should_refuse: true`); the growth target.
- `src/janbot/eval/dataset.py` — the loader's `split` / `should_refuse` validation (fail-closed), `load_golden_dataset(path, split=None)`, `split_manifest`.
- The **ten-class grid** and the **faithfulness-asymmetry** note (epic-evaluation Notes, 2026-10-15) — the authoring grid and the reason N is measured.
- `epic-evaluation-dataset-classes.md` — the audit's per-item mapping and its finding that **class labels do not predict grounding pressure** (X=2 by class, Y=6 observed, Z=8; the two disjoint).
- `src/janbot/eval/metrics.py` — `refusal_pass_rate` / `spurious_refusal_rate` (class 8's measurement) and the shared eligibilities.
- 7.2's findings: `epic-graceful-decline.md` (the EKS item's 0.5111 similarity; the `LowRelevance` gate at θ=0.26) and `run-7.2-theta-probe-incorpus.txt`.
- `_bmad-output/initiative-janbot/epic-evaluation/gate-rule.md` — the rule to **re-instantiate** at the new gate-eligible n at the re-baseline (its principle — 1.5σ, symmetric floor, gate metrics, populations — stays frozen; its n-specific thresholds are re-registered, pre-registered before the reference is measured).
- Reference: MLflow run `9c7260da` (the current reference; refusal_pass_rate 0.3333).

## Tasks & Acceptance

**Execution:**
- [ ] `eval/golden_dataset.yaml` -- author val items per class (batches the owner approves; ≥ ~10 val per class, stratified, sources spread) -- the breadth (hitl).
- [ ] `eval/golden_dataset.yaml` -- fix class 8: author more refusal items and resolve the EKS item (rephrase / reclassify in-corpus / drop) -- the class-8 repair.
- [ ] run the deterministic context-sensitivity screen over the new val items (no model) -- the grounding-pressure candidate set (over-predicts).
- [ ] run the keyed val eval and count the items whose faithfulness verdict moves under perturbation -- the confirmed N; iterate authoring until **≥ ~14** (hitl).
- [ ] re-baseline: a fresh val run becomes the new reference; **re-register the gate rule's n-specific thresholds for the new gate-eligible n** (principle frozen; thresholds re-instantiated — at n=100, accept ≥ 7, regression ≤ 6) and record the pre-registration -- the new gate reference + rule instantiation.
- [ ] record the decision, the per-class counts, the gate-eligible n, the N evidence, and the EKS resolution in the epic Notes -- the deliverable.

**Acceptance Criteria:**
- Given the authored dataset, when it loads, then every class is stratified into both splits, each has ≥ ~10 val items, every expected source is in `public_profile_org/`, and the loader validates it fail-closed.
- Given the screen, when it runs, then it flags the context-sensitive val items deterministically before any keyed run; given the keyed run, then the confirmed grounding-pressure count is recorded and authoring iterates to **≥ ~14** (a shortfall is recorded with the next step).
- Given class 8, then it holds more than three refusal items and the EKS item is resolved (a documented decision), with `refusal_pass_rate` / `spurious_refusal_rate` re-measured.
- Given the re-baseline, then a new reference run is recorded and the gate rule's **n-specific thresholds are re-registered for the new gate-eligible n** (the principle unchanged; at n=100: accept ≥ 7, regression ≤ 6, frozen before the reference is measured), so a lever is judged against a threshold that is outside noise — the frozen "≥ 3 items" at n=100 would sit inside 1.5σ and accept noise.

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Design Notes

- **Scale, honestly.** Gate-eligible val ≈ 100 at the current ~60/40 split implies ~150 train items — roughly **200+ authored items**, an owner content effort, not an agent code change. The plan stages it: the agent **drafts** each class's items from the corpus with candidate expected answers and sources; the owner approves/edits (the 5.17 "owner correction pass" precedent); each batch is committed with the manifest. Class 8's refusal val items sit **outside** the gate-eligible n.
- **The rule is re-instantiated, not pointer-moved.** The gate rule's *principle* is n-independent (1.5σ, symmetric floor), but its *thresholds* were instantiated at n=15 (≥3 items / ≤2). At gate-eligible n=100, σ ≈ 0.044, 1.5σ ≈ 0.067 → **accept ≥ 7 items (0.07), regression ≤ 6 (0.06)**. The re-instantiation is pre-registered (frozen before the n=100 reference is measured); 5.13's same-n re-point is a different operation.
- **Why designed, not accumulated.** The audit shows class labels do not predict grounding pressure, so breadth cannot be judged by item count alone — the **screen + keyed confirm** is what proves the val can actually move the gate. The grid still governs *coverage* (each failure mode present, stratified); the measurement governs *power*.
- **The N target is restated for the new floor.** "≥ ~9" was derived against the n=15 floor (3 items, ~3× headroom); at the re-instantiated ~7-item floor that is only ~1.3× — thin. The target is **≥ ~14** (2× the ~7-item floor), or 9 stands only as a bare minimum with no comfort margin.
- **The 3×12 fallback (option ii), recorded.** It cures run-to-run variance by averaging repeats, but the diagnosed misses are **deterministic retrieval** — repeating a run reproduces them — so it adds nothing for this bottleneck; it is not chosen.
- **The EKS decision.** The managed-Kubernetes item expects a decline, but the corpus's `openshift-kubernetes-bridge.org` discusses Kubernetes vocabulary (best similarity 0.5111), so the item may be **answerable** — in which case it becomes an in-corpus item citing the bridge, not a refusal item. The class-8 repair decides this by reading the bridge object.

## Verification

**Commands:**
- `uv run pytest -q` -- expected: green; the loader validates the grown dataset fail-closed.
- the deterministic context-sensitivity screen -- expected: the flagged val items (no model, no key).
- `JANBOT_JUDGE_MODEL=anthropic/claude-haiku-4.5 OPENROUTER_API_KEY=… uv run python -m janbot.eval --dataset eval/golden_dataset.yaml --split val` (hitl) -- expected: the grounding-pressure count confirmed **≥ ~14**; the gate-eligible n recorded; the run recorded as the new reference.
- Manual: the gate rule's **n-specific thresholds are re-registered** for the new gate-eligible n (principle unchanged; at n=100 accept ≥ 7, regression ≤ 6, pre-registered); the epic Notes record the decision, per-class counts, gate-eligible n, N, and the EKS resolution.
