"""ASGI request guards that enforce byte limits even without Content-Length."""

from __future__ import annotations

import json
import time
import uuid

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            await JSONResponse({"error": "invalid_length", "message": "Invalid Content-Length"}, 400)(scope, receive, send)
            return
        if declared > self.max_bytes:
            await JSONResponse({"error": "payload_too_large", "message": "Request exceeds upload limit"}, 413)(scope, receive, send)
            return
        # Buffer a bounded body once; downstream form parsing cannot bypass this bound.
        chunks: list[bytes] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            total += len(body)
            if total > self.max_bytes:
                await JSONResponse({"error": "payload_too_large", "message": "Request exceeds upload limit"}, 413)(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        consumed = False

        async def replay() -> Message:
            nonlocal consumed
            if not consumed:
                consumed = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class ResponseSecurityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id

        async def secured(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"same-origin"),
                    (b"x-frame-options", b"DENY"),
                    (b"x-request-id", request_id.encode()),
                    (b"cache-control", b"no-store"),
                ])
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, secured)
