# Agent Instructions

## Repository Map

| Directory      | Purpose                                                       | Working Rules                                                                                                                                               |
| -------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ocr-service/` | FastAPI service for OCR and document parsing using PaddleOCR. | A standalone Python project. All changes to the service, its tests, Docker configuration, and documentation must be made within this directory.             |
| `llm-service/` | vLLM service for Qwen3.5-9B.                                 | Before starting any work, you must read [`llm-service/AGENTS.md`](llm-service/AGENTS.md). Its rules are stricter and take precedence within this directory. |
| `yandex/`      | Independent SDKs for Yandex Mail and Yandex Disk.             | Protected area: do not modify without a separate, explicit user request.                                                                                    |

The repository root does not contain shared dependency configuration, Docker Compose, or CI configuration. Do not add them unless the user explicitly requests integration between the services.

## Change Boundaries

* First determine which service the task belongs to, and work only within that service’s directory.
* Do not connect `ocr-service/` and `llm-service/` through imports, shared dependencies, shared runtime directories, or a proxy layer unless explicitly requested.
* Do not modify another service to fix a local issue.
* Do not modify files in the repository root, except for this `AGENTS.md`, unless there is a separate reason and explicit permission.
* New service source files, tests, Docker files, lock files, and documentation must be located within the corresponding service directory.

## Protecting `yandex/`

Unless the task is explicitly directed at the SDKs in `yandex/`, the following actions are prohibited:

* editing, creating, deleting, moving, or renaming files in `yandex/`;
* running formatting tools, generators, migrations, or bulk replacements that include `yandex/`;
* changing file permissions in `yandex/`;
* fixing existing SDK issues as part of an unrelated task.

Before completing the work, if Git is available, verify the scope of changes:

```bash
git status --short -- yandex
git diff -- yandex
git diff --cached -- yandex
```

If Git metadata is unavailable, report this in the final summary and do not claim that an unavailable Git check was completed successfully.

## General Quality Requirements

* Use types, explicit error handling, and safe default values.
* Do not add secrets, tokens, real `.env` files, or model weights to the repository.
* Do not log the contents of user documents, personal data, binary files, or secrets.
* Do not use `eval`, unsafe interpolation of user data into shell commands, or insecure temporary filenames.
* Do not download large models or perform network requests in unit tests.
* Do not delete source code, tests, or documentation unless explicitly necessary. Generated local artifacts may only be removed within the scope of the current service.
* Before changing an external API, update the tests and documentation together with the implementation.

Documentation must be written in Russian. Do not translate commands, filenames, URLs, JSON fields, environment variables, model identifiers, or actual API messages.

## `ocr-service/`

Before making changes to the OCR service, review:

* [`ocr-service/README.md`](ocr-service/README.md) — quick start and user-facing overview;
* [`ocr-service/docs/`](ocr-service/docs/README.md) — architecture, API, and operations;
* `ocr-service/pyproject.toml` and `ocr-service/uv.lock` — locked dependencies.

### Architectural Rules

* Preserve the separation between the HTTP layer, service layer, file handler, capabilities registry, model manager, PaddleOCR adapters, and normalizers.
* Routers must not instantiate PaddleOCR objects and must not return internal PaddleOCR structures directly.
* `CapabilitiesRegistry` is the single source of truth for tasks, models, languages, default values, and compatibility validation.
* Do not load models during module import, application startup, liveness checks, or readiness checks.
* Preserve lazy, thread-safe model loading, the LRU cache, and the concurrent inference limit.
* Run blocking inference outside the event loop.
* For uploads, preserve validation of file size, MIME type, extension, signature, and content. Temporary PDF files must be deleted on both success and failure.
* The default mode must work on CPU. Do not include both CPU and GPU variants of PaddlePaddle in the same dependency set.

### Dependencies and Checks

Use an isolated environment and the lock file:

```bash
cd ocr-service
uv lock --check
uv sync --extra dev --python 3.11
uv run ruff format --check app tests
uv run ruff check app tests
uv run pytest
```

The real PaddleOCR smoke test is not run by default. It requires an explicit run with `RUN_PADDLE_SMOKE=1` and `PADDLE_SMOKE_IMAGE`. Do not claim that real inference was verified unless this test was actually executed.

After making changes, update the following files when necessary:

* `ocr-service/README.md` — quick start and user-facing overview;
* `ocr-service/docs/architecture.md` — components, data flow, and security;
* `ocr-service/docs/api.md` — HTTP API contract;
* `ocr-service/docs/operations.md` — configuration, Docker, monitoring, and limitations;
* `ocr-service/docs/README.md` — documentation navigation.

## `llm-service/`

For any task within `llm-service/`, you must apply the rules in its local [`AGENTS.md`](llm-service/AGENTS.md). In particular, do not change the Qwen3.5-9B model, add a proxy server, weaken SSRF protections, or run resource-intensive checks without a suitable Linux/GPU environment.

## Final Report

At the end, briefly state:

1. what was changed;
2. which checks were performed and their results;
3. which checks were not performed and why;
4. the scope of the changes: `ocr-service/`, `llm-service/`, or another explicitly requested directory;
5. the status of the `yandex/` verification, when applicable.

Do not claim that execution, real inference, a Docker build, GPU compatibility, or a Git check succeeded unless the corresponding verification was actually performed.
