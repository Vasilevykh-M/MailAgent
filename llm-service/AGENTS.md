# AGENTS.md

## Service contract

This repository runs `Qwen/Qwen3.6-27B-FP8` with vLLM and native Ray on two Linux servers, one visible RTX 5090 per server.

The Makefile is the only operational interface. Do not add required wrapper scripts and do not load `.env` files.

## Topology

- head: Ray head, one GPU, vLLM OpenAI-compatible API;
- worker: Ray worker, one GPU, no HTTP API;
- tensor parallel size: 1;
- pipeline parallel size: 2;
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

Use `config.mk` for non-secret node configuration. Use `config.mk.example` on head and `config.worker.mk.example` on worker.

Pass `VLLM_API_KEY` and `HF_TOKEN` through the process environment. Never commit real secrets.

## Validation

Before delivery:

```bash
make check-config
make check
```

Verify that the Makefile parses, both config templates are present, and documentation does not require `scripts/*.sh` or `.env`.
