# Terraform core (M4/E1.5) — runbook

Owner decision **option (c)**: **Terraform owns the whole stack, including the container
image** — build + push happen inside `terraform apply`. One graph, one apply; the image is
referenced by **digest**, never a tag. Reversal is one line
(`lifecycle { ignore_changes = [template[0].containers[0].image] }`) — this is not permanent.

## Preflight (the usual failure point)

A running engine reachable by the `kreuzwerker/docker` provider, and registry credentials
known **to the provider**.

**Finding (build, 2026-10-16):** the `kreuzwerker/docker` provider resolves registry auth
**only from a `registry_auth` block** — it does *not* read the host Docker config on its own
(verified in provider source `internal/provider/provider.go`; the debug shows
`provider.AuthConfigs` is nil without a block). So `main.tf` declares:

```hcl
provider "docker" {
  registry_auth {
    address     = "europe-central2-docker.pkg.dev"
    config_file = "~/.docker/config.json"   # a PATH, not a secret
  }
}
```

The block contains **no secret** — only the path to a client-side config file — so the token
stays out of Terraform config and state (provider config is not persisted to state). Write
the credential into that file from a short-lived `gcloud` token (Docker-format `auths`, which
the provider parses via its `config_file` path):

```sh
systemctl --user enable --now podman.socket
export DOCKER_HOST=unix:///run/user/1000/podman/podman.sock

python3 - <<'PY'
import json, base64, subprocess, os
p = os.path.expanduser("~/.docker/config.json")
tok = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
json.dump({"auths": {"europe-central2-docker.pkg.dev":
  {"auth": base64.b64encode(("oauth2accesstoken:" + tok).encode()).decode()}}},
  open(p, "w"))
os.chmod(p, 0o600)
PY
```

(A `podman login --authfile ~/.docker/config.json` writes a non-Docker-format file the
provider cannot parse, so this scripted `auths` entry is used instead.)

## Backend (bootstrapped once by hand — Terraform cannot create its own backend)

```sh
gcloud storage buckets create gs://janbot-tfstate-436042949490 \
  --location=europe-central2 --uniform-bucket-level-access
gcloud storage buckets update gs://janbot-tfstate-436042949490 --versioning
```

Remote state, **object versioning on**. `.gitignore` excludes `*.tfstate*`, `.terraform/`,
value-bearing `*.tfvars`; **`.terraform.lock.hcl` is committed** (pins provider versions).

## Deploy (one graph; two applies because the secret version is out-of-band)

```sh
cd terraform
terraform init
terraform apply -var image_tag=$(git rev-parse --short HEAD)
```

This **builds** `../Containerfile`, **pushes** `…/janbot/api:<tag>`, creates the Artifact
Registry repo (with cleanup policies), the **secret container**, the least-privilege
`janbot-run` SA + its `secretAccessor`, and the Cloud Run service (by `@sha256` digest). The
`triggers` hash only `src/**`, `public_profile_org/**` and the `Containerfile` (deterministic;
`__pycache__`/`*.pyc` excluded).

**Ordering (settled at build):** Cloud Run references the secret **version** `latest`, which
the out-of-band step adds *after* Terraform creates the container — so the **first** apply
creates the base resources and fails at Cloud Run (`version … was not found`); add the
version, then apply again:

```sh
printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-
terraform apply -var image_tag=$(git rev-parse --short HEAD)
```

## Known issues (build, 2026-10-16)

- **Scaling drift (google provider 6.50.0):** the Cloud Run v2 API returns
  `manual_instance_count` (and `min_instance_count: 0`) inside `scaling`, which the schema
  cannot set, so `terraform plan` always shows `0 to add, 1 to change` for the service even
  though nothing real changes. `max_instance_count = 2` is applied; the phantom change is
  cosmetic. Follow-up: pin a provider version that fixes it, or accept the plan noise.
- **URL is deterministic:** recreating `janbot-api` in the same project+region yields the
  **same** URL (`https://janbot-api-kafmnjtk3a-lm.a.run.app`), so the E1 log's URL is *not*
  historical — contrary to the plan's expectation.
- A brand-new secret version can take a few seconds to resolve for Cloud Run; a retry of the
  apply succeeds.

## The secret VALUE (out-of-band, once)

Terraform creates the secret **container** only. Add the version separately so the value
never enters the state file:

```sh
printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-
```

## Named secrets / config

- Service `janbot-api`, region `europe-central2`, **authenticated-only** (no `allUsers`
  binding). To share a demo later: `gcloud run services add-iam-policy-binding janbot-api
  --region=europe-central2 --member=… --role=roles/run.invoker`.
- Env: `JANBOT_MODEL_MODE=production`, `OPENROUTER_API_KEY` from Secret Manager.
  `JANBOT_PROGRAM_PATH` stays unset (the baseline ships).

## Replacement proof

The hand-made E1 spike is **not** in Terraform state, so `terraform destroy` cannot remove
it — delete it with `gcloud`, then `apply` from zero (the image is rebuilt and pushed
automatically; only the secret **version** is re-added):

```sh
gcloud run services delete janbot-api --region=europe-central2 --quiet
gcloud artifacts repositories delete janbot --location=europe-central2 --quiet
gcloud secrets delete OPENROUTER_API_KEY --quiet
terraform apply -var image_tag=$(git rev-parse --short HEAD)
printf '%s' "$OPENROUTER_API_KEY" | gcloud secrets versions add OPENROUTER_API_KEY --data-file=-
```

Then re-verify all 7 acceptance criteria at the **new** URL (the Cloud Run URL changes; the
E1 deploy log's URL is historical).

## Destroy caveat + protection-lift procedure

`prevent_destroy` (Artifact Registry repo, secret container) and Cloud Run
`deletion_protection` **block `terraform destroy` by design** — the first destroy errors
until they are lifted deliberately:

1. set `prevent_destroy = false` on the repo + secret container and
   `deletion_protection = false` on the Cloud Run service;
2. `terraform apply` (persist the lift), then `terraform destroy`;
3. *(optional)* restore the flags and `apply`.

## Cleanup policy

With (c) every apply pushes an image, so the repo declares **cleanup policies** in HCL
(keep the 5 newest; delete untagged > 7 days). If the pinned provider lacks
`cleanup_policies`, apply them out-of-band and move them into HCL later:

```sh
gcloud artifacts repositories set-cleanup-policies janbot --location=europe-central2 \
  --policy=keep-5.json
```
