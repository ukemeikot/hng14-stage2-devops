# ── Stage 1: build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install --no-cache-dir -r requirements.txt \
    && /venv/bin/pip uninstall -y pip setuptools wheel 2>/dev/null || true

# ── Stage 2: runtime image ────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install redis-cli for the HEALTHCHECK (tiny, no server components)
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --shell /bin/sh --create-home appuser

COPY --from=builder /venv /venv

WORKDIR /app
COPY worker.py .

ENV PATH="/venv/bin:$PATH"

USER appuser

# Use redis-cli ping — much faster than spawning a full Python interpreter
# DL3025: env vars in HEALTHCHECK CMD are intentional (run-time config)
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD redis-cli -h "${REDIS_HOST:-redis}" -p "${REDIS_PORT:-6379}" -a "$REDIS_PASSWORD" ping | grep -q PONG || exit 1

CMD ["python", "worker.py"]
