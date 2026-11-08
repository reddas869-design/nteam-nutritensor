from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from nutritensor.core.errors import GenerationCancelled
from nutritensor.domain.models import (
    AnalysisRequest, Candidate, EvidenceSummary, FoodSelection, PortionResult,
    QualityFlag, RuntimeStats, Stage,
)
from nutritensor.nutrition.calculator import Aggregate


EventSink = Callable[[Stage, str, str, float, dict | None], Awaitable[None]]


@dataclass(slots=True)
class AgentContext:
    job_id: str
    owner_id: str
    request: AnalysisRequest
    emit: EventSink
    cancel: threading.Event
    image_path: Path | None = None
    candidates: list[Candidate] = field(default_factory=list)
    model_foods: list = field(default_factory=list)
    transient_catalog: object | None = None
    model_only: bool = False
    selections: list[FoodSelection] = field(default_factory=list)
    portions: list[PortionResult] = field(default_factory=list)
    aggregate: Aggregate | None = None
    flags: list[QualityFlag] = field(default_factory=list)
    evidence: EvidenceSummary = field(default_factory=EvidenceSummary)
    stats: RuntimeStats = field(default_factory=RuntimeStats)
    explanation: str = ""
    started: float = field(default_factory=time.perf_counter)
    needs_confirmation: bool = True

    def check_cancelled(self) -> None:
        if self.cancel.is_set():
            raise GenerationCancelled("Analysis cancelled")

    def add_stats(self, stats: RuntimeStats) -> None:
        self.stats.model_ms += stats.model_ms
        self.stats.prompt_tokens += stats.prompt_tokens
        self.stats.completion_tokens += stats.completion_tokens
        self.stats.backend = stats.backend
        self.stats.cache_hit = self.stats.cache_hit or stats.cache_hit
        if stats.gpu_peak_mb is not None:
            self.stats.gpu_peak_mb = max(self.stats.gpu_peak_mb or 0, stats.gpu_peak_mb)
        if self.stats.model_ms > 0:
            self.stats.tokens_per_second = self.stats.completion_tokens / (self.stats.model_ms / 1000)
