from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings
from app.services.inference_limiter import InferenceLimiter
from app.services.model_manager import ModelManager


@dataclass
class Pipeline:
    key: str


class Adapter:
    def __init__(self) -> None:
        self.calls = 0
        self.released: list[str] = []
        self._lock = threading.Lock()

    def create(self, model: str, language: str, settings: Settings) -> Pipeline:
        with self._lock:
            self.calls += 1
        time.sleep(0.02)
        return Pipeline(f"{model}:{language}")

    def predict(self, pipeline: Pipeline, input_value, **parameters):
        return []

    def release(self, pipeline: Pipeline) -> None:
        self.released.append(pipeline.key)


class Factory:
    def __init__(self, adapter: Adapter) -> None:
        self.adapter = adapter

    def for_task(self, task: str) -> Adapter:
        return self.adapter


def _settings(tmp_path: Path, cache_size: int = 2) -> Settings:
    return Settings(paddle_model_home=tmp_path / "models", model_cache_size=cache_size, request_timeout_seconds=5)


def test_model_manager_deduplicates_concurrent_loads_and_enforces_lru(tmp_path: Path) -> None:
    async def scenario() -> None:
        adapter = Adapter()
        manager = ModelManager(_settings(tmp_path, cache_size=2), adapters=Factory(adapter))
        leases = await asyncio.gather(*[manager.acquire("ocr", "pp-ocrv5", "en") for _ in range(8)])
        assert adapter.calls == 1
        assert manager.loaded_model_count == 1
        for lease in leases:
            await lease.release()
        for language in ("ru", "en"):
            lease = await manager.acquire("ocr", "model-" + language, language)
            await lease.release()
        assert manager.loaded_model_count == 2
        assert adapter.released
        await manager.close()

    asyncio.run(scenario())


def test_inference_limiter_caps_concurrency() -> None:
    async def scenario() -> None:
        limiter = InferenceLimiter(maximum=2, timeout_seconds=2)
        active = 0
        maximum_active = 0
        counter_lock = threading.Lock()

        def operation() -> None:
            nonlocal active, maximum_active
            with counter_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            time.sleep(0.03)
            with counter_lock:
                active -= 1

        await asyncio.gather(*[limiter.run(asyncio.Lock(), operation) for _ in range(6)])
        assert maximum_active == 2

    asyncio.run(scenario())
