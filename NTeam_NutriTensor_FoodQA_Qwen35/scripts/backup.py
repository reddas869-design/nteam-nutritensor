#!/usr/bin/env python3
"""Create a consistent SQLite backup using SQLite's online backup API."""

import argparse
from datetime import datetime, timezone
from pathlib import Path

from nutritensor.core.config import Settings
from nutritensor.storage.database import Database


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = Settings.from_env()
    if not settings.database_path.exists():
        raise SystemExit("No database exists at the configured path")
    name = datetime.now(timezone.utc).strftime("nutritensor-%Y%m%dT%H%M%SZ.sqlite3")
    destination = args.output or Path("backups") / name
    if destination.exists():
        raise SystemExit("Backup destination already exists; choose a new path")
    Database(settings.database_path).backup(destination)
    print(f"Consistent database snapshot saved to {destination}")
    print("Protect this backup: it contains private journal and session data. Images and model weights are separate.")


if __name__ == "__main__":
    main()
