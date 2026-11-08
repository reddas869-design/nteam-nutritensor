"""FoodData Central import normalization. No external call is made implicitly."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

import httpx

from nutritensor.domain.models import FoodRecord, Nutrients, Serving, Source


NUTRIENT_FIELDS = {
    1003: ("protein_g", "g"),
    1004: ("fat_g", "g"),
    1005: ("carbohydrate_g", "g"),
    1079: ("fiber_g", "g"),
    2000: ("sugar_g", "g"),
    1093: ("sodium_mg", "mg"),
}
ENERGY_PREFERENCE = (2048, 2047, 1008)


def finite_nonnegative(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def normalize_unit(unit: str) -> str:
    return unit.strip().lower().replace("µ", "u").replace("μ", "u")


def normalize_nutrients(rows: list[dict]) -> tuple[Nutrients, list[str]]:
    values: dict[str, float] = {}
    energies: dict[int, float] = {}
    warnings: list[str] = []
    for row in rows:
        nutrient = row.get("nutrient", {})
        nutrient_id = nutrient.get("id", row.get("nutrientId"))
        amount = finite_nonnegative(row.get("amount", row.get("value")))
        if amount is None:
            continue
        unit = normalize_unit(nutrient.get("unitName", row.get("unitName", "")))
        if nutrient_id in ENERGY_PREFERENCE:
            if unit == "kcal":
                energies[int(nutrient_id)] = amount
            else:
                warnings.append(f"Energy {nutrient_id} has unsupported unit {unit}")
        elif nutrient_id in NUTRIENT_FIELDS:
            field, expected_unit = NUTRIENT_FIELDS[nutrient_id]
            if unit == expected_unit:
                values[field] = amount
            elif expected_unit == "mg" and unit == "g":
                values[field] = amount * 1000
            elif expected_unit == "g" and unit == "mg":
                values[field] = amount / 1000
            else:
                warnings.append(f"Nutrient {nutrient_id} has unsupported unit {unit}")
    for nutrient_id in ENERGY_PREFERENCE:
        if nutrient_id in energies:
            values["energy_kcal"] = energies[nutrient_id]
            break
    return Nutrients(**values), warnings


def from_fdc(payload: dict) -> FoodRecord:
    if not payload.get("fdcId") or not payload.get("description"):
        raise ValueError("Missing FDC identifier or description")
    nutrients, warnings = normalize_nutrients(payload.get("foodNutrients", []))
    servings = []
    for item in payload.get("foodPortions", [])[:20]:
        grams = finite_nonnegative(item.get("gramWeight"))
        if not grams:
            continue
        amount = item.get("amount", 1)
        measure = item.get("measureUnit", {}).get("name", "portion")
        modifier = item.get("modifier", "")
        label = f"{amount} {measure} {modifier}".strip()[:80]
        servings.append(Serving(label=label, grams=grams))
    fdc_id = str(payload["fdcId"])
    category = payload.get("foodCategory", {})
    if isinstance(category, dict):
        category = category.get("description", "Other")
    return FoodRecord(
        id=f"fdc:{fdc_id}", name=payload["description"][:300],
        category=str(category or payload.get("brandedFoodCategory") or "Other")[:80],
        nutrients=nutrients, servings=servings,
        source=Source(
            provider=f"USDA FoodData Central / {payload.get('dataType', 'unknown')}",
            record_id=fdc_id, title=payload["description"][:500],
            url=f"https://fdc.nal.usda.gov/food-details/{fdc_id}/nutrients",
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            license="CC0 / public domain; USDA attribution requested", is_demo=False,
        ),
        notes="; ".join(warnings + [
            "Values are per 100 g. Verify preparation and edible portion.",
            f"Publication date: {payload.get('publicationDate', 'not supplied')}",
            "Energy preference: Atwater specific, Atwater general, then reported kcal.",
        ])[:2000],
    )


class FoodDataCentral:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("A FoodData Central API key is required for online imports")
        self.api_key = api_key

    def fetch(self, food_id: int) -> FoodRecord:
        if food_id <= 0:
            raise ValueError("FDC ID must be positive")
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            response = client.get(
                f"https://api.nal.usda.gov/fdc/v1/food/{food_id}",
                params={"api_key": self.api_key},
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()
            return from_fdc(response.json())
