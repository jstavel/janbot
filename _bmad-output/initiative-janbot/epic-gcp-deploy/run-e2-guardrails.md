# E2 guardrails — runbook and cost bound

**Date:** 2026-10-20 · **Project:** `janbot-deploy-2026-10` · **Region:** `europe-central2`.

The guardrail layer sits **in front of** `/chat`: input bounds → per-IP rate →
answer cache → global quota → program. `/health` is unchanged. The `/chat`
contract and the AI core are untouched.

## Controls and evidence

| # | Control | Where | Acceptance evidence |
|---|---|---|---|
| 1 | Answer cache (demo shield) | `src/janbot/guardrails/cache.py`; artifact `cache/answers-fc430d3e17714457b896bafdac9cc1ac.json` | `tests/test_guardrails_api.py::test_cache_hit_makes_zero_model_calls_and_is_contract_shaped`; `build_cache` validates the pinned artifact |
| 2 | Per-IP rate limit | `src/janbot/guardrails/limits.py` | `test_nth_request_is_served_and_n_plus_one_is_refused` |
| 3 | Hard global quota (conservative request quota) | same | `test_exactly_the_quota_is_allowed_under_concurrency` |
| 4 | Input bounds | `BodySizeLimitMiddleware` + the `/chat` question check | `test_oversized_body_is_rejected_before_parsing`; `test_over_long_question_is_rejected_before_rate_and_model` |
| 5 | Over-claiming guard | ADR-010 inside `ChatProgram.forward` | `probe_over_claiming-e2-output.txt` |
| 6 | Abuse control | rate + quota + input bounds (CORS arrives at E3) | the two counter tests above |

**Fail closed:** every Firestore error becomes a denial (`503`), never a pass.
`test_store_error_fails_closed` pins it.

**Quota semantics:** the global counter is a **conservative request quota** —
every request that reaches the program consumes a slot, including a pre-LM
refusal (empty retrieval / low relevance). It bounds spend from above; a refusal
flood can exhaust the daily quota (availability trade; the per-IP rate limit
bounds the rate, not the total). Exact model-call counting would need a pre-LM
hook in the AI core, which E2's boundary forbids.

**Off switch:** `JANBOT_GUARDRAILS=on|off`, default `on`. `off` is honoured only
outside production; `JANBOT_MODEL_MODE=production` + `off` fails fast at startup
(`tests/test_config.py::test_production_with_guardrails_off_fails_fast`).

## Cache provenance

The cache is **real model output**, not the golden `expected_answer`. It was
recorded from a **production-config** run:

- run id `fc430d3e17714457b896bafdac9cc1ac`, `split=val`, `JANBOT_MODEL_MODE=production`, `openrouter/auto`;
- routed models: `deepseek/deepseek-v4-flash-0731`, `deepseek/deepseek-v4.1-flash-1017`, `google/gemini-2.5-flash`, `openai/gpt-6-luna`, `z-ai/glm-5.3-flash`;
- **49 non-refusal answers** (59 val items minus the 10 refusals); refusals stay live because θ declines them pre-LM and caching them would freeze the item-3 reason heuristic;
- dataset sha `a8bd69dc…`, corpus commit `bf04023…`, corpus tree sha `2cc21360…`, `output_guard=on`.

Regenerate the cache with one production run (the exporter uses a no-op
guardrail limiter and does not need Firestore; the key is used only for this
run, never at build time):

```sh
JANBOT_MODEL_MODE=production JANBOT_RETRIEVAL_MODE=hybrid \
JANBOT_RETRIEVAL_WINDOW=chunks JANBOT_TOP_K=4 \
JANBOT_RELEVANCE_THRESHOLD=0.26 JANBOT_OUTPUT_GUARD=on \
uv run python -m janbot.eval --split val --cache-out cache/answers-<run>.json
```

The image build runs `python -m janbot.guardrails.build_cache`, which **fails if
the current dataset sha or corpus tree sha differs from the artifact** — the
artifact must be regenerated when either changes. The cache key is normalized
question text (trim, lower-case, whitespace-collapsed); novel phrasings miss by
design.

## Cost bound (one place, measured and worst case)

Measured production call (`openrouter/auto` → `openai/gpt-6-luna`, 2026-10-20):
1,263 input, 115 output, 1,260 cache-write tokens. At **500 model calls/day × 31
days = 15,500 calls**:

| routing | OpenRouter price (in / out / cache write per M) | $/call | 15,500 calls/month |
|---|---|---|---|
| measured `openai/gpt-6-luna` | $0.10 / $0.50 / $0.125 | $0.000341 | **$5.29** |
| owner example `openai/gpt-6-astra` | $10 / $50 / $12.50 | $0.0341 | **$529** |
| worst-case catalogue `openai/o1-pro` | $150 / $600 / unpriced (use prompt) | $0.258–$0.447 | **$4,006–$6,935** |

The quota is a conservative **request** quota: pre-LM refusals consume a slot, so
the call count is an upper bound on model calls. `openrouter/auto` is **not
pinned**: the measured row is a sample. The catalogue
maximum is a conservative upper bound. **The quota bounds calls, not dollars.**
The money tail is accepted explicitly, with the **500 CZK (~$20) budget alert**
as the backstop. A hard money cap would require pinning the production model or
lowering the quota to ~2.5 calls/day at the worst-case model, which is not a
viable demo.

## Firestore operations and latency

- **Cache miss:** per-IP window (1 read + 1 write) + global quota (1 read + 1
  write) = **2 writes minimum plus 2 reads (4 ops)**; at the measured 50–90 ms/op
  that is **200–360 ms** added.
- **Cache hit:** rate only = **1 read + 1 write (2 ops)**, **100–180 ms**; the
  global-quota read/write pair disappears because no model call is made.

The counter is a **single document** per counter (`FieldValue.increment`, with a
read-then-set window reset for the rate counter), not sharded: the spike measured
one document absorbing 100 sustained writes/s with exact counts
(`spike-quota-counter.md`). The implemented transaction is verified against a
throwaway Firestore native database in `spike-quota-counter-e2-output.txt`:
20 concurrent quota increments at cap 10 → exactly 10 allowed; 11 concurrent
rate checks at cap 10 → 9 allowed and 2 fail-closed store errors under first-write
contention (the cap is never exceeded); an unreachable database → `store_error`
for both.

**Cache-hit quota bypass (stated consequence):** a hit makes no model call and
skips the global quota. A flood of cache hits is bounded only by the per-IP rate
× available IPs × `max_instances=2`; cost is safe, availability is the accepted
trade.

## Terraform and apply

E2 owns the Firestore resource:

- `google_firestore_database.janbot` — native, `europe-central2`, `delete_protection_state = DELETE_PROTECTION_ENABLED`, `deletion_policy = ABANDON`;
- `google_project_iam_member.run_datastore` — `roles/datastore.user` for `janbot-run`;
- Cloud Run env: `JANBOT_GUARDRAILS=on`, cache path, Firestore project/database,
  rate/quota/input values.

The Firestore IaC moved from E4b to E2; E4b is WIF + GitHub Actions only
(`epic-gcp-deploy.md`, `tickets.toml`). The round ends at a verified
`terraform plan`; the **owner runs the apply** (same blast-radius rule as E1.5),
then verifies the phase-2 checks.

## Over-claiming evidence (ADR-010, control 5)

`probe_over_claiming-e2-output.txt` records:

- `"Would you like to work for our company?"` → **answered**, but the
  first-person commitment clause is dropped; no first-person commitment/interest
  assertion reaches the caller. ADR-010 D2 repairs the clause and keeps the
  grounded remainder; it does not force a whole-answer decline.
- `"Have you used Clojure in production systems?"` → **answered** with
  `['edeposit.org']`.

## Verification

```sh
ulimit -n 16384 && uv run pytest -q
JANBOT_MODEL_MODE=eval uv run python _bmad-output/initiative-janbot/epic-gcp-deploy/probe_over_claiming.py
terraform -chdir=terraform validate && terraform -chdir=terraform plan
python -m janbot.guardrails.build_cache \
  --source cache/answers-fc430d3e17714457b896bafdac9cc1ac.json \
  --out /tmp/answers.json
```

## Live acceptance (2026-10-20, owner-run with an independent reviewer)

Deployed revision **`janbot-api-00005-xqs`**, image `sha256:13f0aac0…`, Firestore database
`janbot` (native, `europe-central2`). Authenticated calls through a throwaway service account
(`roles/run.invoker` + key), deleted afterwards; the service IAM policy is empty again, so the
window of access closed with the checks.

| # | control | evidence | verdict |
|---|---|---|---|
| 1 | cache hit | 200, **0.22 s**, cites `departure-narrative.org`; the same class of question on a miss: 200, **11.0 s** (~50× contrast) | ✅ hit is a served answer with no model call |
| 2 | per-IP rate limit | 10 requests / 600 s window: 6 served (4 already spent earlier) then 7–11 → **429** `{"detail":"too many requests"}` | ✅ |
| 3 | global quota | counters live in `janbot_guardrails`: `quota_2026-10-20` `count=2` after two model calls; rate doc keyed by a **hashed IP** (`rate_40e739e1…`), no raw address stored | ✅ wired and counting |
| 4 | input bounds | 2 500-char question → **422** `question exceeds the maximum length of 2000 characters`; 9 000-byte body → **413** `request body too large` | ✅ rejected before any model call |
| 5 | **over-claiming guard** | `"Would you like to work for our company?"` → **200 answered**: *“Yes, I’d be interested. I’m drawn to a workplace where people have the freedom to contribute thought.”* | ❌ **FAILS** |
| 6 | fail closed | not exercised against the live store (would require breaking Firestore); covered by the unit tests and the spike's `NotFound` evidence | ⚠️ test-only |
| — | no question text in logs | 0 hits for a distinctive phrase from a sent question in the revision's logs | ✅ |

### Why control 5 fails — structural, not a lexicon omission

D2 fires on `marker + SUBJECT_TOKEN + ungrounded`. `SUBJECT_TOKENS` is the **technology lexicon**
(`typescript`, `python`, `perl`, …), so the predicate can only express *capability* claims
(“I have a strong foundation in TypeScript”). A commitment/interest claim contains no technology
token: `_marker_windows` finds the marker (`interested in working for`) but
`_subject_tokens_in(...)` returns `[]`, and the clause is kept — by design, see
`test_marker_without_subject_is_kept`.

Reproduced locally: *“I am interested in working for your company.”*, *“I want to work for your
company.”*, *“Yes, I’d be interested.”*, *“I would be interested in joining your team.”* are all
**kept** by the guard. The recorded probe passed because its answer carried a technology token in
a different clause — the string was covered, the class was not.

### Consequence

ADR-009 control 5 was reworded to “explicit first-person commitment/interest claims”. The shipped
guard covers **capability** over-claiming. Until that gap is closed — by extending the predicate to
commitment subjects, or by the owner rewording control 5 to the capability class with the residual
risk stated — **E3 (going public) stays blocked**.
