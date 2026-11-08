"""Durable job state plus a bounded single-process analysis scheduler."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass

from nutritensor.agents.context import AgentContext
from nutritensor.agents.roles import CalculationAgent, ExplanationAgent, IdentificationAgent, RetrievalAgent, ReviewAgent
from nutritensor.core.config import Settings
from nutritensor.core.errors import AppError, Conflict, GenerationCancelled, QueueFull
from nutritensor.core.telemetry import Metrics
from nutritensor.domain.models import AnalysisRequest, AnalysisResult, FoodRecord, JobStatus, Stage
from nutritensor.inference.gateway import ModelGateway
from nutritensor.nutrition.catalog import Catalog
from nutritensor.services.images import ImageService
from nutritensor.storage.database import Database, timestamp


logger = logging.getLogger("nutritensor.agents")


@dataclass(slots=True)
class WorkItem:
    job_id: str
    owner: str
    request: AnalysisRequest
    cancel: threading.Event
    submitted: float
    model_records: list[FoodRecord] | None = None


class Coordinator:
    def __init__(
        self, settings: Settings, database: Database, catalog: Catalog,
        gateway: ModelGateway, images: ImageService, metrics: Metrics,
    ):
        self.settings = settings
        self.database = database
        self.catalog = catalog
        self.gateway = gateway
        self.images = images
        self.metrics = metrics
        self.queue: asyncio.Queue[WorkItem] = asyncio.Queue(maxsize=settings.queue_capacity)
        self._pending: dict[str, WorkItem] = {}
        self._worker: asyncio.Task | None = None
        self._accepting = False
        self._roles = [
            (Stage.IDENTIFY, IdentificationAgent(catalog, gateway, settings)),
            (Stage.RETRIEVE, RetrievalAgent(catalog, gateway, settings)),
            (Stage.CALCULATE, CalculationAgent(catalog)),
            (Stage.REVIEW, ReviewAgent()),
            (Stage.EXPLAIN, ExplanationAgent(gateway, settings)),
        ]

    async def start(self) -> None:
        self.database.recover_interrupted_jobs()
        self._accepting = True
        self._worker = asyncio.create_task(self._loop(), name="nutritensor-analysis-worker")

    async def stop(self) -> None:
        self._accepting = False
        for item in self._pending.values():
            item.cancel.set()
            self.database.set_status(item.job_id, JobStatus.CANCELLED)
        if self._worker:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass
        await self.gateway.close()

    def submit(self, owner: str, request: AnalysisRequest, idempotency_key: str | None = None) -> str:
        if not self._accepting:
            raise QueueFull("The service is shutting down")
        model_records: list[FoodRecord] = []
        if request.source_analysis_id:
            # A client may only reuse its own completed scan's immutable food records.
            parent = self.database.get_job(request.source_analysis_id, owner)
            if parent.status != JobStatus.COMPLETE or not parent.result:
                raise Conflict("The source scan must be complete before confirming portions")
            selected = {item.food_id for item in request.items}
            model_records = [
                portion.food.model_copy(deep=True) for portion in parent.result.portions
                if portion.food.id in selected and portion.food.source.provider.startswith("Qwen3.5-4B (")
            ]
        if request.image_id:
            self.images.path(owner, request.image_id)
        if request.items:
            allowed = {food.id for food in model_records}
            for selection in request.items:
                if selection.food_id not in allowed:
                    self.catalog.get(selection.food_id)
        elif self.settings.is_demo or not (request.image_id or request.description):
            self.catalog.require_available()
        if request.description and self.settings.is_demo:
            from nutritensor.nutrition.policy import food_names_only
            food_names_only(request.description, self.catalog)
        # An existing idempotent request must remain retrievable even when the queue is full.
        if idempotency_key:
            with self.database.connection() as connection:
                previous = connection.execute(
                    "SELECT id,request_json FROM jobs WHERE owner_id=? AND idempotency_key=?", (owner, idempotency_key)
                ).fetchone()
            if previous:
                job_id, _ = self.database.create_job(owner, request, idempotency_key)
                return job_id
        if self.owner_busy(owner):
            raise QueueFull("Wait for or cancel your current analysis before starting another.")
        if self.queue.full():
            raise QueueFull("The analysis queue is full. Wait for an existing meal to finish.")
        job_id, created = self.database.create_job(owner, request, idempotency_key)
        if not created:
            return job_id
        item = WorkItem(job_id, owner, request, threading.Event(), time.perf_counter(), model_records)
        self._pending[job_id] = item
        self.queue.put_nowait(item)
        self.metrics.queue_depth.set(self.queue.qsize())
        self.database.append_event(job_id, Stage.INTAKE, "completed", "Meal added to the analysis queue", 0.05)
        return job_id

    def cancel(self, owner: str, job_id: str) -> None:
        job = self.database.get_job(job_id, owner)
        if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
            raise Conflict("This analysis has already finished")
        item = self._pending.get(job_id)
        if item:
            item.cancel.set()
        self.database.set_status(job_id, JobStatus.CANCELLED)
        self.database.append_event(job_id, Stage.COMPLETE, "cancelled", "Analysis cancelled", 1)

    def owner_busy(self, owner: str) -> bool:
        return any(item.owner == owner for item in self._pending.values())

    async def _loop(self) -> None:
        while True:
            item = await self.queue.get()
            self.metrics.queue_depth.set(self.queue.qsize())
            try:
                if item.cancel.is_set():
                    continue
                self.metrics.active_jobs.set(1)
                await self._execute(item)
            except Exception as exc:
                # A storage or cleanup failure must not silently kill the only worker.
                logger.exception("Worker operation failed", extra={"job_id": item.job_id, "error_code": type(exc).__name__})
                try:
                    self.database.set_status(item.job_id, JobStatus.FAILED, "A worker operation failed; retry the analysis.")
                except Exception:
                    logger.error("Unable to persist worker failure", extra={"job_id": item.job_id})
            finally:
                self.metrics.active_jobs.set(0)
                self._pending.pop(item.job_id, None)
                self.queue.task_done()

    async def _execute(self, item: WorkItem) -> None:
        if not self.database.set_status(item.job_id, JobStatus.RUNNING):
            return

        async def emit(stage, state, message, progress, detail=None):
            if not item.cancel.is_set():
                self.database.append_event(item.job_id, stage, state, message, progress, detail)

        context = AgentContext(
            job_id=item.job_id, owner_id=item.owner, request=item.request,
            emit=emit, cancel=item.cancel,
        )
        context.stats.queue_ms = (time.perf_counter() - item.submitted) * 1000
        if item.model_records:
            context.transient_catalog = Catalog([*self.catalog.all(), *item.model_records])
        try:
            # An upload may have expired or been removed while waiting in the queue.
            if item.request.image_id:
                context.image_path = self.images.path(item.owner, item.request.image_id)
            for stage, role in self._roles:
                context.check_cancelled()
                await emit(stage, "started", f"Running {stage.value}", {
                    Stage.IDENTIFY: .12, Stage.RETRIEVE: .35, Stage.CALCULATE: .55,
                    Stage.REVIEW: .74, Stage.EXPLAIN: .87,
                }[stage])
                with self.metrics.stage(stage.value):
                    await role.run(context)
            context.check_cancelled()
            context.stats.total_ms = (time.perf_counter() - context.started) * 1000
            result = AnalysisResult(
                id=item.job_id, created_at=timestamp(), meal_name=item.request.meal_name,
                meal_type=item.request.meal_type, mode=self.settings.mode,
                needs_confirmation=context.needs_confirmation, candidates=context.candidates,
                portions=context.portions, totals=context.aggregate.totals,
                lower=context.aggregate.lower, upper=context.aggregate.upper,
                coverage=context.aggregate.coverage, flags=context.flags,
                evidence=context.evidence, explanation=context.explanation,
                stats=context.stats, catalog_version=("qwen35-estimates" if context.model_only or item.model_records else self.catalog.version), image_id=item.request.image_id,
            )
            if self.database.complete_job(item.job_id, result):
                await emit(Stage.COMPLETE, "completed", "Ready to review", 1)
                self.metrics.jobs.labels(outcome="complete").inc()
                self.metrics.generation_tokens.inc(context.stats.completion_tokens)
        except GenerationCancelled:
            self.database.set_status(item.job_id, JobStatus.CANCELLED)
            self.metrics.jobs.labels(outcome="cancelled").inc()
        except asyncio.CancelledError:
            item.cancel.set()
            self.database.set_status(item.job_id, JobStatus.CANCELLED)
            raise
        except Exception as exc:
            message = exc.message if isinstance(exc, AppError) else "Analysis failed unexpectedly. Check the local server logs."
            self.database.set_status(item.job_id, JobStatus.FAILED, message)
            await emit(Stage.COMPLETE, "failed", message, 1, {"error_code": type(exc).__name__})
            self.metrics.jobs.labels(outcome="failed").inc()
            logger.exception("Analysis failed", extra={"job_id": item.job_id, "error_code": type(exc).__name__})
        finally:
            if item.request.image_id and not self.database.preferences(item.owner).save_images:
                try:
                    self.images.remove(item.owner, item.request.image_id)
                except AppError:
                    pass
