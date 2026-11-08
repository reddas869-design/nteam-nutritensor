from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from nutritensor.domain.models import FoodSelection, Nutrients, RecipeCreate
from nutritensor.nutrition.calculator import aggregate, build_recipe, calculate_portions, macro_energy, quality_review
from nutritensor.nutrition.catalog import Catalog, normalize
from nutritensor.nutrition.usda import from_fdc, normalize_nutrients


def test_known_meal_arithmetic_is_independent_of_language_model(catalog):
    selections = [
        FoodSelection(food_id="demo:rice", grams=150, portion_source="weighed", uncertainty_percent=2),
        FoodSelection(food_id="demo:chicken", grams=120, portion_source="weighed", uncertainty_percent=2),
    ]
    result = aggregate(calculate_portions(catalog, selections))
    assert result.totals.energy_kcal == pytest.approx(393)
    assert result.totals.protein_g == pytest.approx(41.25)
    assert result.totals.carbohydrate_g == pytest.approx(42.3)
    assert result.totals.fat_g == pytest.approx(4.77)
    assert result.lower.energy_kcal == pytest.approx(385.14)
    assert result.upper.energy_kcal == pytest.approx(400.86)
    assert result.coverage["energy_kcal"] == 1


def test_missing_value_invalidates_total_but_reports_coverage(catalog):
    rice = catalog.get("demo:rice")
    chicken = catalog.get("demo:chicken")
    chicken.nutrients.sodium_mg = None
    subset = Catalog([rice, chicken], allow_demo=True)
    parts = calculate_portions(subset, [FoodSelection(food_id=rice.id, grams=100), FoodSelection(food_id=chicken.id, grams=100)])
    result = aggregate(parts)
    assert result.totals.sodium_mg is None
    assert result.lower.sodium_mg is None
    assert result.upper.sodium_mg is None
    assert result.coverage["sodium_mg"] == 0.5
    assert result.totals.energy_kcal == 295


def test_empty_meal_is_unknown_not_zero():
    result = aggregate([])
    assert all(value is None for value in result.totals.model_dump().values())
    assert all(value == 0 for value in result.coverage.values())


@pytest.mark.parametrize("grams", [0, -1, float("nan"), float("inf"), 5001])
def test_invalid_portion_is_rejected(grams):
    with pytest.raises(ValidationError):
        FoodSelection(food_id="demo:rice", grams=grams)


@pytest.mark.parametrize("factor", [-1, float("inf"), float("nan")])
def test_invalid_scaling_is_rejected(factor):
    with pytest.raises(ValueError):
        Nutrients(energy_kcal=100).scaled(factor)


def test_image_weight_has_minimum_uncertainty():
    selection = FoodSelection(food_id="any", grams=100, portion_source="image_estimate", uncertainty_percent=1)
    assert selection.uncertainty_percent == 25


def test_source_record_is_not_mutated_by_callers(catalog):
    original = catalog.get("demo:rice")
    original.nutrients.energy_kcal = 999
    assert catalog.get("demo:rice").nutrients.energy_kcal == 130


def test_demo_records_cannot_enter_live_catalog(catalog):
    with pytest.raises(ValueError, match="Demo nutrition"):
        Catalog(catalog.all())


def test_duplicate_ids_are_rejected(catalog):
    with pytest.raises(ValueError, match="Duplicate"):
        Catalog([catalog.get("demo:rice"), catalog.get("demo:rice")], allow_demo=True)


def test_unicode_alias_and_description_match(catalog):
    assert catalog.search("ভাত")[0].food.id == "demo:rice"
    assert catalog.search("  RICE!! ")[0].exact
    matched = {match.food.id for match in catalog.match_description("rice with dal and egg")}
    assert matched == {"demo:rice", "demo:dal", "demo:egg"}


def test_description_does_not_match_substrings_inside_words(catalog):
    assert catalog.match_description("priceless sculpture") == []


def test_recipe_yield_accounts_for_water_weight(catalog):
    recipe = build_recipe(catalog, RecipeCreate(
        name="Rice and lentil test", ingredients=[
            {"food_id": "demo:rice", "grams": 100},
            {"food_id": "demo:dal", "grams": 100},
        ], cooked_weight_g=300, servings=3,
    ))
    assert recipe.total.energy_kcal == 240
    assert recipe.per_100g.energy_kcal == 80
    assert recipe.total.protein_g == pytest.approx(9.2)
    assert len(recipe.sources) == 2


def test_quality_flags_distinguish_uncertain_portions(catalog):
    portions = calculate_portions(catalog, [FoodSelection(food_id="demo:rice", grams=100)])
    flags = quality_review(portions, confirmed=False)
    codes = {flag.code for flag in flags}
    assert {"demo_data", "estimated_portion", "confirmation_required"} <= codes


def test_macro_shares_do_not_replace_reported_energy():
    nutrients = Nutrients(energy_kcal=200, protein_g=10, carbohydrate_g=10, fat_g=10)
    assert sum(macro_energy(nutrients).values()) == 170
    assert nutrients.energy_kcal == 200
    assert macro_energy(Nutrients(protein_g=10)) is None


def test_usda_energy_values_are_alternatives_not_additive():
    rows = [
        {"nutrient": {"id": 1008, "unitName": "KCAL"}, "amount": 120},
        {"nutrient": {"id": 2047, "unitName": "KCAL"}, "amount": 118},
        {"nutrient": {"id": 2048, "unitName": "KCAL"}, "amount": 117},
        {"nutrient": {"id": 1003, "unitName": "G"}, "amount": 8},
    ]
    nutrients, warnings = normalize_nutrients(rows)
    assert nutrients.energy_kcal == 117
    assert nutrients.protein_g == 8
    assert nutrients.fiber_g is None
    assert warnings == []


def test_usda_units_and_missing_values_are_validated():
    rows = [
        {"nutrientId": 1093, "unitName": "g", "value": 0.12},
        {"nutrientId": 1003, "unitName": "mg", "value": 2500},
        {"nutrientId": 1004, "unitName": "g", "value": -1},
        {"nutrientId": 1005, "unitName": "g", "value": "NaN"},
        {"nutrientId": 1008, "unitName": "kJ", "value": 400},
    ]
    nutrients, warnings = normalize_nutrients(rows)
    assert nutrients.sodium_mg == 120
    assert nutrients.protein_g == 2.5
    assert nutrients.fat_g is None
    assert nutrients.carbohydrate_g is None
    assert nutrients.energy_kcal is None
    assert warnings


def test_usda_record_preserves_provenance():
    food = from_fdc({
        "fdcId": 12345,
        "description": "Test input, not a real source record",
        "dataType": "Foundation",
        "publicationDate": "2025-01-01",
        "foodNutrients": [{"nutrient": {"id": 1008, "unitName": "kcal"}, "amount": 100}],
        "foodPortions": [{"gramWeight": 40, "amount": 1, "measureUnit": {"name": "portion"}}],
    })
    assert food.id == "fdc:12345"
    assert food.source.record_id == "12345"
    assert food.source.basis == "per_100g"
    assert "Foundation" in food.source.provider
    assert food.servings[0].grams == 40
    assert "2025-01-01" in food.notes
