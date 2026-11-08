from __future__ import annotations

import json
from dataclasses import replace
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from nutritensor.core.accounts import Accounts
from nutritensor.core.config import ConfigurationError
from nutritensor.main import create_app
from scripts.manage_users import update_accounts

PASSWORD = "a-long-test-password-123"


def provision(settings, tmp_path):
    path = tmp_path / "users.json"
    for index, name in enumerate(["alice", "bravo", "charlie"]):
        update_accounts(path, "add", name, PASSWORD, migrate_owner=index == 0)
    return replace(settings, users_path=path, mode="live", model_backend="openai-compatible")


def test_three_accounts_and_fourth_is_rejected(settings, tmp_path):
    configured = provision(settings, tmp_path)
    before = configured.users_path.read_bytes()
    with pytest.raises(ValueError, match="at most three"):
        update_accounts(configured.users_path, "add", "delta", PASSWORD)
    assert configured.users_path.read_bytes() == before
    assert configured.users_path.stat().st_mode & 0o777 == 0o600
    accounts = Accounts(configured)
    assert accounts.verify("ALICE", PASSWORD).owner_id == "local-owner"
    assert accounts.verify("alice", "wrong") is None
    assert accounts.verify("unknown", PASSWORD) is None
    assert len({a.owner_id for a in accounts.all()}) == 3


def test_password_reset_and_removal_revoke_existing_session(settings, tmp_path):
    configured = provision(settings, tmp_path)
    accounts = Accounts(configured)
    alice = accounts.verify("alice", PASSWORD)
    old_session = {"owner_id": alice.owner_id, "created_at": datetime.now(timezone.utc).isoformat()}
    assert accounts.for_session(old_session)
    update_accounts(configured.users_path, "reset-password", "alice", "a-different-long-password")
    assert accounts.for_session(old_session) is None
    assert accounts.verify("alice", PASSWORD) is None
    assert accounts.verify("alice", "a-different-long-password")
    update_accounts(configured.users_path, "remove", "bravo")
    assert accounts.verify("bravo", PASSWORD) is None
    update_accounts(configured.users_path, "add", "delta", PASSWORD)
    assert len(accounts.all()) == 3


def test_missing_account_file_does_not_restore_legacy_password(settings, tmp_path):
    configured = provision(settings, tmp_path)
    accounts = Accounts(configured)
    configured.users_path.unlink()
    with pytest.raises(ConfigurationError):
        accounts.verify("owner", "")


@pytest.mark.parametrize("case", ["too_many", "duplicate_owner", "naive_time", "bad_hash"])
def test_invalid_registry_fails_closed(settings, tmp_path, case):
    configured = provision(settings, tmp_path)
    payload = json.loads(configured.users_path.read_text())
    if case == "too_many":
        payload["users"].append(payload["users"][0])
    elif case == "duplicate_owner":
        payload["users"][1]["owner_id"] = payload["users"][0]["owner_id"]
    elif case == "naive_time":
        payload["users"][0]["updated_at"] = "2026-01-01T00:00:00"
    else:
        payload["users"][0]["password_hash"] = "plaintext"
    configured.users_path.write_text(json.dumps(payload))
    with pytest.raises(ConfigurationError):
        Accounts(configured)


def test_live_accounts_have_private_preferences_and_revocable_sessions(settings, tmp_path):
    configured = provision(settings, tmp_path)
    with TestClient(create_app(configured)) as client:
        def login(name):
            response = client.post("/api/v1/session", json={"username": name, "password": PASSWORD})
            assert response.status_code == 200
            assert response.json()["username"] == name
            return {"X-CSRF-Token": response.json()["csrf_token"]}
        alice_headers = login("alice")
        assert client.put("/api/v1/preferences", json={"timezone": "Asia/Dhaka"}, headers=alice_headers).status_code == 200
        login("bravo")
        assert client.get("/api/v1/preferences").json()["timezone"] != "Asia/Dhaka"
        login("alice")
        assert client.get("/api/v1/preferences").json()["timezone"] == "Asia/Dhaka"
        update_accounts(configured.users_path, "remove", "alice")
        assert client.get("/api/v1/session").status_code == 401
        assert client.post("/api/v1/session", json={"username": "alice", "password": PASSWORD}).status_code == 401
