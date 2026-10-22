# E3 going public — runbook (flip, CORS, widget, usage)

**Date:** 2026-10-22 · **Project:** `janbot-deploy-2026-10` · **Region:** `europe-central2` ·
**Service:** `janbot-api` — `https://janbot-api-kafmnjtk3a-lm.a.run.app` ·
**Widget:** `https://jstavel.github.io/janbot/` (origin `https://jstavel.github.io`).

The flip is Terraform-owned: `allUsers` + `roles/run.invoker`, the
`JANBOT_CORS_ORIGINS` env (the ADR-008 allowance, Pages origin only, POST-only),
and the usage counters (`usage_<UTC date>` docs, fail-open, no IP, no text).
The widget is a static thin caller of `POST /chat` — no key, no build step.
The round ends at a **verified `terraform plan`; the owner runs the apply**
(E2 blast-radius rule).

## Pre-apply checks (both required, both one-time)

### 1. The org-policy IAM constraint can refuse `allUsers` even when `plan` is clean

`plan` is a dry-run of Terraform's own model; **org policies are evaluated by
the API at apply time**. Inspect the project's effective constraints first:

```sh
gcloud org-policies list --project janbot-deploy-2026-10
gcloud org-policies describe iam.allowedPolicyMemberDomains --project janbot-deploy-2026-10
gcloud projects describe janbot-deploy-2026-10 --format='value(parent)'
```

- **Empty list / no constraint named `iam.allowedPolicyMemberDomains`** (a
  personal project with no organization has none by default) → allowed.
- **A `describe` hit** (inherited from an org, or set on the project) → the
  binding may be refused; read the policy rules: `allowed_values` listing the
  org's domain id only would refuse `allUsers`/`allAuthenticatedUsers`.

**The definitive check is the attempt itself — made reversible** (the plan
sanctions this hand probe, but it must leave no grant behind: add, confirm,
remove):

```sh
gcloud run services add-iam-policy-binding janbot-api \
  --region europe-central2 --project janbot-deploy-2026-10 \
  --member allUsers --role roles/run.invoker \
&& echo 'add-iam-policy-binding: allUsers is allowed by org policy' \
&& gcloud run services remove-iam-policy-binding janbot-api \
  --region europe-central2 --project janbot-deploy-2026-10 \
  --member allUsers --role roles/run.invoker \
&& echo 'remove-iam-policy-binding: the service is private again'
```

- **Add succeeds and the removal confirms** → `allUsers` is allowed by the
  org policies; proceed to the formal apply.
- **Add fails** naming `constraints/iam.allowedPolicyMemberDomains` (or a
  neighbour: `iam.allowedPolicyMemberDomainsGroup` is the usual co-traveller)
  → **stop**. The flip needs an owner-side policy change or renegotiation;
  do not disable the constraint from the terminal.
- **The removal fails** → run it by hand again before anything else; do not
  proceed to the apply with a hand-granted binding still in place.

**The service becomes public only when the owner's `terraform apply` creates
the binding.** The probe grants and immediately revokes, so an aborted apply
cannot leave the service public with the grant recorded nowhere in Terraform
state — abort-safety is the point of the reversal.

**Observed (2026-10-22, read-only):** the project has **no parent
organization** and `orgpolicy.googleapis.com` is **not enabled** on it —
`gcloud org-policies list/describe` is refused with `SERVICE_DISABLED`. No
inherited org constraint can therefore refuse `allUsers`; the hand-attempt
probe above stays the definitive check.

### 2. Pages must be enabled with GitHub Actions as the source

One-time manual precondition — without it the first run of
`.github/workflows/pages.yml` fails confusingly in `configure-pages`:

Repo → **Settings → Pages → Build and deployment → Source: `GitHub Actions`**.
(If that UI path is blocked by plan limits for the repo, the first workflow
run's `enablement: true` in `configure-pages` performs it — the runbook's
precondition exists so the failure mode is never a mystery.)

## The flip

The image digest moves **because of the `src/**` trigger alone** (config, API
and the new usage module changed); the `corpus`, `cache`, `dataset` and
`Containerfile` triggers are untouched, so `build_cache` has nothing to refuse.
The build tree must be clean — commit first (`clean_build_tree` refuses an
otherwise-valid plan).

```sh
ulimit -n 16384 && uv run pytest -q     # the full suite stays green
terraform -chdir=terraform validate
terraform -chdir=terraform plan \
  -var image_tag=$(git rev-parse --short HEAD) \
  -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

**The verified plan shows exactly:**

| change | resource |
|---|---|
| 1 to add | `google_cloud_run_v2_service_iam_member.public_invoker` (`allUsers` + `roles/run.invoker`) |
| 1 to replace (rebuild) | `docker_registry_image.janbot` — the `src` trigger's new hash |
| 1 update in place | `google_cloud_run_v2_service.janbot` — new image digest + the `JANBOT_CORS_ORIGINS` env |
| 0 to destroy | — |

No other drift. Anything else in the plan is a finding, not a flip.

```sh
# owner runs the apply
terraform -chdir=terraform apply \
  -var image_tag=$(git rev-parse --short HEAD) \
  -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

The first request after the apply is a **cold start** (~8–23 s, E2's
measurement; `min_instances = 0` is an owner decision — a single post-deploy
request is not a latency measurement).

## Post-apply preflight probes

```sh
SERVICE_URL=$(terraform -chdir=terraform output -raw service_url)

# 1. allowed preflight → 200, `access-control-allow-origin: https://jstavel.github.io`
curl -is -X OPTIONS "$SERVICE_URL/chat" \
  -H 'Origin: https://jstavel.github.io' \
  -H 'Access-Control-Request-Method: POST'

# 2. refused origin → 400 `Disallowed CORS origin`, NO allow-origin header
curl -is -X OPTIONS "$SERVICE_URL/chat" \
  -H 'Origin: https://example.com' \
  -H 'Access-Control-Request-Method: POST'

# 3. refused method → 400 `Disallowed CORS method`, NO allow-origin header
curl -is -X OPTIONS "$SERVICE_URL/chat" \
  -H 'Origin: https://jstavel.github.io' \
  -H 'Access-Control-Request-Method: DELETE'

# 4. cross-origin POST → the response carries no allow-origin header
curl -is -X POST "$SERVICE_URL/chat" \
  -H 'Origin: https://example.com' -H 'content-type: application/json' \
  -d '{"question":"What search infrastructure have you built?"}'

# 5. widget-origin POST → 200 + the echoed origin (this is what the widget does)
curl -is -X POST "$SERVICE_URL/chat" \
  -H 'Origin: https://jstavel.github.io' -H 'content-type: application/json' \
  -d '{"question":"What search infrastructure have you built?"}'
```

## Widget end-to-end

Open `https://jstavel.github.io/janbot/` (wait for the first Pages run to go
green on `main` — the workflow fires on `widget/**` pushes):

| check | expected |
|---|---|
| ask a baked question | cached answer + `Cited sources:` line, no model call (a spent daily quota cannot break the demo) |
| ask an off-corpus question ("What is the weather tomorrow?") | the graceful-decline copy, no citations, no error styling |
| ask 2 500 characters | `422: question exceeds the maximum length of 2000 characters` |
| the page's network panel | exactly one `POST …/chat` per ask (plus one preflight), **no key anywhere** |
| page sources | no key, `POST` only; the service URL is the one hardcoded constant |

## Live acceptance — the guardrail layer re-proves on the public revision

Run from the widget and/or curl, then attribute from the logs (E2 lesson: use
`--format=json` — structured `decline` lines render as blank rows under
`textPayload`):

```sh
gcloud logging read \
  'resource.type=cloud_run_revision AND resource.labels.revision_name~"^janbot-api" \
   AND severity>=WARNING' \
  --project janbot-deploy-2026-10 --limit 50 --format=json
```

| # | probe | expected | attribution |
|---|---|---|---|
| 1 | 11 rapid requests from one IP | the N+1th is **429** `{"detail":"too many requests"}` | `{"event":"decline","component":"guardrail","cause":"rate_limited"}` |
| 2 | a 2 500-char question | **422** with the maximum-length detail | `cause=input-too-long`; no model call |
| 3 | a 9 KB body | **413** `request body too large` | `cause=body-too-large`; **not** in the usage counters (pre-route) |
| 4 | *"Are you interested in this role?"* | **answered** | Amendment 5 holds live on the public revision; no decline line |
| 5 | *"Would you like to work for our company?"* | **answered** | the accepted control-5 residual — served by definition |
| 6 | *"Can you start next month if we hire you?"* | **insufficient** | `cause=low-relevance` — θ, no model call (not a live guard decline) |
| 7 | cache-hit vs live-guard | a baked question answers in ~1 s with zero OpenRouter spend; a novel question takes ~7–23 s | the `usage_<date>` `served` doc counts both; only the novel one can log a decline |

**Honest scope of the flip:** unauthenticated means *any HTTP client* — CORS
constrains only which origins a browser lets read responses. The abuse controls
are the per-IP rate limit + global quota (ADR-009 control 7); that is why rows
1–3 must re-prove live.

## Guardrail tuning (round of 2026-10-22, parts 1–3)

Three flips ride one revision: the honest refusal header (`Retry-After`), the
rate default 10 → 20, and `startup_cpu_boost`. The verified plan for the round
shows **exactly**: 1 replace — `docker_registry_image.janbot` (the `src`
trigger's new hash: `limits.py` + `main.py` changed), 1 update in place —
`google_cloud_run_v2_service.janbot` (new digest + `JANBOT_RATE_LIMIT` 10 → 20 +
`startup_cpu_boost`), **0 destroy**. Anything else is a finding.

### Why the per-IP rate limit is 20 / 10 min (and what risk that carries)

A 12-request burst from one address produced a bare `429` (measured
2026-10-22): a corporate NAT shares one IP, so a whole office got ten questions
per window — anti-abuse at ten per office is a UX defect, not protection. The
**cost guard was never the per-IP window**: the global daily quota (500
model-call slots) plus the baked answer cache bound spend; the per-IP window
only bounds abuse rate. Raising it to 20 halves the false-refusal rate for a
shared address.

**Residual risk (recorded on purpose):** more model calls per office before
the daily quota bites — up to 20 un-cached calls per IP per 10 min, so one
office can spend ~2 880 quota slots/day at the theoretical max (20 × 144
windows); the 500/day quota is what actually stops the spend. No IP-less
identity (cookies/sessions) is introduced: a public endpoint without auth
cannot reliably identify a caller, and pretending otherwise would be worse
than an honest IP limit.

### The refusal now says when to come back

- A **rate** 429 carries `Retry-After` = seconds to the caller's next window
  boundary (the earliest moment a slot frees; two refusals in one window
  shrink the header — pinned by `test_two_refusals_in_one_window_shrink_the_header`).
- A **quota** 429 carries `Retry-After` = seconds to the next UTC midnight
  (the daily counter's reset point).
- A **503 store** error carries **no** `Retry-After` — a store error's
  recovery time is unknown, and a fabricated wait would be dishonest.
- `Retry-After` is not CORS-safelisted, so the 429 also carries
  `Access-Control-Expose-Headers: Retry-After`; without it the widget's
  cross-origin fetch would read `null` and render no wait.
- The `/chat` JSON schema is unchanged; the `detail` strings are byte-identical
  (the widget keys on them): `too many requests` → "Too many questions from
  this address — try again in about N minutes" (N = ceil(Retry-After/60));
  `the daily model-call quota is exhausted` → the daily-limit copy.
  413/422/5xx keep the raw `status + ": " + detail` rendering.

### Cold-start re-measure (after the owner's apply)

`startup_cpu_boost = true` is free but only observable post-apply. Measure the
**cold** path, not the warm one:

1. Wait ≥ 15 minutes after the last request (Cloud Run scales to 0; a warm
   instance would silently invalidate the measurement).
2. Time exactly one request against a **baked** question (cache hit — no model
   call, so the number isolates the cold start):

```sh
SERVICE_URL=$(terraform -chdir=terraform output -raw service_url)
curl -sS -o /dev/null -w '%{time_total}\n' -X POST "$SERVICE_URL/chat" \
  -H 'content-type: application/json' \
  -d '{"question":"What search infrastructure have you built?"}'
```

3. Record it below, next to the pre-flip numbers. One request is an anecdote;
   if the number looks off, repeat the cold wait once before concluding.

**Measured:** pre-flip cold start ~50 s (owner, 2026-10-22, before this
round); post-apply (with `startup_cpu_boost`): *pending the owner's apply —
record the number here*.

Note: the live-acceptance row-1 probe above ("11 rapid requests") was written
at rate 10; with the new default the N+1th refusal is the **21st** request in
the window.

## Usage visibility (no redeploy)

```sh
JANBOT_FIRESTORE_PROJECT=janbot-deploy-2026-10 JANBOT_FIRESTORE_DATABASE=janbot \
  uv run python -m janbot.guardrails.usage --date 2026-10-23
JANBOT_FIRESTORE_PROJECT=janbot-deploy-2026-10 JANBOT_FIRESTORE_DATABASE=janbot \
  uv run python -m janbot.guardrails.usage --days 7
```

Prints `served` / `declined` per UTC date; a missing day reads `0 0`. Reading
needs only ADC — no service dependency, no deploy. **No document records an IP
or any question/answer text** — the counter is called with the outcome class
only; `tests/test_usage.py::test_record_methods_take_no_ip_or_text` pins it.

Reconciliation, so the totals are not misread: `served + declined` counts only
requests the `/chat` route itself resolved. It excludes the pre-route
body-limit refusals (413/400 — they stay in the decline log), FastAPI's own
pre-handler 422s (a blank, mistyped or malformed body never reaches the
handler), 405s for non-POST methods on `/chat`, `/health` hits, and 5xx. The
`quota_<date>` doc undercounts relative to it: cache hits, input-bounds
refusals, rate refusals and store errors never reach the quota check.

## Known pitfalls (verified during the E3 apply, 2026-10-22)

### The Artifact Registry push auth is a short-lived token, not a stored credential

The `docker_registry_image.janbot` build pushes through the podman socket
(`DOCKER_HOST=unix:///run/user/1000/podman/podman.sock`). The push fails with
a bare `500 (Internal Server Error)` when the registry credentials the client
hands the daemon have expired, and the error names nothing — the symptom hides
the cause. Two independent credential paths are in play:

- a manual `podman push` reads `~/.config/containers/auth.json` (`podman login`);
- the Terraform docker provider reads `~/.docker/config.json` and forwards the
  credentials as the request's `X-Registry-Auth` header — the podman compat
  push endpoint trusts that header, not the local authfile.

Both must be refreshed before any apply that rebuilds the image:

```sh
TOKEN=$(gcloud auth print-access-token)   # expires in ~1 hour
printf 'oauth2accesstoken:%s' "$TOKEN" | base64 -w0 > /tmp/ar.b64
# refresh ~/.docker/config.json auths entry for europe-central2-docker.pkg.dev
```

Diagnosing this cost one apply attempt that read as a registry outage and was
actually credential expiry. A future improvement (not done here): bake a
credential helper (`gcloud auth configure-docker` writes a helper entry) so
the refresh is automatic.

### CORS is a browser read-back policy, not an access control — the IP gate is the limiter

State it explicitly, because it is easy to misread what the allowance defends.
CORS checks **only the `Origin` header value**; it never inspects the caller's
IP and cannot — any non-browser client (`curl`, a script, another server) sends
an arbitrary `Origin` and the server cannot tell forgery from truth. Verified
during live acceptance: a forged `Origin: https://jstavel.github.io` POST from
`curl` was answered `200`. Therefore:

- `JANBOT_CORS_ORIGINS` defends against **browser drive-by** — a page the
  visitor opens cannot silently make the browser call `/chat` cross-origin
  (the failed preflight stops the request before it is sent) and cannot read
  the response.
- It does **not** defend the endpoint itself: with `allUsers` ingress,
  `POST /chat` is reachable by any client on the internet regardless of origin.
- The actual per-IP perimeter is `FirestoreLimits` (rate window keyed on the
  last trusted `X-Forwarded-For` hop) plus the global daily quota. CORS never
  substitutes for them, and they never rely on CORS.

## Rollback

A Terraform change, never a console flip: revert the commit (or remove the IAM
resource and set `cors_origins = ""`), then plan/apply. Removing
`google_cloud_run_v2_service_iam_member.public_invoker` deletes the `allUsers`
binding **immediately — no new revision is needed for the IAM change**. An
empty `cors_origins` leaves the env present but **blank**, which the config
reads as unset, so the CORS middleware is absent on the next revision.
