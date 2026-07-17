# Agent Instructions: ocr-service

## Scope of Work

Work only inside `ocr-service`.

Do not modify or create files in the repository root, `llm-service/`, or
`yandex/` unless the user has made a separate explicit request. In particular,
do not change another service's dependencies, configuration, or documentation.

`ocr-service` is a standalone application. Do not connect it to other services
through imports, shared runtime directories, shared dependencies, or a proxy
layer without an explicit request.

## Purpose and Public API

The service provides a FastAPI API for official PaddleOCR pipelines:

- standard OCR through `PaddleOCR` (`POST /api/v1/ocr`);
- document parsing through `PPStructureV3`
  (`POST /api/v1/documents/parse`).

Maintain these public endpoints:

```text
GET  /health/live
GET  /health/ready
GET  /api/v1/capabilities
POST /api/v1/ocr
POST /api/v1/documents/parse
```

Do not replace PaddleOCR with cloud OCR, SaaS, stubs, or an obsolete API. Do
not return internal PaddleOCR objects or raw result structures directly.

## Architecture

Keep the separation of responsibilities:

```text
FastAPI routes → ProcessingService → CapabilitiesRegistry / FileProcessor /
ModelManager / InferenceLimiter → PaddleOCR adapters → normalizers
```

- Routers accept HTTP requests and must not create PaddleOCR objects.
- `CapabilitiesRegistry` is the single source of truth for tasks, models,
  languages, defaults, and compatibility. Use it for `/capabilities`,
  validation, and adapter selection.
- `ModelManager` loads models lazily, uses a lock for every key, maintains an
  LRU cache, and must not create a model instance per request.
- The cache key includes, at minimum, task, model, language, device, and
  material pipeline parameters.
- Inference runs outside the event loop, is capped by a process-wide semaphore,
  and access to an individual model instance is serialized.
- Adapters encapsulate the PaddleOCR Python API; normalizers produce stable
  Pydantic responses.

Do not load models during module import, application startup, `GET /health/live`,
or `GET /health/ready`.

## Models and Configuration

- CPU is the default mode. Do not install CPU and GPU PaddlePaddle wheels in
  the same dependency set.
- GPU is enabled with `PADDLE_DEVICE`, for example `gpu:0`, and a compatible
  GPU wheel described in the documentation.
- `PADDLE_MODEL_HOME` must be a writable persistent directory. Do not add model
  weights to the repository or Docker layers.
- Values from `.env.example` must be typed and validated.
- Do not change models, languages, or defaults without updating the capability
  registry, tests, OpenAPI, and documentation.

## File and Data Security

- Maintain allowlists for MIME types and extensions, plus signature and content
  validation for JPEG, PNG, and PDF.
- Preserve upload-size and PDF-page-count limits.
- Do not trust the original filename or pass user data to shell commands.
- Use temporary PDFs with random names and delete them after success and after
  exceptions.
- Do not persist user documents.
- Do not log document contents, OCR results, binary data, personal data,
  secrets, or local paths.
- API errors must not reveal tracebacks, raw PaddleOCR exceptions, or
  environment variables.

Every request must have a `request_id`: retain a valid incoming `X-Request-ID`,
otherwise generate a UUID; return it in headers, responses, and errors.

## Dependencies and Checks

Use the isolated project:

```bash
cd ocr-service
uv lock --check
uv sync --extra dev --python 3.11
uv run ruff format --check app tests
uv run ruff check app tests
uv run pytest
uv run python -c "from app.main import app; print(sorted(route.path for route in app.routes))"
```

The real PaddleOCR smoke test runs only when explicitly enabled:

```bash
RUN_PADDLE_SMOKE=1 PADDLE_SMOKE_IMAGE=/absolute/path/to/image.png \
  uv run pytest -m integration
```

Do not claim that real inference, GPU mode, the Docker build, or the smoke test
works unless that exact check has actually run.

Format and check only `ocr-service` files; never run tools with a scope that
includes `yandex/`.

## Docker

Maintain these Docker-image properties:

- CPU startup by default;
- an unprivileged user;
- a mountable `/models` directory for weights;
- `GET /health/live` in `HEALTHCHECK`;
- no `.env`, `.git`, documents, virtual environment, or model weights in the
  image;
- Uvicorn startup using `app.main:app`.

## Documentation

Documentation is written in Russian. Do not translate commands, filenames,
URLs, JSON fields, environment variables, model identifiers, or actual API
messages.

When behavior changes, update the relevant documents:

- `README.md` — quick start, configuration, and user examples;
- `docs/architecture.md` — components, data flow, and security;
- `docs/api.md` — public HTTP contract and errors;
- `docs/operations.md` — deployment, monitoring, resources, and updates;
- `docs/README.md` — documentation navigation.

## Generated Artifacts

Do not add these to the repository. Clean them only inside `ocr-service` when
needed:

```text
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
paddleocr_fastapi_service.egg-info/
models/
tmp/
```

Do not delete source code, tests, the lock file, or documentation without a
clear reason and a user request.

## Final Report

In the final response, briefly state:

1. what changed;
2. which checks ran and their results;
3. which checks did not run and why;
4. that changes are limited to `ocr-service`.

If the task requires a `yandex/` verification, run Git commands only when Git
metadata is available; otherwise, state honestly that verification was not
possible.
