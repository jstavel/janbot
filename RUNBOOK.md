# RUNBOOK — how to run JanBot

**Scope:** the single source for **how**. What and why live in [`_bmad-output/`](_bmad-output/)
(ADRs, specs, plans); which decisions bind lives in [`DECISIONS.md`](DECISIONS.md) (a derived
index over the ADRs); the stack procedure lives in [`terraform/RUNBOOK.md`](terraform/RUNBOOK.md)
and is **linked, never copied** — two copies of the deploy steps drift, and then there are two
authorities for one command.

**Verified by running it.** A line here that does not work is a bug in this file, not a
detail to route around. It is written for the agent first and the human second: an agent
starts every session from zero, so nothing here may depend on a chat history.

## 0. What you need

- [`uv`](https://docs.astral.sh/uv/) — Python 3.12 comes from `.python-version`.
- For the container path: `podman` with `podman.socket` (the Terraform docker provider talks
  Docker API to it — see `terraform/RUNBOOK.md` §Preflight).
- For deploy: `gcloud` authenticated against the project that owns the stack
  (`janbot-deploy-2026-10`) and `terraform`. **The state was created by Terraform 1.15**; do
  not point OpenTofu at it without a read-only `plan` first.

## 1. Local run

```sh
uv sync
uv run uvicorn janbot.api.main:app --reload
curl -s localhost:8000/health     # {"status":"ok"}
```

The default `JANBOT_MODEL_MODE=eval` uses the locked deterministic snapshot and needs no key;
it cannot reach the network. `production` needs `OPENROUTER_API_KEY`. Every knob is in
[`README.md` §Configuration](README.md) — this file does not repeat the table.

## 2. Tests

```sh
uv run pytest -q
```

The suite closes its per-test resources — an autouse release fixture in
[`tests/conftest.py`](tests/conftest.py) stops the chroma systems and disposes the
mlflow engines each test created — so the default file-descriptor limit is enough.
The old `ulimit -n 16384` wrapper existed to mask a resource leak, not to fix one;
do not reintroduce it. Do not pin a pass count here — it changes with every story;
the criterion is **green**.

## 3. Index

`chroma_db/` is not committed and the image bakes its own index, so a local rebuild is a
diagnostic, not a deploy step.

```sh
uv run python -m janbot.ingest                 # public_profile_org/ -> chroma_db/
```

Identity must be **path-independent** — two builds and a build from a copy of the corpus at
another path must agree:

```sh
uv run python -m janbot.ingest --index /tmp/index-a
uv run python -m janbot.ingest --index /tmp/index-b
diff -u /tmp/index-a/index-identity.json /tmp/index-b/index-identity.json
```

The identity the current corpus produces is `b36feac2…`, 417 chunks, model
`all-MiniLM-L6-v2@913d7300…`. To check the **deployed** artefact rather than a local build,
read the file out of the image:

```sh
podman run --rm --entrypoint python3 \
  europe-central2-docker.pkg.dev/janbot-deploy-2026-10/janbot/api:<tag> \
  -c "print(open('/app/index/index-identity.json').read())"
```

## 4. Answer cache

The cache is a **baked build input** — real model output recorded from a production run, not
the golden `expected_answer`. The image build **fails** when the dataset sha or the corpus
tree sha no longer matches the artifact, so a corpus or dataset change is not a silent drift;
it is a required regeneration.

```sh
JANBOT_MODEL_MODE=production JANBOT_RETRIEVAL_MODE=hybrid JANBOT_RETRIEVAL_WINDOW=chunks \
JANBOT_TOP_K=4 JANBOT_RELEVANCE_THRESHOLD=0.26 JANBOT_OUTPUT_GUARD=on \
uv run python -m janbot.eval --split val --cache-out cache/answers-<run>.json
```

Needs `OPENROUTER_API_KEY` (used for this run only, never at build time). Refusals are
deliberately **not** cached — they are decided before the model call, and caching them would
freeze the reason heuristic.

## 5. Deploy

```sh
terraform -chdir=terraform plan  -var image_tag=$(git rev-parse --short HEAD) -var registry_auth_file="$DOCKER_CONFIG/config.json"
terraform -chdir=terraform apply -var image_tag=$(git rev-parse --short HEAD) -var registry_auth_file="$DOCKER_CONFIG/config.json"
```

Full procedure — registry-auth setup, the two-apply ordering, secret rotation, destroy
caveats, base-image bumps: **[`terraform/RUNBOOK.md`](terraform/RUNBOOK.md)**. Three things
to know before starting: the image is built **from the working tree** (the plan refuses a
dirty `src/`, `public_profile_org/`, `cache/`, `Containerfile`, `pyproject.toml`, `uv.lock`,
`.dockerignore`); the tag is the commit sha; the deployed reference is the **digest**.

> Never pipe a terraform command into `head`/`tail`. Closing stdout kills the process
> mid-run and leaves a state lock behind — see the trap recorded in `terraform/RUNBOOK.md`.

## 6. Live check — after every deploy

Since the E3 flip (ADR-008), `GET /health` and `POST /chat` are
**unauthenticated** — no identity token is needed. Browser calls are allowed
only from the Pages origin `https://jstavel.github.io` (`JANBOT_CORS_ORIGINS`;
the `allUsers` `roles/run.invoker` grant is Terraform-owned). Before the flip
is applied the service is authenticated-only and the calls below need
`Authorization: Bearer $(gcloud auth print-identity-token)`.

```sh
URL=$(terraform -chdir=terraform output -raw service_url)

curl -s -o /dev/null -w '%{http_code}\n' "$URL/health"

curl -s -X POST "$URL/chat" \
  -H 'content-type: application/json' \
  -d '{"question":"Are you interested in this role?"}'
```

Expect `status=answered` with one citation, and **no decline line** in the logs.

Decline causes are structured log fields, deliberately carrying no question or answer text:

```sh
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="janbot-api"' \
  --limit=50 --format=json --freshness=15m \
| python3 -c "import sys,json;[print(e['timestamp'], e.get('jsonPayload') or e.get('textPayload','')[:80]) for e in json.load(sys.stdin)]"
```

**Do not** use `--format="value(timestamp,textPayload,jsonPayload.message)"`: the decline
event has no `message` field, so it renders as a blank line and a real decline reads as "no
decline". This produced a false negative on 2026-10-21 before it was caught.

**Read an absence only after a control has spoken.** Pair the answered question with one that
must decline (an out-of-corpus question → `cause=low-relevance`); if the control emits its
line in the same revision, the instrument is live and the missing line on the first question
means something.

Counters: Firestore database `janbot` in `janbot-deploy-2026-10`, collection
`janbot_guardrails` — `rate_<hashed ip>` and `quota_<date>`.

## 7. Rollback

Cloud Run keeps the previous revisions; Artifact Registry keeps the 5 newest image versions or
30 days, whichever horizon is longer. Force a new revision after a secret change, and the
protection-lift procedure: `terraform/RUNBOOK.md`.

```sh
gcloud run revisions list --service janbot-api --region europe-central2
gcloud run services update-traffic janbot-api --region europe-central2 --to-revisions <revision>=100
```

## 8. Traps, measured

| trap | what it looks like | what to do |
|---|---|---|
| cold start | first request after a deploy takes 20+ s (instance boot ~8 s measured on `00008`) | do not read a single post-deploy request as steady-state latency |
| `reason` vs `cause` | the API says `reason=personal`, the log says `cause=low-relevance` | `reason` is the question class, `cause` is the mechanism that fired — read the log |
| file descriptors | the full suite fails in the store tests only | the per-test chroma/mlflow release fixture in [`tests/conftest.py`](tests/conftest.py) closes this (2026-10-22: measured 1021 → 26 fds at session end under `ulimit -n 1024`, suite green). A reappearance is a regression in that fixture — do not raise the limit |
| stale state lock | `Error acquiring the state lock` after an interrupted command | confirm no terraform is running, then `terraform force-unlock <ID>` |
| dirty build tree | `plan` fails on the dirty-build-tree precondition | commit or stash — the image is built from the working tree, not a commit |
| Containerfile touched by a docs change | `plan` wants `1 to add, 1 to change, 1 to destroy` although no code changed — `triggers.containerfile` hashes the **file**, comments included | expected: the next `apply` rebuilds an identical-behaviour image (~3 min, new digest, new revision). Measured 2026-10-21: a single comment edit moved the trigger `a36e324b…` → `b880f5b7…`. If a rebuild must not happen, don't edit `Containerfile` in a docs commit — fix the reference in the same commit as the next real deploy |
| image tag after a rebase merge | the deployed tag is a branch commit (`api:1aded50`) while `main` carries rewritten SHAs (`569cf4d`) | the tag records the **build input**, and the build inputs are hashed: prove the tree with `git diff <tagged sha> <main sha> --stat` (empty = same tree), and cite the `main` SHA in documentation — see [README §Merging](README.md) |

## 9. What this file does not cover

Evaluation runs, dataset splits, the optimization gate and the pre-registered rule live in
[`README.md` §Evaluation](README.md) and `_bmad-output/initiative-janbot/epic-evaluation/`.
The guardrail controls, their measured coverage and the live-acceptance records live in
`_bmad-output/initiative-janbot/epic-gcp-deploy/run-e2-guardrails.md`.
