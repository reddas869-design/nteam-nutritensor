"""Small provider protocol keeps the nutrition engine independent of GPU libraries."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from nutritensor.domain.models import ModelCapabilities, RuntimeStats


@dataclass(slots=True)
class GenerationRequest:
    system: str
    prompt: str
    image_path: Path | None = None
    max_new_tokens: int = 384
    thinking: bool = False
    cancel: threading.Event = field(default_factory=threading.Event)
    purpose: str = "explanation"


@dataclass(slots=True)
class GenerationResult:
    text: str
    stats: RuntimeStats


class InferenceProvider(Protocol):
    def capabilities(self) -> ModelCapabilities: ...
    def generate(self, request: GenerationRequest) -> GenerationResult: ...
    def close(self) -> None: ...
