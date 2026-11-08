from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nutritensor.core.config import Settings
from nutritensor.main import create_app
from nutritensor.nutrition.demo import demo_catalog
from nutritensor.storage.database import Database


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_path=tmp_path / "workspace.sqlite3",
        uploads_path=tmp_path / "images",
        catalog_path=tmp_path / "foods.json",
        users_path=tmp_path / "users.json",
        request_limit=1000,
    )


@pytest.fixture
def catalog():
    return demo_catalog()


@pytest.fixture
def database(tmp_path: Path):
    return Database(tmp_path / "repository.sqlite3")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client


@pytest.fixture
def session(client):
    response = client.post("/api/v1/session", json={})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


@pytest.fixture
def meal_request():
    return {
        "items": [
            {"food_id": "demo:rice", "grams": 150, "portion_source": "weighed", "uncertainty_percent": 2},
            {"food_id": "demo:chicken", "grams": 120, "portion_source": "weighed", "uncertainty_percent": 2},
        ],
        "meal_name": "A simple lunch",
        "meal_type": "lunch",
        "confirmed": True,
    }


def wait_for_job(client, job_id: str, timeout: float = 5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/analyses/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] not in {"queued", "running"}:
            return job
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} failed to finish within {timeout} seconds")


def completed_job(client, headers, payload):
    response = client.post("/api/v1/analyses", json=payload, headers=headers)
    assert response.status_code == 202, response.text
    job = wait_for_job(client, response.json()["id"])
    assert job["status"] == "complete", job
    return job
