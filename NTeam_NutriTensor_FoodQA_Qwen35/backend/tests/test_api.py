from __future__ import annotations

import json
from datetime import datetime, timezone

from conftest import completed_job, wait_for_job
from test_security_and_images import image_bytes


def test_unauthenticated_routes_do_not_leak_workspace(client):
    assert client.get("/api/v1/health").status_code == 200
    for path in ("/api/v1/foods", "/api/v1/journal", "/api/v1/recipes", "/api/v1/preferences", "/api/v1/metrics"):
        assert client.get(path).status_code == 401


def test_csrf_rejects_writes_and_untrusted_origins(client, session, meal_request):
    assert client.post("/api/v1/analyses", json=meal_request).status_code == 403
    bad = {**session, "Origin": "https://untrusted.example"}
    assert client.post("/api/v1/analyses", json=meal_request, headers=bad).status_code == 403
    assert client.post("/api/v1/session", json={}, headers={"Origin": "https://untrusted.example"}).status_code == 403


def test_complete_meal_flow_with_sources_and_persistence(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    result = job["result"]
    assert result["totals"]["energy_kcal"] == 393
    assert result["mode"] == "demo"
    assert not result["needs_confirmation"]
    assert result["portions"][0]["food"]["source"]["is_demo"]
    assert result["stats"]["tokens_per_second"] is None
    response = client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"]})
    assert response.status_code == 201, response.text
    saved = response.json()
    again = client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"]})
    assert again.json()["id"] == saved["id"]
    assert len(client.get("/api/v1/journal").json()["items"]) == 1
    changed = client.patch(f'/api/v1/journal/{saved["id"]}', headers=session, json={"meal_name": "Lunch after class", "notes": "Weighed portions"})
    assert changed.status_code == 200
    assert changed.json()["meal_name"] == "Lunch after class"
    assert changed.json()["result"]["totals"]["energy_kcal"] == 393
    assert client.delete(f'/api/v1/journal/{saved["id"]}', headers=session).status_code == 204
    assert client.get("/api/v1/journal").json()["items"] == []


def test_unconfirmed_meal_cannot_be_saved(client, session, meal_request):
    meal_request["confirmed"] = False
    job = completed_job(client, session, meal_request)
    assert client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"]}).status_code == 409


def test_idempotency_returns_existing_job_and_conflicts_on_changed_input(client, session, meal_request):
    headers = {**session, "Idempotency-Key": "retry-safe-key"}
    first = client.post("/api/v1/analyses", json=meal_request, headers=headers)
    second = client.post("/api/v1/analyses", json=meal_request, headers=headers)
    assert first.json()["id"] == second.json()["id"]
    meal_request["meal_name"] = "Changed request"
    conflict = client.post("/api/v1/analyses", json=meal_request, headers=headers)
    assert conflict.status_code == 409


def test_owner_isolation_for_jobs_images_and_journal(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    saved = client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"]}).json()
    image = client.post("/api/v1/images", headers=session, files={"file": ("meal.jpg", image_bytes(), "image/jpeg")}).json()
    other = client.post("/api/v1/session", json={}).json()
    second_headers = {"X-CSRF-Token": other["csrf_token"]}
    assert client.get(f'/api/v1/analyses/{job["id"]}').status_code == 404
    assert client.get(f'/api/v1/images/{image["id"]}').status_code == 404
    assert client.delete(f'/api/v1/journal/{saved["id"]}', headers=second_headers).status_code == 404
    assert client.get("/api/v1/journal").json()["items"] == []


def test_sse_replay_has_monotonic_ids_and_terminal_event(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    response = client.get(f'/api/v1/analyses/{job["id"]}/events')
    assert response.status_code == 200
    ids = [int(line[4:]) for line in response.text.splitlines() if line.startswith("id: ")]
    assert ids == sorted(set(ids))
    assert "event: finished" in response.text
    assert "event: progress" in response.text
    replay = client.get(f'/api/v1/analyses/{job["id"]}/events', headers={"Last-Event-ID": str(ids[-1])})
    assert "event: progress" not in replay.text
    assert "event: finished" in replay.text


def test_demo_does_not_fabricate_image_recognition(client, session):
    image = client.post("/api/v1/images", headers=session, files={"file": ("meal.jpg", image_bytes(), "image/jpeg")})
    assert image.status_code == 201
    image_id = image.json()["id"]
    created = client.post("/api/v1/analyses", headers=session, json={"image_id": image_id})
    job = wait_for_job(client, created.json()["id"])
    assert job["status"] == "failed"
    assert job["error"] == "Something went wrong. Try again."
    assert client.get(f"/api/v1/images/{image_id}").status_code == 404


def test_upload_size_enforced_before_parser(client, session):
    response = client.post("/api/v1/images", content=b"x", headers={**session, "Content-Length": str(50 * 1024 * 1024)})
    assert response.status_code == 413


def test_unknown_food_and_invalid_grams_are_rejected(client, session):
    bad_food = {"items": [{"food_id": "missing", "grams": 100}]}
    assert client.post("/api/v1/analyses", headers=session, json=bad_food).status_code == 404
    negative = {"items": [{"food_id": "demo:rice", "grams": -1}]}
    assert client.post("/api/v1/analyses", headers=session, json=negative).status_code == 422
    assert client.post("/api/v1/analyses", headers=session, json={}).status_code == 422


def test_preferences_validate_timezone_and_ignore_no_fields(client, session):
    assert client.put("/api/v1/preferences", headers=session, json={"timezone": "Not/AZone"}).status_code == 422
    assert client.put("/api/v1/preferences", headers=session, json={"admin": True}).status_code == 422
    response = client.put("/api/v1/preferences", headers=session, json={"timezone": "Asia/Kolkata", "language": "bn"})
    assert response.status_code == 200
    assert client.get("/api/v1/preferences").json()["language"] == "bn"


def test_recipe_and_export_flow(client, session, meal_request):
    recipe = client.post("/api/v1/recipes", headers=session, json={
        "name": "Rice example", "ingredients": [{"food_id": "demo:rice", "grams": 100}],
        "cooked_weight_g": 200, "servings": 2,
    })
    assert recipe.status_code == 201
    assert recipe.json()["per_100g"]["energy_kcal"] == 65
    assert len(client.get("/api/v1/recipes").json()["items"]) == 1
    job = completed_job(client, session, meal_request)
    saved = client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"], "notes": "=HYPERLINK(\"bad\")"})
    assert saved.status_code == 201
    csv = client.get("/api/v1/export?format=csv")
    assert csv.status_code == 200
    assert "'=HYPERLINK" in csv.text
    payload = client.get("/api/v1/export").json()
    assert payload["schema_version"] == 1
    assert len(payload["journal"]) == 1
    assert len(payload["recipes"]) == 1
    assert "csrf" not in json.dumps(payload).lower()


def test_erase_invalidates_session_and_removes_records(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    client.post("/api/v1/journal", headers=session, json={"analysis_id": job["id"]})
    assert client.delete("/api/v1/account", headers=session).status_code == 204
    assert client.get("/api/v1/session").status_code == 401
    client.post("/api/v1/session", json={})
    assert client.get("/api/v1/journal").json()["items"] == []


def test_response_security_headers(client):
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert len(response.headers["x-request-id"]) == 32


def test_untrusted_host_rejected(client):
    assert client.get("/api/v1/health", headers={"Host": "untrusted.example"}).status_code == 400


def test_live_login_requires_password_and_preserves_owner_across_sessions(settings):
    from dataclasses import replace
    from fastapi.testclient import TestClient
    from nutritensor.main import create_app

    configured = replace(
        settings, mode="live", model_backend="openai-compatible",
        admin_password="a-test-password-with-entropy", cookie_secure=True,
        environment="production",
    )
    with TestClient(create_app(configured), base_url="https://testserver") as live:
        assert live.post("/api/v1/session", json={"password": "incorrect"}).status_code == 401
        login = live.post("/api/v1/session", json={"password": configured.admin_password})
        assert login.status_code == 200
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie and "secure" in cookie and "samesite=strict" in cookie
        headers = {"X-CSRF-Token": login.json()["csrf_token"]}
        assert live.put("/api/v1/preferences", headers=headers, json={"timezone": "Asia/Dhaka"}).status_code == 200
        assert live.delete("/api/v1/session", headers=headers).status_code == 204
        assert live.get("/api/v1/preferences").status_code == 401
        second = live.post("/api/v1/session", json={"password": configured.admin_password})
        assert second.status_code == 200
        assert live.get("/api/v1/preferences").json()["timezone"] == "Asia/Dhaka"
        assert configured.admin_password not in second.text
        # Readiness must not report an empty production catalog as ready.
        assert live.get("/api/v1/ready").status_code == 503
