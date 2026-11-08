"""Fail-closed food entry policy, independent of model compliance."""

import re

from nutritensor.core.errors import UnsupportedFoodInput
from nutritensor.domain.models import Candidate
from nutritensor.nutrition.catalog import Catalog

RETRY_MESSAGE = "Something went wrong. Try again."


def food_names_only(text: str, catalog: Catalog) -> list[Candidate]:
    whole = catalog.search(text, limit=2)
    if whole and whole[0].exact and not (len(whole) > 1 and whole[1].exact):
        return [Candidate(label=whole[0].food.name, food_id=whole[0].food.id, confidence=1,
                          evidence="Exact catalog name supplied by the user")]
    parts = re.split(r"[,;\n]+", text.strip())
    if not 1 <= len(parts) <= 12:
        raise UnsupportedFoodInput(RETRY_MESSAGE)
    result = []
    for part in parts:
        match = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)\s*g\s+)?(.+?)\s*", part, re.IGNORECASE)
        if not match:
            raise UnsupportedFoodInput(RETRY_MESSAGE)
        grams = float(match[1]) if match[1] else None
        matches = catalog.search(match[2], limit=2)
        if not matches or not matches[0].exact or (len(matches) > 1 and matches[1].exact) or (grams is not None and not 0 < grams <= 5000):
            raise UnsupportedFoodInput(RETRY_MESSAGE)
        food = matches[0].food
        result.append(Candidate(label=food.name, food_id=food.id, confidence=1, grams=grams,
                                evidence="Exact catalog name supplied by the user"))
    return result


FOOD_QUESTIONS = {
    "how many calories are in this meal": "energy_kcal",
    "how much protein is in this meal": "protein_g",
    "explain the portions": "portions",
    "why are some values unknown": "unknown",
    "এই খাবারে কত ক্যালোরি": "energy_kcal",
    "এই খাবারে কত প্রোটিন": "protein_g",
}


def approved_question(text: str) -> str | None:
    normalized = " ".join(text.lower().strip().rstrip("?.!।").split())
    return FOOD_QUESTIONS.get(normalized)
