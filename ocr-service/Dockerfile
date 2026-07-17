FROM ghcr.io/astral-sh/uv:0.11.13 AS uv

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PADDLE_DEVICE=cpu \
    PADDLE_MODEL_HOME=/models \
    PADDLE_PDX_CACHE_HOME=/models

WORKDIR /srv/app

COPY --from=uv /uv /uvx /bin/

RUN groupadd --system appuser \
    && useradd --system --gid appuser --home-dir /srv/app appuser \
    && mkdir -p /models /tmp/ocr \
    && chown -R appuser:appuser /models /tmp/ocr /srv/app

COPY pyproject.toml uv.lock README.md ./
COPY app ./app

RUN uv sync --frozen --no-dev --no-install-project \
    && chown -R appuser:appuser /srv/app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8000/health/live', timeout=3)"

CMD ["/srv/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
