import json
from importlib.resources import files

import pytest

from nutritensor.nutrition.catalog import Catalog
from nutritensor.nutrition.starter import install_starter, starter_records
from nutritensor.nutrition.usda import from_fdc


def test_starter_nutrients_reproduce_retained_usda_source_records():
    raw = json.loads(files("nutritensor").joinpath("resources/fruit_sources.json").read_text())
    originals = {f"fdc:{row['fdcId']}": from_fdc(row) for row in raw}
    records = starter_records()
    assert len(records) == 8
    for food in records:
        original = originals[food.id]
        assert food.nutrients == original.nutrients
        assert food.source.title == original.source.title
        assert food.source.record_id == original.source.record_id
        assert not food.source.is_demo
    assert Catalog(records).search("apple")[0].food.nutrients.energy_kcal == 52


def test_starter_install_is_offline_and_preserves_existing_records(tmp_path):
    path = tmp_path / "foods.json"
    assert install_starter(path) == 8
    with pytest.raises(ValueError, match="already exists"):
        install_starter(path)
    payload = json.loads(path.read_text())
    payload["foods"][0]["notes"] = "Reviewed local preparation"
    path.write_text(json.dumps(payload))
    assert install_starter(path, merge=True) == 8
    assert Catalog.load(path).get(payload["foods"][0]["id"]).notes == "Reviewed local preparation"


def test_curated_aliases_have_no_ambiguous_exact_match():
    records = starter_records()
    catalog = Catalog(records)
    for food in records:
        for alias in food.aliases:
            matches = [match for match in catalog.search(alias, limit=20) if match.exact]
            assert len(matches) == 1
            assert matches[0].food.id == food.id
