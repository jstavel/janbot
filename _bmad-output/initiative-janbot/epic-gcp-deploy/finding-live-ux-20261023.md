# Live UX measurement + a spurious refusal (2026-10-23, revision `00010`)

Two findings from measuring the deployed demo **through the real widget** (GitHub
Pages → CORS → Cloud Run), not through `curl`. Browser timings were taken with
Chromium over CDP: fill the form, submit, wait for `#reply`/`#error` to become
visible — i.e. the number a visitor experiences.

## 1. Latency profile — where the time actually goes

| Path | Measured | Note |
|---|---|---|
| baked answer-cache hit | **0.8–1.1 s** | e.g. "What is JanBot?" |
| any question the instance has already answered | **0.9 s** | an instance-level cache (DSPy/LiteLLM) — not designed, but real |
| **first-time question** | **5.0–15.0 s** | variance is the `openrouter/auto` routing |
| decline (relevance gate, pre-LM) | 0.9 s | fast by construction |
| cold start after idle | **6.0 s** | `startup_cpu_boost`, was ~40–50 s |

So the remaining cost is **first-time questions only** — 5–15 s, dominated by the
model call, not by the platform. This is the evidence the "speed up the UI"
decision needs: cache coverage and the production model are the levers;
streaming would not shorten the validation path (the output guard validates
citations only after the full answer exists).

## 2. A live spurious refusal — the relevance gate is phrasing-sensitive

```
POST /chat {"question": "What is your approach to failure recovery?"}
→ 200, status=insufficient, reason=out_of_corpus, in 0.93 s, 2/2 identical runs
```

The topic **is** in the corpus. Rephrased, the same intent answers:

```
POST /chat {"question": "How do you recover deleted files?"}
→ 200, status=answered, citations=[filesystem-recovery.org]
```

Mechanism: the low-relevance gate (`θ = 0.26`, two best chunks below θ) refuses
before the model call. So the refusal is not a grounding failure — it is a
**retrieval/θ sensitivity to wording**: "failure recovery" as an abstract phrase
does not embed near the incident narratives, while "recover deleted files" does.

Why this matters at the demo's level: a recruiter asks a natural, abstract
question and receives a graceful decline about a topic the profile demonstrably
covers. It is exactly the class `spurious_refusal_rate` measures (2/55 on the
current reference) — this is one of those two, observed live.

### Options (a decision, not a fix)

1. **Dataset** — add this question as a class-4 depth item with
   `expected_sources: [filesystem-recovery.org]`; it then measures the refusal
   rate per item instead of hiding inside an aggregate.
2. **Retrieval** — the query is abstract and the object is narrative; candidates
   are a hybrid-weight change, chunk-level summaries, or query expansion. All are
   gating-metric levers and would need their own run against the reference.
3. **θ** — lowering 0.26 trades this refusal against the over-claiming guard
   (ADR-009's deterministic protection). Not a free win; do not touch it without
   a measured comparison.
4. **Corpus** — an object that speaks to the abstract framing (a "recovery and
   failure" summary) rather than only the two incident narratives.

Order of preference: (1) first — it is measurable and cheap; then diagnose with
(2)/(4); (3) only with evidence.

## 3. Widget copy drift (fixed in the same round)

The widget's loading text still promised *"the first question after idle may take
up to ~23 s (the service cold-starts)"* — measured cold start is now 6.0 s and a
first-time question is 5–15 s, so the number was **pessimistic and wrong**. Copy
now reads: *"a new question can take up to ~15 s; common questions come back in
about a second."* The lesson is the owner's own: a detail that once carried a
guarantee must be re-measured when the thing it describes changes, or it turns
into a decorative claim.
