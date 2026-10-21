# JanBot container (M4/E1 authenticated spike).
#
# Build with the file NAMED EXPLICITLY so nothing auto-detects a missing Dockerfile:
#   podman build -f Containerfile -t janbot:local .
#   buildah bud -f Containerfile -t janbot:local .
#   docker build -f Containerfile -t janbot:local .
# `Containerfile` is the OCI-standard name (identical syntax); the neutral
# `.dockerignore` is honoured by both Podman (after `.containerignore`) and Docker.
#
# Baked at build: the corpus, the vector index (python -m janbot.ingest) and Chroma's
# ONNX all-MiniLM-L6-v2 embedding model. No ingest at startup; no secret in the image.
# Dependencies come from uv.lock; the project itself is not installed as a wheel
# (src/ is placed on PYTHONPATH) so the build needs no package build backend.

# Base images are pinned by digest; bump them deliberately (see terraform/README.md
# "Base-image bump"). A tag would move under the build with no plan diff.
ARG PYTHON_IMAGE=python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG UV_IMAGE=ghcr.io/astral-sh/uv@sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336

# The uv image gets its own stage: the kreuzwerker/docker provider's legacy
# builder does not expand ARGs in `COPY --from=`, but it does expand them in
# `FROM`, so the digest pin still lives in exactly one place (the ARG above).
FROM ${UV_IMAGE} AS uvsrc

FROM ${PYTHON_IMAGE} AS builder

COPY --from=uvsrc /uv /uvx /bin/

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

FROM ${PYTHON_IMAGE} AS runtime

# Re-declare the ARGs so the labels below can see them.
ARG PYTHON_IMAGE
ARG UV_IMAGE
LABEL org.opencontainers.image.base.name="python:3.12-slim" \
      org.opencontainers.image.base.digest="sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1" \
      org.opencontainers.image.base.uv.digest="sha256:4a1f3666816dafadd20ceb71eac9a7d56d7ef30279f7d64048519ab901ada336"

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    JANBOT_PROJECT_ROOT=/app \
    JANBOT_MODEL_MODE=production \
    JANBOT_CORPUS_PATH=/app/public_profile_org \
    JANBOT_INDEX_PATH=/app/index \
    JANBOT_CACHE_PATH=/app/cache/answers.json

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY src/ ./src/
COPY public_profile_org/ ./public_profile_org/
COPY eval/golden_dataset.yaml ./eval/golden_dataset.yaml
COPY cache/ ./cache/
COPY README.md ./

# Fetch and verify the pinned ONNX MiniLM model before building the index. A
# transient download is retried; a persistent failure or sha mismatch fails the
# build loudly. The model identity is recorded in index-identity.json.
RUN python -m janbot.store.embedding_model

# Bake: build the index. No key; no startup ingest.
RUN python -m janbot.ingest

# Bake the pinned answer cache: validates provenance (run id, dataset sha, corpus
# commit) and fails the build on a dataset mismatch. No key; no model call.
RUN python -m janbot.guardrails.build_cache \
    --source cache/answers-fc430d3e17714457b896bafdac9cc1ac.json \
    --out /app/cache/answers.json

EXPOSE 8080
CMD ["sh", "-c", "uvicorn janbot.api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
