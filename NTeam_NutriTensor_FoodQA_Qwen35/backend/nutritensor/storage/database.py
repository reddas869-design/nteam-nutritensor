"""SQLite repository. All owner checks live at the query boundary."""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from nutritensor.core.errors import Conflict, NotFound
from nutritensor.domain.models import (
    AnalysisRequest, AnalysisResult, JobEvent, JobStatus, JobView,
    JournalEntry, JournalUpdate, Preferences, Recipe, Stage,
)


SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    csrf_hash TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('queued','running','complete','failed','cancelled')),
    request_json TEXT NOT NULL,
    result_json TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    idempotency_key TEXT,
    UNIQUE(owner_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS jobs_owner_created ON jobs(owner_id, created_at DESC);
CREATE TABLE IF NOT EXISTS events (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    state TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    progress REAL NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS events_job_sequence ON events(job_id, sequence);
CREATE TABLE IF NOT EXISTS images (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS images_expiry ON images(created_at);
CREATE TABLE IF NOT EXISTS journal (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    analysis_id TEXT NOT NULL,
    meal_name TEXT NOT NULL,
    meal_type TEXT NOT NULL,
    eaten_at TEXT NOT NULL,
    notes TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(owner_id, analysis_id)
);
CREATE INDEX IF NOT EXISTS journal_owner_time ON journal(owner_id, eaten_at DESC);
CREATE TABLE IF NOT EXISTS preferences (
    owner_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recipes (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_id TEXT,
    timestamp TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_time ON audit(timestamp);
"""


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def identifier() -> str:
    return uuid.uuid4().hex


class Database:
    def __init__(self, path: Path):
        self.path = path
        self._write_lock = threading.RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connection(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=15000")
        try:
            if write:
                with self._write_lock:
                    connection.execute("BEGIN IMMEDIATE")
                    yield connection
                    connection.commit()
            else:
                yield connection
        except BaseException:
            if write:
                connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with sqlite3.connect(self.path) as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.executescript(SCHEMA)
            maximum = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if maximum is not None and maximum > SCHEMA_VERSION:
                raise RuntimeError("Database schema is newer than this application")
            connection.execute(
                "INSERT OR IGNORE INTO schema_version VALUES (?,?)", (SCHEMA_VERSION, timestamp())
            )
        self.path.chmod(0o600)

    def create_session(self, token_hash: str, owner_id: str, csrf_hash: str, expires_at: str) -> None:
        with self.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO sessions VALUES (?,?,?,?,?)",
                (token_hash, owner_id, csrf_hash, expires_at, timestamp()),
            )

    def get_session(self, token_hash: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE token_hash=? AND expires_at>?", (token_hash, timestamp())
            ).fetchone()
            return dict(row) if row else None

    def rotate_csrf(self, token_hash: str, csrf_hash: str) -> None:
        with self.connection(write=True) as connection:
            connection.execute("UPDATE sessions SET csrf_hash=? WHERE token_hash=?", (csrf_hash, token_hash))

    def delete_session(self, token_hash: str) -> None:
        with self.connection(write=True) as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash=?", (token_hash,))

    def recover_interrupted_jobs(self) -> int:
        with self.connection(write=True) as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status='failed',error=?,updated_at=? WHERE status IN ('running','queued')",
                ("The service restarted before this analysis completed. Please retry.", timestamp()),
            )
            return cursor.rowcount

    def create_job(self, owner: str, request: AnalysisRequest, key: str | None = None) -> tuple[str, bool]:
        with self.connection(write=True) as connection:
            if key:
                row = connection.execute(
                    "SELECT id,request_json FROM jobs WHERE owner_id=? AND idempotency_key=?", (owner, key)
                ).fetchone()
                if row:
                    if json.loads(row["request_json"]) != request.model_dump(mode="json"):
                        raise Conflict("Idempotency key was already used for different input")
                    return row["id"], False
            job_id = identifier()
            now = timestamp()
            connection.execute(
                "INSERT INTO jobs(id,owner_id,status,request_json,created_at,updated_at,idempotency_key) "
                "VALUES(?,?,?,?,?,?,?)",
                (job_id, owner, "queued", request.model_dump_json(), now, now, key),
            )
            return job_id, True

    def get_job(self, job_id: str, owner: str) -> JobView:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id=? AND owner_id=?", (job_id, owner)).fetchone()
        if not row:
            raise NotFound("Analysis not found")
        return self._job_view(row, self.events(job_id, owner))

    def _job_view(self, row: sqlite3.Row, events: list[JobEvent]) -> JobView:
        return JobView(
            id=row["id"], status=JobStatus(row["status"]), created_at=row["created_at"],
            updated_at=row["updated_at"], error=row["error"], events=events,
            result=AnalysisResult.model_validate_json(row["result_json"]) if row["result_json"] else None,
        )

    def list_jobs(self, owner: str, limit: int = 30, offset: int = 0) -> list[JobView]:
        with self.connection() as connection:
            rows = connection.execute(
                "SELECT * FROM jobs WHERE owner_id=? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (owner, min(limit, 100), offset),
            ).fetchall()
        return [self._job_view(row, []) for row in rows]

    def set_status(self, job_id: str, status: JobStatus, error: str | None = None) -> bool:
        with self.connection(write=True) as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status=?,error=?,updated_at=? WHERE id=? "
                "AND status IN ('queued','running')",
                (status.value, error, timestamp(), job_id),
            )
            return cursor.rowcount == 1

    def complete_job(self, job_id: str, result: AnalysisResult) -> bool:
        with self.connection(write=True) as connection:
            cursor = connection.execute(
                "UPDATE jobs SET status='complete',result_json=?,error=NULL,updated_at=? "
                "WHERE id=? AND status='running'",
                (result.model_dump_json(), timestamp(), job_id),
            )
            return cursor.rowcount == 1

    def append_event(
        self, job_id: str, stage: Stage, state: str, message: str, progress: float, detail: dict | None = None,
    ) -> JobEvent:
        now = timestamp()
        with self.connection(write=True) as connection:
            cursor = connection.execute(
                "INSERT INTO events(job_id,stage,state,message,timestamp,progress,detail_json) VALUES(?,?,?,?,?,?,?)",
                (job_id, stage.value, state, message, now, progress, json.dumps(detail or {})),
            )
            sequence = cursor.lastrowid
        return JobEvent(
            sequence=sequence, job_id=job_id, stage=stage, state=state, message=message,
            timestamp=now, progress=progress, detail=detail or {},
        )

    def events(self, job_id: str, owner: str, after: int = 0) -> list[JobEvent]:
        with self.connection() as connection:
            exists = connection.execute("SELECT 1 FROM jobs WHERE id=? AND owner_id=?", (job_id, owner)).fetchone()
            if not exists:
                raise NotFound("Analysis not found")
            rows = connection.execute(
                "SELECT * FROM events WHERE job_id=? AND sequence>? ORDER BY sequence LIMIT 1000", (job_id, after)
            ).fetchall()
        return [JobEvent(
            sequence=row["sequence"], job_id=job_id, stage=row["stage"], state=row["state"],
            message=row["message"], timestamp=row["timestamp"], progress=row["progress"],
            detail=json.loads(row["detail_json"]),
        ) for row in rows]

    def store_image(self, owner: str, image_id: str, relative: str, width: int, height: int, digest: str) -> None:
        with self.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO images VALUES(?,?,?,?,?,?,?)", (image_id, owner, relative, width, height, digest, timestamp())
            )

    def get_image(self, image_id: str, owner: str) -> dict:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM images WHERE id=? AND owner_id=?", (image_id, owner)).fetchone()
        if not row:
            raise NotFound("Image not found or expired")
        return dict(row)

    def delete_image(self, image_id: str, owner: str) -> str:
        record = self.get_image(image_id, owner)
        with self.connection(write=True) as connection:
            connection.execute("DELETE FROM images WHERE id=? AND owner_id=?", (image_id, owner))
        return record["relative_path"]

    def expired_images(self, before: str) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM images WHERE created_at<?", (before,)).fetchall()
        return [dict(row) for row in rows]

    def add_journal(self, owner: str, result: AnalysisResult, eaten_at: str, notes: str) -> JournalEntry:
        if result.needs_confirmation:
            raise Conflict("Confirm food identity and portions before saving this meal")
        with self.connection(write=True) as connection:
            existing = connection.execute(
                "SELECT * FROM journal WHERE owner_id=? AND analysis_id=?", (owner, result.id)
            ).fetchone()
            if existing:
                return self._journal(existing)
            entry_id = identifier()
            connection.execute(
                "INSERT INTO journal VALUES(?,?,?,?,?,?,?,?,?)",
                (entry_id, owner, result.id, result.meal_name, result.meal_type, eaten_at, notes,
                 result.model_dump_json(), timestamp()),
            )
        return self.get_journal(owner, entry_id)

    def _journal(self, row: sqlite3.Row) -> JournalEntry:
        return JournalEntry(
            id=row["id"], analysis_id=row["analysis_id"], meal_name=row["meal_name"],
            meal_type=row["meal_type"], eaten_at=row["eaten_at"], notes=row["notes"],
            result=AnalysisResult.model_validate_json(row["result_json"]),
        )

    def get_journal(self, owner: str, entry_id: str) -> JournalEntry:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM journal WHERE id=? AND owner_id=?", (entry_id, owner)).fetchone()
        if not row:
            raise NotFound("Journal entry not found")
        return self._journal(row)

    def list_journal(
        self, owner: str, start: str | None = None, end: str | None = None, limit: int = 100, offset: int = 0,
    ) -> list[JournalEntry]:
        query = "SELECT * FROM journal WHERE owner_id=?"
        parameters: list[Any] = [owner]
        if start:
            query += " AND eaten_at>=?"
            parameters.append(start)
        if end:
            query += " AND eaten_at<?"
            parameters.append(end)
        query += " ORDER BY eaten_at DESC LIMIT ? OFFSET ?"
        parameters.extend([min(limit, 1000), offset])
        with self.connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._journal(row) for row in rows]

    def update_journal(self, owner: str, entry_id: str, patch: JournalUpdate) -> JournalEntry:
        self.get_journal(owner, entry_id)
        values = patch.model_dump(exclude_none=True, mode="json")
        if values:
            assignments = ",".join(f"{name}=?" for name in values)
            with self.connection(write=True) as connection:
                connection.execute(
                    f"UPDATE journal SET {assignments} WHERE id=? AND owner_id=?",
                    [*values.values(), entry_id, owner],
                )
        return self.get_journal(owner, entry_id)

    def delete_journal(self, owner: str, entry_id: str) -> None:
        with self.connection(write=True) as connection:
            cursor = connection.execute("DELETE FROM journal WHERE id=? AND owner_id=?", (entry_id, owner))
            if not cursor.rowcount:
                raise NotFound("Journal entry not found")

    def preferences(self, owner: str) -> Preferences:
        with self.connection() as connection:
            row = connection.execute("SELECT payload FROM preferences WHERE owner_id=?", (owner,)).fetchone()
        return Preferences.model_validate_json(row["payload"]) if row else Preferences()

    def save_preferences(self, owner: str, preferences: Preferences) -> Preferences:
        with self.connection(write=True) as connection:
            connection.execute(
                "INSERT INTO preferences VALUES(?,?,?) ON CONFLICT(owner_id) DO UPDATE "
                "SET payload=excluded.payload,updated_at=excluded.updated_at",
                (owner, preferences.model_dump_json(), timestamp()),
            )
        return preferences

    def save_recipe(self, owner: str, recipe: Recipe) -> Recipe:
        with self.connection(write=True) as connection:
            connection.execute("INSERT INTO recipes VALUES(?,?,?,?)", (recipe.id, owner, recipe.model_dump_json(), timestamp()))
        return recipe

    def list_recipes(self, owner: str) -> list[Recipe]:
        with self.connection() as connection:
            rows = connection.execute("SELECT payload FROM recipes WHERE owner_id=? ORDER BY created_at DESC LIMIT 500", (owner,)).fetchall()
        return [Recipe.model_validate_json(row["payload"]) for row in rows]

    def delete_recipe(self, owner: str, recipe_id: str) -> None:
        with self.connection(write=True) as connection:
            cursor = connection.execute("DELETE FROM recipes WHERE owner_id=? AND id=?", (owner, recipe_id))
            if not cursor.rowcount:
                raise NotFound("Recipe not found")

    def audit(self, owner: str, action: str, resource_id: str | None = None) -> None:
        with self.connection(write=True) as connection:
            connection.execute("INSERT INTO audit(owner_id,action,resource_id,timestamp) VALUES(?,?,?,?)", (owner, action, resource_id, timestamp()))

    def purge_expired(self, audit_days: int = 30) -> None:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=audit_days)).isoformat()
        with self.connection(write=True) as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at<?", (timestamp(),))
            connection.execute("DELETE FROM audit WHERE timestamp<?", (cutoff,))

    def erase_owner(self, owner: str) -> list[str]:
        with self.connection(write=True) as connection:
            paths = [row[0] for row in connection.execute("SELECT relative_path FROM images WHERE owner_id=?", (owner,))]
            for table in ("images", "journal", "jobs", "preferences", "recipes", "audit", "sessions"):
                connection.execute(f"DELETE FROM {table} WHERE owner_id=?", (owner,))
        return paths

    def backup(self, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as source:
            with sqlite3.connect(destination) as target:
                source.backup(target)
        destination.chmod(0o600)
