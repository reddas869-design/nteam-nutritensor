"""Authenticated application routes. GPU work runs through the coordinator."""

from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Header, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from nutritensor.api.dependencies import Principal, authenticate, require_session
from nutritensor.core.errors import Conflict, Forbidden, NotFound, Unauthorized
from nutritensor.core.security import new_token, token_digest
from nutritensor.domain.models import (
    AnalysisRequest, ChatRequest, JobStatus, JournalCreate, JournalUpdate,
    LoginRequest, Preferences, RecipeCreate, SessionView,
)
from nutritensor.nutrition.calculator import build_recipe
from nutritensor.services.journal import date_bounds, export_account, export_csv, summarize
from nutritensor.services.labels import parse_label, read_label


router = APIRouter(prefix="/api/v1")
Auth = Annotated[Principal, Depends(require_session)]


@router.get("/health")
async def health(request: Request):
    return {"status": "ok", "version": "2.0.0", "mode": request.app.state.settings.mode}


@router.get("/ready")
async def readiness(request: Request, response: Response):
    # A local multimodal model can scan food without any custom nutrition catalog.
    catalog_ready = len(request.app.state.catalog) > 0
    capabilities = request.app.state.provider.capabilities()
    model_only_ready = (request.app.state.settings.mode == "live" and capabilities.vision)
    ready = catalog_ready or model_only_ready
    if not ready:
        response.status_code = 503
    return {"ready": ready, "catalog_ready": catalog_ready, "model_only_ready": model_only_ready,
            "model_loaded": capabilities.loaded}


@router.post("/session", response_model=SessionView)
async def login(payload: LoginRequest, request: Request, response: Response):
    state = request.app.state
    origin = request.headers.get("Origin")
    if origin and origin not in state.settings.allowed_origins:
        raise Forbidden("This browser origin is not allowed")
    ip = request.client.host if request.client else "unknown"
    decision = state.login_limiter.check(ip)
    if not decision.allowed:
        from fastapi import HTTPException
        raise HTTPException(429, "Too many sign-in attempts", headers={"Retry-After": str(decision.retry_after)})
    account = None
    if not state.settings.is_demo:
        account = await asyncio.to_thread(state.accounts.verify, payload.username, payload.password)
        if not account:
            raise Unauthorized("The username or password is incorrect")
    token, csrf = new_token(), new_token()
    expires = datetime.now(timezone.utc) + timedelta(hours=state.settings.session_ttl_hours)
    owner = account.owner_id if account else f"demo-{new_token()}"
    state.database.create_session(
        token_digest(token, state.settings.session_secret), owner,
        token_digest(csrf, state.settings.session_secret), expires.isoformat(),
    )
    response.set_cookie(
        "nteam_session", token, httponly=True, secure=state.settings.cookie_secure,
        samesite="strict", max_age=state.settings.session_ttl_hours * 3600, path="/api",
    )
    state.login_limiter.clear(ip)
    return SessionView(authenticated=True, username=account.username if account else "demo", csrf_token=csrf, mode=state.settings.mode, expires_at=expires.isoformat())


@router.get("/session", response_model=SessionView)
async def session(request: Request):
    principal = authenticate(request)
    csrf = new_token()
    request.app.state.database.rotate_csrf(
        principal.token_hash, token_digest(csrf, request.app.state.settings.session_secret)
    )
    return SessionView(
        authenticated=True, csrf_token=csrf, mode=request.app.state.settings.mode, expires_at=principal.expires_at,
        username=principal.username,
    )


@router.delete("/session", status_code=204)
async def logout(request: Request, response: Response, principal: Auth):
    request.app.state.database.delete_session(principal.token_hash)
    response.delete_cookie("nteam_session", path="/api")


@router.get("/capabilities")
async def capabilities(request: Request, principal: Auth):
    result = request.app.state.provider.capabilities()
    result.catalog_count = len(request.app.state.catalog)
    result.catalog_version = request.app.state.catalog.version
    return result


@router.get("/foods")
async def foods(
    request: Request, principal: Auth, q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50), category: str | None = Query(default=None, max_length=80),
):
    return {"items": request.app.state.catalog.search(q, limit, category), "catalog_version": request.app.state.catalog.version}


@router.get("/foods/categories")
async def categories(request: Request, principal: Auth):
    return {"items": request.app.state.catalog.categories()}


@router.get("/foods/{food_id}")
async def food(food_id: str, request: Request, principal: Auth):
    return request.app.state.catalog.get(food_id)


@router.post("/images", status_code=201)
async def upload(request: Request, principal: Auth, file: UploadFile = File(...)):
    limit = request.app.state.settings.upload_limit_bytes
    content = await file.read(limit + 1)
    await file.close()
    result = await asyncio.to_thread(request.app.state.images.save, principal.owner_id, content)
    request.app.state.database.audit(principal.owner_id, "image_uploaded", result["id"])
    return result


@router.get("/images/{image_id}")
async def image(image_id: str, request: Request, principal: Auth):
    path = request.app.state.images.path(principal.owner_id, image_id)
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.delete("/images/{image_id}", status_code=204)
async def remove_image(image_id: str, request: Request, principal: Auth):
    if request.app.state.coordinator.owner_busy(principal.owner_id):
        raise Conflict("Wait for or cancel the current analysis before deleting images")
    request.app.state.images.remove(principal.owner_id, image_id)


@router.post("/images/{image_id}/label")
async def image_label(image_id: str, request: Request, principal: Auth):
    path = request.app.state.images.path(principal.owner_id, image_id)
    return await asyncio.to_thread(read_label, path, request.app.state.settings.enable_ocr)


@router.post("/labels/parse")
async def label_text(payload: dict, request: Request, principal: Auth):
    text = payload.get("text", "")
    if not isinstance(text, str) or len(text) > 10000:
        raise Conflict("Label text must be at most 10,000 characters")
    return parse_label(text)


@router.post("/analyses", status_code=202)
async def create_analysis(
    payload: AnalysisRequest, request: Request, principal: Auth,
    idempotency_key: str | None = Header(default=None, max_length=120),
):
    job_id = request.app.state.coordinator.submit(principal.owner_id, payload, idempotency_key)
    return {"id": job_id, "status_url": f"/api/v1/analyses/{job_id}", "events_url": f"/api/v1/analyses/{job_id}/events"}


@router.get("/analyses")
async def list_analyses(request: Request, principal: Auth, limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0)):
    return {"items": request.app.state.database.list_jobs(principal.owner_id, limit, offset)}


@router.get("/analyses/{job_id}")
async def analysis(job_id: str, request: Request, principal: Auth):
    return request.app.state.database.get_job(job_id, principal.owner_id)


@router.post("/analyses/{job_id}/cancel", status_code=202)
async def cancel_analysis(job_id: str, request: Request, principal: Auth):
    request.app.state.coordinator.cancel(principal.owner_id, job_id)
    return {"status": "cancellation_requested"}


@router.get("/analyses/{job_id}/events")
async def stream_events(
    job_id: str, request: Request, principal: Auth,
    last_event_id: str | None = Header(default=None), after: int = Query(default=0, ge=0),
):
    request.app.state.database.get_job(job_id, principal.owner_id)
    try:
        sequence = max(after, int(last_event_id or 0))
    except ValueError:
        sequence = after

    async def stream():
        nonlocal sequence
        idle_ticks = 0
        while not await request.is_disconnected():
            events = request.app.state.database.events(job_id, principal.owner_id, sequence)
            for event in events:
                sequence = event.sequence
                yield f"id: {sequence}\nevent: progress\ndata: {event.model_dump_json()}\n\n"
            job = request.app.state.database.get_job(job_id, principal.owner_id)
            if job.status not in {JobStatus.QUEUED, JobStatus.RUNNING}:
                yield f"event: finished\ndata: {json.dumps({'status': job.status.value})}\n\n"
                return
            idle_ticks += 1
            if idle_ticks % 20 == 0:
                yield ": heartbeat\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@router.post("/journal", status_code=201)
async def save_meal(payload: JournalCreate, request: Request, principal: Auth):
    job = request.app.state.database.get_job(payload.analysis_id, principal.owner_id)
    if job.status != JobStatus.COMPLETE or not job.result:
        raise Conflict("Only complete analyses can be saved")
    return request.app.state.database.add_journal(
        principal.owner_id, job.result, payload.eaten_at.isoformat(), payload.notes,
    )


@router.get("/journal")
async def journal(
    request: Request, principal: Auth, limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
    start: date | None = None, end: date | None = None,
):
    first, last = None, None
    if start and end:
        if end < start or (end - start).days > 366:
            raise Conflict("Choose a date range of at most 367 days")
        preferences = request.app.state.database.preferences(principal.owner_id)
        first, last = date_bounds(start, end, preferences.timezone)
    return {"items": request.app.state.database.list_journal(principal.owner_id, first, last, limit, offset)}


@router.patch("/journal/{entry_id}")
async def edit_journal(entry_id: str, payload: JournalUpdate, request: Request, principal: Auth):
    return request.app.state.database.update_journal(principal.owner_id, entry_id, payload)


@router.delete("/journal/{entry_id}", status_code=204)
async def delete_journal(entry_id: str, request: Request, principal: Auth):
    request.app.state.database.delete_journal(principal.owner_id, entry_id)


@router.get("/summary")
async def summary(request: Request, principal: Auth, start: date, end: date):
    if end < start or (end - start).days > 90:
        raise Conflict("Choose a summary range of at most 91 days")
    preferences = request.app.state.database.preferences(principal.owner_id)
    first, last = date_bounds(start, end, preferences.timezone)
    entries = []
    offset = 0
    while True:
        page = request.app.state.database.list_journal(principal.owner_id, first, last, 1000, offset)
        entries.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return summarize(entries, preferences.timezone, start, end)


@router.get("/preferences")
async def preferences(request: Request, principal: Auth):
    return request.app.state.database.preferences(principal.owner_id)


@router.put("/preferences")
async def set_preferences(payload: Preferences, request: Request, principal: Auth):
    return request.app.state.database.save_preferences(principal.owner_id, payload)


@router.get("/recipes")
async def recipes(request: Request, principal: Auth):
    return {"items": request.app.state.database.list_recipes(principal.owner_id)}


@router.post("/recipes", status_code=201)
async def create_recipe(payload: RecipeCreate, request: Request, principal: Auth):
    result = build_recipe(request.app.state.catalog, payload)
    return request.app.state.database.save_recipe(principal.owner_id, result)


@router.delete("/recipes/{recipe_id}", status_code=204)
async def delete_recipe(recipe_id: str, request: Request, principal: Auth):
    request.app.state.database.delete_recipe(principal.owner_id, recipe_id)


@router.post("/chat")
async def chat(payload: ChatRequest, request: Request, principal: Auth):
    return await request.app.state.chat.answer(principal.owner_id, payload)


@router.get("/export")
async def export(request: Request, principal: Auth, format: str = Query(default="json", pattern="^(json|csv)$")):
    payload = export_account(request.app.state.database, principal.owner_id)
    request.app.state.database.audit(principal.owner_id, "export")
    if format == "csv":
        from nutritensor.domain.models import JournalEntry
        content = export_csv([JournalEntry.model_validate(item) for item in payload["journal"]])
        media = "text/csv"
    else:
        content = json.dumps(payload, ensure_ascii=False, indent=2)
        media = "application/json"
    return Response(content, media_type=media, headers={
        "Content-Disposition": f'attachment; filename="nutritensor-export.{format}"',
        "Cache-Control": "no-store",
    })


@router.delete("/account", status_code=204)
async def erase_account(request: Request, response: Response, principal: Auth):
    if request.app.state.coordinator.owner_busy(principal.owner_id):
        raise Conflict("Cancel pending analyses and wait for completion before deleting workspace data")
    paths = request.app.state.database.erase_owner(principal.owner_id)
    directory = request.app.state.settings.uploads_path.resolve()
    for relative in paths:
        path = (directory / relative).resolve()
        if path.parent == directory:
            path.unlink(missing_ok=True)
    response.delete_cookie("nteam_session", path="/api")


@router.get("/metrics")
async def metrics(request: Request, principal: Auth):
    return Response(request.app.state.metrics.render(), media_type="text/plain; version=0.0.4")
