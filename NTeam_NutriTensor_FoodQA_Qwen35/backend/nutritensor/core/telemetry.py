"""Request metrics deliberately omit prompts, images, food names, and session tokens."""

from __future__ import annotations

import json
import os
import logging
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in ("request_id", "job_id", "stage", "duration_ms", "error_code"):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        # Developer-only diagnostics are written to the local server console.
        # Do not include prompts, image bytes, auth headers, or session cookies.
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
            if os.getenv("NTEAM_DEBUG_TRACEBACK", "false").lower() in {"1", "true", "yes"}:
                payload["traceback"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger = logging.getLogger("nutritensor")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False


class Metrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.requests = Counter(
            "nteam_http_requests_total", "Requests by route and status", ["route", "status"],
            registry=self.registry,
        )
        self.request_seconds = Histogram(
            "nteam_http_duration_seconds", "HTTP duration", ["route"], registry=self.registry,
        )
        self.jobs = Counter(
            "nteam_jobs_total", "Analysis jobs by outcome", ["outcome"], registry=self.registry,
        )
        self.stage_seconds = Histogram(
            "nteam_stage_duration_seconds", "Stage latency", ["stage"], registry=self.registry,
        )
        self.queue_depth = Gauge(
            "nteam_queue_depth", "Waiting inference jobs", registry=self.registry,
        )
        self.active_jobs = Gauge(
            "nteam_active_jobs", "Running analysis jobs", registry=self.registry,
        )
        self.generation_tokens = Counter(
            "nteam_generation_tokens_total", "Generated completion tokens", registry=self.registry,
        )

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self.stage_seconds.labels(stage=name).observe(time.perf_counter() - started)

    def render(self) -> bytes:
        return generate_latest(self.registry)
