FROM python:3.11.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/api-service

RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml uv.lock README.md ./
RUN pip install --no-cache-dir uv==0.5.21 && uv sync --frozen --no-dev --no-install-project
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev
RUN chown -R appuser:appuser /srv/api-service
USER appuser

EXPOSE 8080
CMD ["sh", "-c", "uv run alembic upgrade head && uv run mail-results-partitions && uv run uvicorn app.main:app --host 0.0.0.0 --port 8080"]
