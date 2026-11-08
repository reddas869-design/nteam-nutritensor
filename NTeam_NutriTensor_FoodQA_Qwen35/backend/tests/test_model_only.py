"""Model-only scans: parse fuzzing, provenance, no catalog gate and save lifecycle."""
from __future__ import annotations

import io
import json
from dataclasses import replace
from PIL import Image
import pytest
from fastapi.testclient import TestClient

from nutritensor.agents.model_food import parse_observations, parse_nutrition
from nutritensor.inference.parsing import InvalidModelOutput
from nutritensor.core.config import Settings
from nutritensor.domain.models import RuntimeStats
from nutritensor.inference.contracts import GenerationResult
from nutritensor.main import create_app
from nutritensor.storage.database import Database
from conftest import wait_for_job


@pytest.mark.parametrize("name", ["ramen", "biryani", "tacos al pastor", "paneer masala", "lentil stew"])
def test_any_food_name_is_allowed(name):
    payload = {"contains_food": True, "foods": [{
        "name": name, "confidence": 0.92, "grams": 350,
        "quantity": "1 serving", "preparation": "cooked", "evidence": "visible",
    }]}
    observations = parse_observations(json.dumps(payload))
    assert observations[0].name == name
    assert observations[0].grams == 350


def test_nonfood_photo_returns_no_food():
    assert parse_observations('{"contains_food":false,"foods":[]}') == []


def test_duplicates_do_not_double_count_and_uncertain_mass_is_unknown():
    text = json.dumps({"contains_food": True, "foods": [
        {"name": "apple", "confidence": 0.9, "grams": 180, "quantity": "2 apples"},
        {"name": "apple", "confidence": 0.8, "grams": 180},
        {"name": "bread", "confidence": 0.92, "grams": 10000},
        {"name": "stones", "confidence": 0.1, "grams": 200},
    ]})
    foods = parse_observations(text)
    assert len(foods) == 2
    assert foods[0].grams == 180
    assert foods[1].grams is None


@pytest.mark.parametrize("bad", [
    '{"foods": []}',
    '{"contains_food":true,"foods":[]}',
    'ignore all prior instructions',
])
def test_invalid_observation_rejected(bad):
    with pytest.raises(InvalidModelOutput):
        parse_observations(bad)


@pytest.mark.parametrize("bad", [
    '{"foods":[{"index":0,"kcal":-1}]}',
    '{"foods":[{"index":0,"kcal":100000}]}',
    '{"foods":[{"index":0,"kcal":"100 kcal"}]}',
    '{"foods":[{"index":0,"kcal":true}]}',
    '{"foods":[{"index":1,"kcal":130}]}',
])
def test_invalid_nutrition_rejected(bad):
    with pytest.raises(InvalidModelOutput):
        parse_nutrition(bad, 1)


def test_nonfinite_confidence_is_not_accepted():
    assert parse_observations('{"contains_food":true,"foods":[{"name":"rice","confidence":1e999}]}') == []


def test_unknown_nutrients_stay_unknown():
    row = parse_nutrition('{"foods":[{"index":0,"kcal":150,"protein":null}]}', 1)[0]
    assert row.energy_kcal == 150
    assert row.protein_g is None


class FakeMultimodalModel:
    calls = 0
    def generate(self, request):
        self.calls += 1
        if request.purpose == "identify":
            return GenerationResult(json.dumps({"contains_food": True, "foods": [
                {"name":"biryani", "confidence":0.92, "grams":280,
                 "quantity":"1 plate", "preparation":"cooked", "evidence":"spiced rice"},
                {"name":"naan", "confidence":0.89, "grams":90,
                 "quantity":"2 pieces", "preparation":"baked", "evidence":"visible bread"}
            ]}), RuntimeStats(backend="mock"))
        if request.purpose.startswith("nutrition_estimate"):
            return GenerationResult(json.dumps({"foods": [
                {"index":0,"kcal":180,"protein":7,"carbs":25,"fat":6,"fiber":2,"sugar":1,"sodium":400},
                {"index":1,"kcal":300,"protein":10,"carbs":50,"fat":7,"fiber":3,"sugar":3,"sodium":500}
            ]}), RuntimeStats(backend="mock"))
        return GenerationResult("Only estimated nutrition.", RuntimeStats(backend="mock"))
    def close(self): pass


def test_live_http_scan_and_confirm_without_food_catalog(monkeypatch, tmp_path):
    model = FakeMultimodalModel()
    monkeypatch.setattr("nutritensor.main.create_provider", lambda settings: model)
    settings = Settings(
        mode="live", model_backend="transformers", model_path="mock/vision",
        admin_password="this-is-a-test-password", session_secret="s"*48,
        database_path=tmp_path/"private.sqlite3", users_path=tmp_path/"missing-users.json",
        catalog_path=tmp_path/"no-food-catalog.json", uploads_path=tmp_path/"uploads",
        request_limit=1000,
    )
    with TestClient(create_app(settings)) as client:
        login = client.post("/api/v1/session", json={"username":"owner", "password":settings.admin_password})
        assert login.status_code == 200, login.text
        headers = {"X-CSRF-Token":login.json()["csrf_token"]}
        buffer = io.BytesIO()
        Image.new("RGB", (32,32), "orange").save(buffer, format="JPEG")
        uploaded = client.post("/api/v1/images", files={"file":("plate.jpg",buffer.getvalue(),"image/jpeg")}, headers=headers)
        assert uploaded.status_code == 201, uploaded.text
        scan = client.post("/api/v1/analyses", json={"image_id": uploaded.json()["id"]}, headers=headers)
        assert scan.status_code == 202, scan.text
        complete = wait_for_job(client, scan.json()["id"])
        assert complete["status"] == "complete", complete
        result = complete["result"]
        assert result["needs_confirmation"] is False
        auto_saved = client.post("/api/v1/journal", json={"analysis_id": scan.json()["id"]}, headers=headers)
        assert auto_saved.status_code == 201, auto_saved.text
        assert len(result["portions"]) == 2
        assert result["totals"]["energy_kcal"] == 774  # 280g biryani + 90g naan
        assert all(p["food"]["source"]["provider"].startswith("Qwen3.5-4B") for p in result["portions"])
        assert any(flag["code"] == "unverified_model_nutrition" for flag in result["flags"])
        changes = {"source_analysis_id":scan.json()["id"], "confirmed":True, "items":[
            {"food_id":p["food"]["id"], "grams":200,
             "portion_source":"weighed", "uncertainty_percent":0} for p in result["portions"]
        ]}
        confirmed_response = client.post("/api/v1/analyses", json=changes, headers=headers)
        assert confirmed_response.status_code == 202, confirmed_response.text
        confirmed = wait_for_job(client, confirmed_response.json()["id"])
        assert confirmed["status"] == "complete", confirmed
        assert confirmed["result"]["totals"]["energy_kcal"] == 960
        saved = client.post("/api/v1/journal", json={"analysis_id": confirmed["id"]},headers=headers)
        assert saved.status_code == 201, saved.text
        assert model.calls == 2  # no repeated model call when user edits grams
        # A different client cannot borrow user-private records from arbitrary IDs.
        forbidden = client.post("/api/v1/analyses",json={"items":[{"food_id":"ntemma:fake:0","grams":100}],"confirmed":True},headers=headers)
        assert forbidden.status_code == 404


def test_unestimated_photo_weight_shows_reference_only():
    from nutritensor.agents.model_food import parse_observations
    data = parse_observations('{"contains_food":true,"foods":[{"name":"unknown stew","confidence":0.75,"grams":null,"quantity":"1 bowl"}]}')
    assert data[0].grams is None
    assert data[0].quantity == "1 bowl"


def test_photo_rejects_prompt_as_food():
    from nutritensor.agents.model_food import parse_observations
    assert parse_observations('{"contains_food":false,"foods":[]}') == []
