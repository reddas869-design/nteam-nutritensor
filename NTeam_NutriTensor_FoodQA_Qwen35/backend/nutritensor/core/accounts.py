"""At most three local accounts; password changes revoke existing sessions."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from nutritensor.core.config import ConfigurationError, Settings
from nutritensor.core.security import hash_password, verify_password

MAX_LOCAL_USERS = 3
USERNAME = re.compile(r"^[a-z0-9][a-z0-9_-]{2,31}$")
PASSWORD_HASH = re.compile(r"^scrypt\$[a-f0-9]{32}\$[a-f0-9]{64}$")


@dataclass(frozen=True)
class LocalAccount:
    username: str
    owner_id: str
    password_hash: str
    updated_at: str


def read_accounts(path: Path) -> list[LocalAccount]:
    try:
        if path.stat().st_size > 32768:
            raise ValueError("Account file too large")
        raw = json.loads(path.read_text(encoding="utf-8"))
        rows = raw["users"]
        if raw.get("version") != 1 or not isinstance(rows, list) or not 0 <= len(rows) <= MAX_LOCAL_USERS:
            raise ValueError("Invalid account format")
        accounts = [LocalAccount(**row) for row in rows]
        for account in accounts:
            timestamp = datetime.fromisoformat(account.updated_at)
            if (not USERNAME.fullmatch(account.username)
                    or not re.fullmatch(r"[A-Za-z0-9_-]{3,100}", account.owner_id)
                    or not PASSWORD_HASH.fullmatch(account.password_hash)
                    or timestamp.tzinfo is None):
                raise ValueError("Invalid account")
        if len({a.username for a in accounts}) != len(accounts) or len({a.owner_id for a in accounts}) != len(accounts):
            raise ValueError("Duplicate account")
        return accounts
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        raise ConfigurationError("Local account file is invalid or unavailable") from exc


class Accounts:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.file_mode = settings.users_path.exists()
        self.dummy_hash = hash_password(secrets.token_urlsafe(32))
        self.legacy_hash = settings.admin_password_hash or hash_password(settings.admin_password)
        if self.file_mode:
            read_accounts(settings.users_path)

    def all(self) -> list[LocalAccount]:
        if self.file_mode or self.settings.users_path.exists():
            self.file_mode = True
            return read_accounts(self.settings.users_path)
        return [LocalAccount("owner", "local-owner", self.legacy_hash, datetime(1970, 1, 1, tzinfo=timezone.utc).isoformat())]

    def verify(self, username: str, password: str) -> LocalAccount | None:
        account = next((a for a in self.all() if a.username == username.strip().lower()), None)
        valid = verify_password(password, account.password_hash if account else self.dummy_hash)
        return account if valid else None

    def for_session(self, session: dict) -> LocalAccount | None:
        account = next((a for a in self.all() if a.owner_id == session["owner_id"]), None)
        if account and datetime.fromisoformat(session["created_at"]) >= datetime.fromisoformat(account.updated_at):
            return account
        return None
