#!/usr/bin/env python3
"""Show the last image-analysis failures from the private local SQLite database.

No GPU inference or API credentials are needed. Run from the project root.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from nutritensor.core.config import Settings


def main() -> None:
    settings = Settings.from_env()
    db = settings.database_path
    if not db.is_file():
        raise SystemExit(f"No database exists at {db}; check NTEAM_DATABASE_PATH")
    with sqlite3.connect(f"file:{db.resolve().as_posix()}?mode=ro", uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, status, error, created_at FROM jobs "
            "WHERE json_extract(request_json, '$.image_id') IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 5"
        ).fetchall()
        if not rows:
            print("No image-analysis jobs have been recorded yet.")
        for row in rows:
            print(f"\n{row['created_at']}  {row['id']}  {row['status']}")
            print("  Error:", row['error'] or "[none]")
            for event in connection.execute(
                "SELECT stage,state,message,detail_json FROM events WHERE job_id=? ORDER BY sequence DESC LIMIT 4",
                (row['id'],),
            ).fetchall()[::-1]:
                detail = json.loads(event['detail_json'] or '{}')
                print("  Stage:", event['stage'], event['state'], event['message'],
                      "error_code=" + str(detail.get('error_code', 'n/a')))


if __name__ == '__main__':
    main()
