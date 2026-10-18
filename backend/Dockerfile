# syntax=docker/dockerfile:1

# Stage 1: build the virtual environment. uv and its caches stay in this stage.
# Production would pin the base image by digest (python:3.12-slim@sha256:...).
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# Dependencies first: this layer is rebuilt only when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

# Download the embedding model now, so containers never fetch it at runtime.
# Keep the name in step with `embedding_model` in app/core/config.py.
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN /app/.venv/bin/python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}', cache_dir='/models')"

# Stage 2: the image we ship. No uv, no compilers, no dev tools.
FROM python:3.12-slim AS runtime
# Security fixes released since the base image was built (Trivy found a fixable CRITICAL
# in perl-base). Production pins the base by digest and lets Dependabot move it.
RUN apt-get update && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /models /models
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app app ./app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    EMBEDDING_CACHE_DIR=/models \
    HF_HUB_OFFLINE=1
USER app
EXPOSE 8000

# Liveness only: /health does not touch the database.
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"]

# --proxy-headers: take the client IP from X-Forwarded-For, but only from addresses listed in
# FORWARDED_ALLOW_IPS (the frontend proxy). Otherwise rate limits would see one shared IP.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
