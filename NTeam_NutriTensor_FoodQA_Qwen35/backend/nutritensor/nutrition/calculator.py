"""Deterministic nutrient arithmetic and explicit missing-data propagation."""

from __future__ import annotations

from dataclasses import dataclass
from math import fsum

from nutritensor.domain.models import FoodSelection, Nutrients, PortionResult, QualityFlag, Recipe, RecipeCreate
from nutritensor.nutrition.catalog import Catalog
from nutritensor.storage.database import identifier, timestamp


@dataclass(frozen=True)
class Aggregate:
    totals: Nutrients
    lower: Nutrients
    upper: Nutrients
    coverage: dict[str, float]


def aggregate(portions: list[PortionResult]) -> Aggregate:
    sums: dict[str, float | None] = {}
    lowers: dict[str, float | None] = {}
    uppers: dict[str, float | None] = {}
    coverage: dict[str, float] = {}
    for field in Nutrients.model_fields:
        values = [getattr(portion.nutrients, field) for portion in portions]
        known = [value for value in values if value is not None]
        coverage[field] = len(known) / len(portions) if portions else 0
        if not portions or len(known) != len(portions):
            sums[field] = None
            lowers[field] = None
            uppers[field] = None
        else:
            sums[field] = round(fsum(known), 3)
            lowers[field] = round(fsum(getattr(portion.lower, field) for portion in portions), 3)
            uppers[field] = round(fsum(getattr(portion.upper, field) for portion in portions), 3)
    return Aggregate(Nutrients(**sums), Nutrients(**lowers), Nutrients(**uppers), coverage)


def calculate_portions(catalog: Catalog, selections: list[FoodSelection]) -> list[PortionResult]:
    portions: list[PortionResult] = []
    for selection in selections:
        food = catalog.get(selection.food_id)
        factor = selection.grams / 100
        uncertainty = selection.uncertainty_percent / 100
        portions.append(PortionResult(
            food=food,
            grams=selection.grams,
            portion_source=selection.portion_source,
            uncertainty_percent=selection.uncertainty_percent,
            nutrients=food.nutrients.scaled(factor),
            lower=food.nutrients.scaled(factor * (1 - uncertainty)),
            upper=food.nutrients.scaled(factor * (1 + uncertainty)),
        ))
    return portions


def quality_review(portions: list[PortionResult], confirmed: bool) -> list[QualityFlag]:
    flags: list[QualityFlag] = []
    if not confirmed:
        flags.append(QualityFlag(
            code="confirmation_required", severity="warning",
            message="Confirm food identity, preparation, and grams before saving.",
        ))
    for portion in portions:
        if portion.food.source.provider.startswith("Qwen3.5-4B ("):
            flags.append(QualityFlag(
                code="unverified_model_nutrition", severity="warning", item_id=portion.food.id,
                message="ntemma estimated these nutrients from general knowledge, not a verified database. "
                        "Food identity, ingredients, edible weight and nutrient figures require confirmation.",
            ))
        if portion.food.source.is_demo:
            flags.append(QualityFlag(
                code="demo_data", severity="warning", item_id=portion.food.id,
                message="Illustrative demo data; do not use these values for dietary decisions.",
            ))
        if portion.portion_source != "weighed":
            flags.append(QualityFlag(
                code="estimated_portion", severity="info", item_id=portion.food.id,
                message="ntemma could be wrong. Have a professional check the numbers",
            ))
        missing = [key for key, value in portion.nutrients.model_dump().items() if value is None]
        if missing:
            flags.append(QualityFlag(
                code="missing_nutrients", severity="warning", item_id=portion.food.id,
                message=f"Source does not report: {', '.join(missing)}. Missing values stay unknown.",
            ))
        if portion.food.preparation == "unspecified":
            flags.append(QualityFlag(
                code="preparation_unknown", severity="info", item_id=portion.food.id,
                message="Preparation is unspecified; raw and cooked weights are not interchangeable.",
            ))
    return flags


def build_recipe(catalog: Catalog, request: RecipeCreate) -> Recipe:
    selections = [FoodSelection(
        food_id=ingredient.food_id, grams=ingredient.grams,
        portion_source="weighed", uncertainty_percent=0,
    ) for ingredient in request.ingredients]
    portions = calculate_portions(catalog, selections)
    result = aggregate(portions)
    unique_sources = {
        (portion.food.source.provider, portion.food.source.record_id): portion.food.source
        for portion in portions
    }
    return Recipe(
        **request.model_dump(), id=identifier(), created_at=timestamp(),
        per_100g=result.totals.scaled(100 / request.cooked_weight_g),
        total=result.totals, sources=list(unique_sources.values()), coverage=result.coverage,
    )


def macro_energy(nutrients: Nutrients) -> dict[str, float] | None:
    if any(getattr(nutrients, key) is None for key in ("protein_g", "carbohydrate_g", "fat_g")):
        return None
    return {
        "protein": nutrients.protein_g * 4,
        "carbohydrate": nutrients.carbohydrate_g * 4,
        "fat": nutrients.fat_g * 9,
    }
