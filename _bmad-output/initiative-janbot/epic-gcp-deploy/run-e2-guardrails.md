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
| 5 | Over-claiming guard | ADR-010 inside `ChatProgram.forward`; **narrowed** actionable/company class (ADR-010 Amendment 4) | `probe_over_claiming-e2-output.txt`; `tests/test_output_guard_commitment.py` |
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

## Embedding model and index identity

The baked index's embedder is **pinned and verified at build** — verification, not
hermeticity: the build still downloads the ~79 MB ONNX archive from S3 (with a short
retry for transient failures) and fails on a sha mismatch or persistent failure.
Vendoring the archive would be the hermetic variant; it is not done.

- model `all-MiniLM-L6-v2`, sha256 `913d7300ceae3b2dbc2c50d1de4baacab4be7b9380491c27fab7418616a16ec3`;
- build step `python -m janbot.store.embedding_model` asserts the installed Chroma provider uses that model/sha, warms the download with a short retry for transient network failures, re-verifies the archive sha, and **fails the build on a mismatch or persistent failure**;
- `python -m janbot.ingest` writes `index-identity.json` beside the index: model identity, chunk count and a sha256 over the sorted chunk ids, documents and embeddings.

**Identity is corpus-root-relative (2026-10-21 close-out, round 2).** The first identity
scheme hashed the **absolute** source path, so the digest covered (path, content): the
deployed image (`janbot-api-00007-xjj`) reported `b6b19fe7…` while a local build of the
same commit reported `a785a786…` — same 417 chunks, and not an embedding-model effect
(deleting and re-extracting the model from the verified archive left the local hash
unchanged). "Two clean local builds produced the same identity" therefore verified one
path context and said nothing about the deployed artefact. `_chunk_id` now hashes the
source **relative to the corpus root**, so ids and the identity are machine-independent
and indices are portable; `source_path` metadata stays absolute (the scope checks and
the citation rewriter are unchanged).

**Reproducibility check (2026-10-21, after the fix):** the repo build and a build from a
copy of the corpus at a different filesystem path produce the **identical** identity file —
`index_identity=b36feac29ae7aa1991900b149e78438ddde8a42ad4574f328ef4dcfedab6b49a`,
417 chunks, model `all-MiniLM-L6-v2@913d7300…`. The next image build must report this
same value. Historical numbers, kept and marked: local `a785a786…` and image `b6b19fe7…`
— both products of the path-dependent pre-fix scheme.

**What the id change invalidates:** the stored chunk ids and `index-identity.json`
(rebuilt by the same build step); nothing else consumes ids — citations use
corpus-relative source labels, and the answer cache is keyed by question text. Retrieval
was **measured, not assumed**: the golden val retrieval on the rebuilt index is
`retrieval_accuracy` **34/49 = 0.6939**, `retrieval_mrr` **0.7415** — identical to the
pre-change measurement on the same commit (same procedure, same 49-item eligible
population), with not one item's miss set or MRR rank changed. No re-baseline is
triggered.

**Reference retrieval:** unchanged on the pinned index — `retrieval_accuracy` **34/49 = 0.6939**, `retrieval_mrr` **0.7415**, matching the reference `156b5d1a`/`5ed5d8d7`.

**The 0.2604 observation:** on the pinned index the top-two similarities for *“Would you like to work for our company?”* are **0.260422 / 0.252066**. The θ gate declines only when **both** are below 0.26, so this question is **not** a θ decline on this index. On the live revision the decline causes are **attributable from the logs** (next section): on `00007`, `low-relevance` (θ, no model call) and `commitment-claim` (after a model call) were both observed. The earlier sentence attributing the `00006` decline to "another control" was an inference from a local index on an image built before the pin; the 00007 log facts supersede it.

## Decline attribution

Every production decline emits one JSON line at WARNING, with no question text, answer text, citation labels or key:

```json
{"event":"decline","component":"program","cause":"low-relevance"}
{"event":"decline","component":"program","cause":"commitment-claim"}
{"event":"decline","component":"guardrail","cause":"rate_limited"}
```

- **`component=program`:** `empty-retrieval`, `low-relevance`, `uncited`, `D1-all-invalid`, `commitment-claim`, `guard-error`, `D2-empty`, `D1`.
- **`component=guardrail`:** `rate_limited`, `quota_exceeded`, `store_error`, `input-too-long`, `body-too-large`, `invalid-content-length`.

The `/chat` contract is unchanged; the cause is only in the logs. `tests/test_api_decline_logging.py` captures both a θ decline and a guard decline and fails if the question, a test token or key text appears.

**Live check after the apply:** one θ decline (e.g. a personal/out-of-corpus question) must log `cause=low-relevance`; one guard decline (e.g. a commitment/uncited answer) must log the guard rule. Scan the log line for the cause only; no text.

## Live check — `janbot-api-00007-xjj` (2026-10-21, second round)

Authenticated run; image `sha256:23e9db40…`; the service was left authenticated-only.
Decline causes from the logs — no question or answer text is logged:

| time (UTC) | question class | cause | latency | attribution |
|---|---|---|---|---|
| 11:36:06 | off-corpus (weather) | `low-relevance` | ~8 s | θ, no model call — **first request after deploy: cold start** |
| 11:36:13 | role interest — *“Are you interested in this role?”* | `commitment-claim` | 6.9 s | guard, after a model call — **false positive**, see Amendment 5 |
| 11:36:23 | actionable — *“Can you start next month?”* | `commitment-claim` | 10.7 s | guard, after a model call — desired |
| 11:36:53 | nonsense | `low-relevance` | 0.95 s | θ, no model call |

Both decline classes are attributable from the log alone: `low-relevance` (θ, no model
call) and `commitment-claim` (after a model call). The role-interest row is a false
positive against ADR-010 Amendment 4's own served list — fixed as **Amendment 5**
(below) and re-checked on the next revision; the re-check is recorded in the next section
(`00008`, verified).

**Cold start (measured; input to the E3 `min-instances` decision):** the first request
after deploy took **~8 s**; later requests ranged **0.95–10.7 s** depending on whether a
model call happened (θ declines sit at the low end). The owner decides `min-instances`;
this record carries the measurement.

## Live check — `janbot-api-00008-86p` (2026-10-21, third round — Amendment 5 verified)

Applied 13:22 UTC by Goose, independently of the builder, from `1aded50`, which was merged
into `main` as `569cf4d`; `git diff 1aded50 569cf4d` is empty, so the tree that was built is
the tree on `main`. Image `…/api@sha256:65357cc7…`, tag `api:1aded50`. The plan replaced the
image on the **`src` trigger alone** (`0e052498…` → `51fe27a8…`); the `cache`, `corpus` and
`dataset` triggers were unchanged, so `build_cache` had nothing to refuse.

**Index identity, read out of the built image** (`podman run --rm --entrypoint python3
…:1aded50`, reading `/app/index/index-identity.json`): `b36feac29ae7aa1991900b149e78438ddde8a42ad4574f328ef4dcfedab6b49a`,
417 chunks, `all-MiniLM-L6-v2@913d7300…`. That is the path-independent value the round-2 fix
predicted — now confirmed **in the deployed artefact**, which is the claim the pre-fix
scheme could not make.

| time (UTC) | question | reply | log line | latency | reading |
|---|---|---|---|---|---|
| 13:23:51 | *"Are you interested in this role?"* | **answered**, `spec-first-pitch.org` | *none* | 21.8 s | **Amendment 5 holds live**: the exact case that logged `commitment-claim` on `00007` is served |
| 13:44:13 | *"Would you like to work for our company?"* — control 5's original failing case | **answered**, `core-values-vs-framework.org` | *none* | 22.7 s | served; residual stated below |
| 13:24:25 | *"Can you start next month if we hire you?"* | `insufficient` (out_of_corpus) | `cause=low-relevance` | 1.3 s | θ declined pre-LM — **not** a live `commitment-claim` |
| 13:24:26 | *"What is the weather in Brno tomorrow?"* | `insufficient` (out_of_corpus) | `cause=low-relevance` | 0.9 s | θ, no model call |
| 13:44:15 | *"Can you relocate to Munich and start in January?"* | `insufficient` (personal) | `cause=low-relevance` | 1.2 s | θ again |

**The instrument was proven before its silence was read:** two of the five questions emitted
a `decline` line in this revision, the two answered questions emitted none. An absent decline
line therefore means "no decline", not "logging was off".

**Three honest limits, so the narrowing is not mistaken for coverage:**

1. **No live post-LM `commitment-claim` decline on this revision.** All three declined
   questions were stopped by θ before any model call. The run proves the guard no longer
   fires on role- and workplace-generic interest; it does **not** re-prove in production that
   an actionable commitment is caught — that evidence stays `00007`, plus
   `tests/test_output_guard_commitment.py` and the coverage probes. The actionable phrasings
   tried here fall below θ on this index, so they never reach the guard.
2. **The residual, plainly.** *"Would you like to work for our company?"* is answered:
   *"Yes. I'm interested in working somewhere that values freedom, commitment, courage, and
   accountability — and where those values are practiced by people, not just written into a
   framework."* Under Amendments 4–5 that is the **served** class — generic enthusiasm, no
   party attribution, nothing a recruiter could act on — and it is the same string the `00005`
   acceptance recorded as ❌ FAILS. Both statements are true: served by the current
   definition, and still readable as first-person interest. The owner accepted that residual
   when the control was narrowed; it is repeated here so the two verdicts are not confused
   later.
3. **`reason` is not `cause`.** The response `reason` (`personal` / `out_of_corpus`) is a
   heuristic over the **question text** (`src/janbot/api/decline.py`); the log `cause` is the
   **mechanism** that fired. *"Can you relocate to Munich and start in January?"* returned
   `reason=personal` while the mechanism was θ `low-relevance`. Read the log when the
   question is which control stopped it.

**Found by executing — both belong in a runbook, not only here:**

- **Decline lines are structured `jsonPayload` with no `message` field.**
  `--format="value(timestamp,severity,textPayload,jsonPayload.message)"` renders them as
  **blank lines**, so a check built on it silently reports "no decline" for a request that
  did decline. Use `--format=json` or `--format="value(timestamp,jsonPayload.cause)"`. This
  produced a false negative during this run before it was caught.
- **The first request after a deploy is a cold start:** 21.8 s and 22.7 s here against 6.9 s
  for the same class on a warm `00007`; the instance boot alone measured ~8 s (autoscaling
  13:43:51 → ready 13:43:59). A single post-deploy request is not a steady-state latency
  measurement.

**Other evidence from the same revision:** the Firestore `janbot` counters moved
(`rate_40e739e1…` `count=3`; `quota_2026-10-21` `count=15` at 13:24:25) — the guardrail layer
runs in this revision; zero log hits for the distinctive phrases of the five questions — no
question or answer text leaves the process; the post-apply `terraform plan` reports
`0 to add, 1 to change, 0 to destroy`, the single change being the known cosmetic `scaling`
block (`manual_instance_count`), with no image or env drift.

**Verdict:** Amendment 5 is verified live on the deployed revision. Control 5's remaining
exposure is the accepted residual in (2), not a regression.

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

## Commitment control — narrowed to actionable commitments (ADR-010 Amendment 4, 2026-10-21)

Three iterations grew the same shape (string → hand battery → generated sweep → foreign
vocabulary) and a vocabulary written outside the implementation still refused only **14/64**
cases (**78% leak**); iteration 1 refused **5/12**, and **8/8** implication-only forms remain
uncovered. The live failure on `janbot-api-00005-xqs` — *“Yes, I’d be interested.”* — is a
polite answer to a direct recruiter question: **the product working, not a defect**. The
control is narrowed rather than chased.

**Protected (best-effort):**

- **Actionable commitments on Jan’s behalf:** availability, start date / notice period,
  compensation expectations, accepting an offer, willingness to relocate or travel —
  anything a recruiter could reasonably act on as a decision Jan made.
- **Interest attributed to the prospect’s company:** a claim about a relationship with that
  company (named or deictic) that the corpus does not support.

**Out of scope and served:** generic enthusiasm or politeness in answer to a direct question
(*“Yes, I’d be interested.”*, *“Sounds great.”*, *“I’d be glad to talk.”*), topic interest
(*“trading systems”*, *“what you do”*) and role interest (*“the role”*). The live
`00005` answer is served.

**Measured coverage (probes in `tests/test_output_guard_coverage.py`):**

| category | covered | probes |
|---|---|---|
| availability / start / notice | **3/3** | “available immediately”, “can start next month”, “notice period is two months” |
| accepting an offer | **1/1** | “I accept the offer” |
| relocation | **1/1** | “willing to relocate” |
| compensation | **1/5** | caught: “salary expectation is 120k”; missed: “would accept 100k CZK gross”, “need at least 90k”, “expected compensation is 120k”, “expect 100k gross” |
| travel | **3/5** | caught: “willing to travel”, “can travel”, “able to travel”; missed: “happy to travel two days a week”, “can commute to Brno once a week” |

**Residual:** compensation (4/5 missed) and travel (2/5 missed) are best-effort gaps,
not claims of coverage. Reopen the vocabulary only if a live acceptance shows a
recruiter could act on one of the missed forms; otherwise no synonym chase.

**Kept, not weakened:** D1/D2 capability over `SUBJECT_TOKENS`, grounded commitments, the
Clojure control, grounded capability and values.

**Tests:** `tests/test_output_guard_commitment.py` generates the actionable/company products
and the named-company cells, pins the out-of-scope served cases and counts the residual. The
generated products are a **regression of the published axes, not proof of the class**: a
sweep generated from the implementation’s own axes cannot fail (it tests cross-product
completeness). The acceptance record below is the independent measurement, not the sweep.

**Residual, with numbers:** **5/12** (iteration 1), **14/64** on foreign vocabulary
(iterations 2/3; 78% leak), **8/8** implication-only. The predicate remains a
marker/reference vocabulary and cannot be complete; coverage is **best-effort by owner
decision**. The layer is re-checked live on the **next revision** against the narrowed cases.

### Amendment 5 (2026-10-21) — role interest is served; the named-company detector stops reading non-companies

**Evidence.** On `janbot-api-00007-xjj`, *“Are you interested in this role?”* produced a
model call (6.9 s) and was declined with `cause=commitment-claim`, although Amendment 4
lists role interest as served. Reproduced locally under the same production routing
(`openrouter/auto`): the answer *“… I'm especially interested in applying an architect's
mindset to AI-assisted workflows …”* trips the predicate because the named-company
detector reads **“AI-assisted”** as the prospect's company — the interest is attached to
the role/topic, not to any party, and the prospect's company is never mentioned. The
same live answers also contained “VPN”, “Layer 3” and “IPsec”, which the detector would
likewise have counted as companies.

**Intent.** The distinction is **what the interest is attached to**, not whether the
sentence is first-person: interest attributed to a **role/position** is served; interest
attributed to a **company/team/party** stays covered; actionable commitments stay
covered. *“I'd be interested in working with you”* and *“I'd love to join your team”*
remain caught — that is party attribution.

**Fix (data, not axes).** The non-company lexicon gained: the evidenced technology
tokens (`ai` — with a leading-word prefix check so “AI-assisted”/“AI-driven” resolve to
their stem — `vpn`, `ipsec`, `layer`), AI vendors/tools that cannot be the prospect
(`openai`, `anthropic`, `gemini`, `chatgpt`, `claude`), cities/regions (`prague`,
`brno`, `czech`, `czechia`, `warsaw`, `europe`), and sentence-initial discourse/courtesy
words (“Certainly”, “Absolutely”, “Glad”, …) that open answers before a first-person
statement. Real company names (Red Hat, Kraken) stay eligible. The reference and
predicate lists are unchanged; role/position has not been a party reference since
Amendment 4. Lexicon `2026-10-21.2`.

**Sweep-cell accounting.** **Zero cells removed.** Every actionable, company-reference
and named-company product keeps its expected outcome
(`tests/test_output_guard_commitment.py` passes unchanged); the new cases are additions
— the reproduced live answer, role-interest forms with pseudo-companies, and the
party-attribution red lines. The change is in the exclusion data, not in the swept
axes, so nothing was weakened to make the false positive pass.

**Measured coverage (probes in `tests/test_output_guard_coverage.py`), full table:**

| category | covered | probes |
|---|---|---|
| availability / start / notice | **3/3** | “available immediately”, “can start next month”, “notice period is two months” |
| accepting an offer | **1/1** | “I accept the offer” |
| relocation | **1/1** | “willing to relocate” |
| compensation | **1/5** | caught: “salary expectation is 120k”; missed: “would accept 100k CZK gross”, “need at least 90k”, “expected compensation is 120k”, “expect 100k gross” |
| travel | **3/5** | caught: “willing to travel”, “can travel”, “able to travel”; missed: “happy to travel two days a week”, “can commute to Brno once a week” |
| interest — role-attributed | **0/3 declined (all served)** | “Yes, I'm interested in this role.”; “…applying an architect's mindset to AI-assisted workflows.”; “Certainly, I'm interested in the role in Prague.” |
| interest — party-attributed | **3/3** | “I'd be interested in working with you.”, “I'd love to join your team.”, “I'm interested in Kraken.” |

**Residual (unchanged by this amendment):** a clause that mixes role interest with a
genuine party reference (“…interested in this role and in what your team does”) stays
covered — fail-closed; the guard is a floor, not a semantic judge.

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
python -m janbot.store.embedding_model
python -m janbot.ingest --index /tmp/index-a && python -m janbot.ingest --index /tmp/index-b
diff -u /tmp/index-a/index-identity.json /tmp/index-b/index-identity.json
# path independence: a corpus copy at a different filesystem location must give the same identity
rm -rf /tmp/other-place && mkdir -p /tmp/other-place && cp -r public_profile_org /tmp/other-place/corpus
python - <<'PY'
import sys; sys.path.insert(0, "src")
from janbot.ingest import index_corpus
index_corpus("/tmp/other-place/corpus", "/tmp/index-crosspath")
PY
diff -u /tmp/index-a/index-identity.json /tmp/index-crosspath/index-identity.json
JANBOT_MODEL_MODE=eval uv run python _bmad-output/initiative-janbot/epic-gcp-deploy/probe_over_claiming.py
terraform -chdir=terraform validate && terraform -chdir=terraform plan
python -m janbot.guardrails.build_cache \
  --source cache/answers-fc430d3e17714457b896bafdac9cc1ac.json \
  --out /tmp/answers.json
```

A live θ decline and a live guard decline must be attributable from the logs (`{"event":"decline","component":"program","cause":"low-relevance"}` / the guard rule), with no text content. `tests/test_api_decline_logging.py` pins the invariant.

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
