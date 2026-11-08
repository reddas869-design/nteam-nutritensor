"""Run with uvicorn nutritensor.main:create_app --factory --workers 1."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from nutritensor.agents.coordinator import Coordinator
from nutritensor.api.middleware import BodyLimitMiddleware, ResponseSecurityMiddleware
from nutritensor.api.routes import router
from nutritensor.core.config import Settings
from nutritensor.core.accounts import Accounts
from nutritensor.core.errors import AppError
from nutritensor.core.security import RateLimiter
from nutritensor.core.telemetry import Metrics, configure_logging
from nutritensor.inference.factory import create_provider
from nutritensor.inference.gateway import ModelGateway
from nutritensor.nutrition.catalog import Catalog
from nutritensor.nutrition.demo import demo_catalog
from nutritensor.services.chat import ChatService
from nutritensor.services.images import ImageService
from nutritensor.storage.database import Database


logger = logging.getLogger("nutritensor.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = (settings or Settings.from_env()).validate()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        state = app.state
        state.settings = settings
        state.database = Database(settings.database_path)
        state.catalog = demo_catalog() if settings.is_demo else Catalog.load(
            settings.catalog_path, allow_demo=settings.allow_demo_catalog,
        )
        state.provider = create_provider(settings)
        state.gateway = ModelGateway(state.provider, settings.queue_capacity + 1)
        state.images = ImageService(settings, state.database)
        state.metrics = Metrics()
        state.login_limiter = RateLimiter(settings.login_limit, 60)
        state.request_limiter = RateLimiter(settings.request_limit, 60)
        state.accounts = Accounts(settings)
        state.coordinator = Coordinator(settings, state.database, state.catalog, state.gateway, state.images, state.metrics)
        state.chat = ChatService(state.database, state.gateway, settings)
        state.images.cleanup()
        state.database.purge_expired(settings.audit_retention_days)
        await state.coordinator.start()

        async def housekeeping():
            while True:
                await asyncio.sleep(3600)
                await asyncio.to_thread(state.images.cleanup)
                await asyncio.to_thread(state.database.purge_expired, settings.audit_retention_days)

        cleanup = asyncio.create_task(housekeeping())
        try:
            yield
        finally:
            cleanup.cancel()
            try:
                await cleanup
            except asyncio.CancelledError:
                pass
            await state.coordinator.stop()

    app = FastAPI(
        title="NTeam NutriTensor API", version="2.0.0",
        description="Private food-photo analysis with explicitly unverified ntemma model estimates; no food catalog gate for images.",
        lifespan=lifespan, docs_url="/api/docs" if settings.environment != "production" else None,
        redoc_url=None, openapi_url="/api/openapi.json" if settings.environment != "production" else None,
    )
    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.upload_limit_bytes + 65536)
    app.add_middleware(ResponseSecurityMiddleware)
    app.add_middleware(
        CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key", "Last-Event-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(settings.allowed_hosts))

    @app.middleware("http")
    async def telemetry(request: Request, call_next):
        started = time.perf_counter()
        # Health probes do not consume a user's request quota.
        if request.url.path not in {"/api/v1/health", "/api/v1/ready"}:
            ip = request.client.host if request.client else "unknown"
            decision = request.app.state.request_limiter.check(ip)
            if not decision.allowed:
                return JSONResponse(
                    {"error": "rate_limited", "message": "Too many requests. Please wait a moment."},
                    429, headers={"Retry-After": str(decision.retry_after)},
                )
        response = await call_next(request)
        route = request.scope.get("route")
        label = getattr(route, "path", "unmatched")
        request.app.state.metrics.requests.labels(route=label, status=str(response.status_code)).inc()
        request.app.state.metrics.request_seconds.labels(route=label).observe(time.perf_counter() - started)
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return JSONResponse({
            "error": exc.code, "message": exc.message,
            "request_id": getattr(request.state, "request_id", None),
        }, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Exclude user input and exception context from validation error responses.
        details = [{"location": list(error["loc"]), "message": error["msg"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse({"error": "validation_error", "message": "Please check the supplied fields", "details": details}, 422)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        logger.error("Request failed", extra={"error_code": type(exc).__name__, "request_id": getattr(request.state, "request_id", None)})
        return JSONResponse({"error": "internal_error", "message": "The request could not be completed. Retry or inspect the server error code."}, 500)

    app.include_router(router)
    return app
