"""Run blocking, potentially non-thread-safe model calls off the event loop."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from app.core.exceptions import InferenceTimeoutError

logger = logging.getLogger(__name__)


class InferenceLimiter:
    def __init__(self, maximum: int, timeout_seconds: int) -> None:
        self._semaphore = asyncio.Semaphore(maximum)
        self._timeout_seconds = timeout_seconds

    async def run(self, model_lock: asyncio.Lock, operation: Callable[[], Any]) -> tuple[Any, int, int]:
        """Return result, semaphore wait time and inference time in milliseconds."""

        waiting_started = time.perf_counter()
        await self._semaphore.acquire()
        wait_ms = int((time.perf_counter() - waiting_started) * 1000)
        await model_lock.acquire()
        started = time.perf_counter()
        task = asyncio.create_task(asyncio.to_thread(operation))
        deferred_release = False
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=self._timeout_seconds)
            return result, wait_ms, int((time.perf_counter() - started) * 1000)
        except TimeoutError as exc:
            # A worker thread cannot safely be cancelled. Hold both guards until
            # it exits so a timed-out pipeline is never used concurrently.
            task.add_done_callback(lambda completed: self._complete_timed_out_task(completed, model_lock))
            deferred_release = True
            raise InferenceTimeoutError("Inference exceeded the configured request timeout") from exc
        finally:
            if not deferred_release:
                model_lock.release()
                self._semaphore.release()

    def _release_guards(self, model_lock: asyncio.Lock) -> None:
        model_lock.release()
        self._semaphore.release()

    def _complete_timed_out_task(self, task: asyncio.Task[Any], model_lock: asyncio.Lock) -> None:
        try:
            task.result()
        except BaseException as exc:
            # The exception is already represented by the timeout response; log
            # its safe type while still consuming it to avoid an asyncio warning.
            logger.warning("timed_out_worker_completed_with_error error_type=%s", type(exc).__name__)
        self._release_guards(model_lock)
