# LogSight backend image (FastAPI + uv).
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS base

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first (better layer caching).
COPY backend/pyproject.toml backend/uv.lock* ./
RUN if [ -f uv.lock ]; then uv sync --frozen --no-dev; else uv sync --no-dev; fi

COPY backend/app ./app
COPY backend/migrations ./migrations

# Run as non-root where practical.
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Apply SQL migrations, then start the API.
CMD ["sh", "-c", "python -m app.migrate --recover && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
