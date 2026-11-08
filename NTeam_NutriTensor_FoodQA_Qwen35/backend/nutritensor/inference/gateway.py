"""Asynchronous admission control around a blocking, single-GPU provider."""

from __future__ import annotations

import asyncio

from nutritensor.core.errors import QueueFull
from nutritensor.inference.contracts import GenerationRequest, GenerationResult, InferenceProvider


class ModelGateway:
    def __init__(self, provider: InferenceProvider, capacity: int = 4):
        self.provider = provider
        self.capacity = capacity
        self._pending = 0
        self._lock = asyncio.Lock()

    @property
    def pending(self) -> int:
        return self._pending

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        if self._pending >= self.capacity:
            raise QueueFull("The local model is busy. Retry after the current analysis.")
        self._pending += 1
        try:
            async with self._lock:
                # Shield the thread: request cancellation cannot imply CUDA completion.
                task = asyncio.create_task(asyncio.to_thread(self.provider.generate, request))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    request.cancel.set()
                    try:
                        await task
                    except Exception:
                        pass
                    raise
        finally:
            self._pending -= 1

    async def close(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self.provider.close)
