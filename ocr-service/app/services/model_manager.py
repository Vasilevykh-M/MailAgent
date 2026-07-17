"""Concurrency-safe lazy model cache with per-model load locks and LRU eviction."""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from app.core.config import Settings
from app.services.paddle_adapters import AdapterFactory, PipelineAdapter

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelKey:
    task: str
    model: str
    language: str
    device: str
    pipeline_parameters: tuple[tuple[str, str], ...] = ()


@dataclass
class LoadedModel:
    key: ModelKey
    pipeline: Any
    adapter: PipelineAdapter
    inference_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    active_leases: int = 0
    evicted: bool = False


class ModelLease:
    """A reference-counted cached model lease."""

    def __init__(self, manager: ModelManager, loaded: LoadedModel, cache_hit: bool, load_time_ms: int) -> None:
        self._manager = manager
        self.loaded = loaded
        self.cache_hit = cache_hit
        self.load_time_ms = load_time_ms
        self._released = False

    async def release(self) -> None:
        if not self._released:
            self._released = True
            await self._manager.release(self.loaded)

    async def __aenter__(self) -> ModelLease:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.release()


class ModelManager:
    """Caches pipelines; factories only run in worker threads after lazy demand."""

    def __init__(self, settings: Settings, adapters: AdapterFactory | None = None) -> None:
        self._settings = settings
        self._adapters = adapters or AdapterFactory()
        self._cache: OrderedDict[ModelKey, LoadedModel] = OrderedDict()
        self._cache_lock = asyncio.Lock()
        self._load_locks: dict[ModelKey, asyncio.Lock] = {}

    @property
    def loaded_model_count(self) -> int:
        return len(self._cache)

    async def acquire(self, task: str, model: str, language: str) -> ModelLease:
        key = ModelKey(task, model, language, self._settings.paddle_device, (("api", "v3"),))
        async with self._cache_lock:
            existing = self._cache.get(key)
            if existing is not None:
                existing.active_leases += 1
                self._cache.move_to_end(key)
                return ModelLease(self, existing, cache_hit=True, load_time_ms=0)
            lock = self._load_locks.setdefault(key, asyncio.Lock())

        async with lock:
            async with self._cache_lock:
                existing = self._cache.get(key)
                if existing is not None:
                    existing.active_leases += 1
                    self._cache.move_to_end(key)
                    return ModelLease(self, existing, cache_hit=True, load_time_ms=0)
            adapter = self._adapters.for_task(task)
            logger.info(
                "model_loading_started task=%s model=%s language=%s device=%s", task, model, language, key.device
            )
            started = time.perf_counter()
            try:
                pipeline = await asyncio.to_thread(adapter.create, model, language, self._settings)
            except Exception:
                logger.exception(
                    "model_loading_failed task=%s model=%s language=%s device=%s", task, model, language, key.device
                )
                raise
            load_time_ms = int((time.perf_counter() - started) * 1000)
            loaded = LoadedModel(key=key, pipeline=pipeline, adapter=adapter, active_leases=1)
            logger.info(
                "model_loading_completed task=%s model=%s language=%s device=%s loading_time_ms=%s",
                task,
                model,
                language,
                key.device,
                load_time_ms,
            )
            evicted = await self._insert_and_evict(loaded)
            for item in evicted:
                await asyncio.to_thread(self._release_pipeline, item)
            return ModelLease(self, loaded, cache_hit=False, load_time_ms=load_time_ms)

    async def _insert_and_evict(self, loaded: LoadedModel) -> list[LoadedModel]:
        releasable: list[LoadedModel] = []
        async with self._cache_lock:
            self._cache[loaded.key] = loaded
            while len(self._cache) > self._settings.model_cache_size:
                _, candidate = self._cache.popitem(last=False)
                candidate.evicted = True
                if candidate.active_leases == 0:
                    releasable.append(candidate)
        return releasable

    async def release(self, loaded: LoadedModel) -> None:
        should_release = False
        async with self._cache_lock:
            loaded.active_leases -= 1
            if loaded.active_leases < 0:
                raise RuntimeError("Model lease released more than once")
            should_release = loaded.evicted and loaded.active_leases == 0
        if should_release:
            await asyncio.to_thread(self._release_pipeline, loaded)

    @staticmethod
    def _release_pipeline(loaded: LoadedModel) -> None:
        try:
            loaded.adapter.release(loaded.pipeline)
        except Exception:
            logger.exception("model_release_failed task=%s model=%s", loaded.key.task, loaded.key.model)

    async def close(self) -> None:
        async with self._cache_lock:
            items = list(self._cache.values())
            self._cache.clear()
            for item in items:
                item.evicted = True
        for item in items:
            if item.active_leases == 0:
                await asyncio.to_thread(self._release_pipeline, item)
