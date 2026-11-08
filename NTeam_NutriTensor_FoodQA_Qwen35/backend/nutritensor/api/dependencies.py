from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Request

from nutritensor.core.errors import Forbidden, Unauthorized
from nutritensor.core.security import token_digest


@dataclass(frozen=True)
class Principal:
    owner_id: str
    token_hash: str
    csrf_hash: str
    expires_at: str
    username: str = "owner"


def authenticate(request: Request) -> Principal:
    token = request.cookies.get("nteam_session")
    if not token:
        raise Unauthorized("Sign in to your local workspace")
    settings = request.app.state.settings
    hashed = token_digest(token, settings.session_secret)
    session = request.app.state.database.get_session(hashed)
    if not session:
        raise Unauthorized("Your workspace session expired. Sign in again.")
    account = None
    if not settings.is_demo:
        account = request.app.state.accounts.for_session(session)
        if not account:
            request.app.state.database.delete_session(hashed)
            raise Unauthorized("Your workspace session expired. Sign in again.")
    return Principal(
        owner_id=session["owner_id"], token_hash=hashed,
        csrf_hash=session["csrf_hash"], expires_at=session["expires_at"],
        username=account.username if account else "demo",
    )


def require_session(request: Request) -> Principal:
    principal = authenticate(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        csrf = request.headers.get("X-CSRF-Token", "")
        expected = token_digest(csrf, request.app.state.settings.session_secret)
        if not csrf or not hmac.compare_digest(expected, principal.csrf_hash):
            raise Forbidden("CSRF token missing or expired. Refresh your workspace.")
        origin = request.headers.get("Origin")
        if origin and origin not in request.app.state.settings.allowed_origins:
            raise Forbidden("This browser origin is not allowed")
    return principal
