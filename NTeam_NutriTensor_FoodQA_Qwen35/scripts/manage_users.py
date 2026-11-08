#!/usr/bin/env python3
"""Provision up to three private local users. No public registration endpoint."""

from __future__ import annotations

import argparse
import fcntl
import getpass
import json
import os
import secrets
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from nutritensor.core.accounts import MAX_LOCAL_USERS, USERNAME, LocalAccount, read_accounts
from nutritensor.core.security import hash_password


def update_accounts(path: Path, action: str, username: str, password: str = "", migrate_owner: bool = False) -> list[LocalAccount]:
    """Lock and atomically replace the account registry; never truncate it in place."""
    if not USERNAME.fullmatch(username):
        raise ValueError("Username must be 3–32 lowercase letters, digits, underscores or hyphens.")
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    with os.fdopen(lock_fd, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        users = read_accounts(path) if path.exists() else []
        current = next((a for a in users if a.username == username), None)
        if action == "add":
            if current:
                raise ValueError("Username already exists. Use reset-password.")
            if len(users) >= MAX_LOCAL_USERS:
                raise ValueError("This deployment permits at most three users.")
            if migrate_owner and users:
                raise ValueError("Only the first account can inherit the original owner's data.")
            owner = "local-owner" if migrate_owner else "user-" + secrets.token_hex(16)
        else:
            if not current:
                raise ValueError("Username does not exist.")
            owner = current.owner_id
            users.remove(current)
        if action != "remove":
            if not 12 <= len(password) <= 1024:
                raise ValueError("Use a password between 12 and 1,024 characters.")
            users.append(LocalAccount(username, owner, hash_password(password), datetime.now(timezone.utc).isoformat()))
        payload = json.dumps({"version": 1, "users": [asdict(a) for a in users]}, indent=2) + "\n"
        fd, temporary = tempfile.mkstemp(prefix=".users-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
            Path(temporary).replace(path)
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return users


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["add", "reset-password", "remove", "list"])
    parser.add_argument("username", nargs="?")
    parser.add_argument("--path", type=Path, help="Override NTEAM_USERS_PATH")
    parser.add_argument("--migrate-owner", action="store_true", help="First account inherits the v1 owner's journal")
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    path = args.path or Path(os.getenv("NTEAM_USERS_PATH", "data/users.json"))
    if args.action == "list":
        if not path.exists():
            print("Legacy owner account is active. Use add owner --migrate-owner to migrate it.")
        else:
            for user in read_accounts(path):
                print(user.username)
        return
    if not args.username:
        parser.error("A username is required")
    password = ""
    if args.action != "remove":
        password = getpass.getpass("Password (12+ characters): ")
        if password != getpass.getpass("Repeat password: "):
            raise SystemExit("Passwords do not match")
    try:
        users = update_accounts(path, args.action, args.username, password, args.migrate_owner)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        del password
    print(f"Updated. {len(users)}/{MAX_LOCAL_USERS} local accounts. Changes apply to the next request.")
    if args.action in {"reset-password", "remove"}:
        print("Previous sessions for this account are revoked. Stored meals are retained.")


if __name__ == "__main__":
    main()
