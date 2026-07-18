# AGENTS.md

## Service contract

This repository runs `Qwen/Qwen3.5-9B` with vLLM and native Ray on one Linux host with one visible RTX 2060.

The Makefile is the only operational interface. Do not add required wrapper scripts and do not load `.env` files.

## Topology

- head: local Ray head, one GPU, vLLM OpenAI-compatible API;
- worker: optional Ray worker for a separately configured multi-node extension, no HTTP API;
- tensor parallel size: 1;
- pipeline parallel size: 1;
- distributed executor backend: Ray.

## Commands

```bash
make install
make start
make status
make cluster-status
make health
make smoke
make stop
```

## Configuration

Use `config.mk` for non-secret node configuration. The required one-host profile is `config.mk.example`; `config.worker.mk.example` is optional and not used on a single RTX 2060.

Pass `VLLM_API_KEY` and `HF_TOKEN` through the process environment. Never commit real secrets.

## Validation

Before delivery:

```bash
make check-config
make check
```

Verify that the Makefile parses, both config templates are present, and documentation does not require `scripts/*.sh` or `.env`.
