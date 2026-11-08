"""Small, intentionally illustrative fixtures. Never loaded in live mode."""

from nutritensor.domain.models import FoodRecord, Nutrients, Serving, Source
from nutritensor.nutrition.catalog import Catalog


# Values are UI fixtures, not USDA/ICMR records or a validated food database.
DEMO_FOODS = [
    ("rice", "Steamed rice", ["rice", "bhaat", "ভাত"], "Grains", "cooked", 130, 2.7, 28.2, 0.3, 0.4, 0.1, 1, 150),
    ("dal", "Yellow dal", ["dal", "lentils", "ডাল"], "Pulses", "cooked", 110, 6.5, 16, 2.2, 4, 1.1, 180, 150),
    ("chicken", "Grilled chicken", ["chicken", "মুরগি"], "Protein", "cooked", 165, 31, 0, 3.6, 0, 0, 74, 120),
    ("cucumber", "Cucumber", ["cucumber", "শসা"], "Vegetables", "raw", 15, 0.7, 3.6, 0.1, 0.5, 1.7, 2, 80),
    ("tomato", "Tomato", ["tomato", "টমেটো"], "Vegetables", "raw", 18, 0.9, 3.9, 0.2, 1.2, 2.6, 5, 80),
    ("chapati", "Chapati", ["roti", "chapati", "রুটি"], "Grains", "cooked", 270, 9, 49, 5, 7, 2, 200, 40),
    ("egg", "Boiled egg", ["egg", "ডিম"], "Protein", "cooked", 155, 13, 1.1, 11, 0, 1.1, 124, 50),
    ("paneer", "Paneer", ["paneer", "পনির"], "Dairy", "fresh", 265, 18, 3, 21, 0, 2, 22, 80),
    ("banana", "Banana", ["banana", "কলা"], "Fruit", "raw", 89, 1.1, 23, 0.3, 2.6, 12, 1, 100),
    ("apple", "Apple", ["apple", "আপেল"], "Fruit", "raw", 52, 0.3, 14, 0.2, 2.4, 10, 1, 150),
    ("yogurt", "Plain yogurt", ["curd", "yogurt", "দই"], "Dairy", "plain", 61, 3.5, 4.7, 3.3, 0, 4.7, 46, 150),
    ("oats", "Rolled oats", ["oats", "ওটস"], "Grains", "dry", 389, 16.9, 66, 6.9, 10.6, 1, 2, 40),
    ("chickpeas", "Chickpeas", ["chana", "chickpeas", "ছোলা"], "Pulses", "cooked", 164, 8.9, 27.4, 2.6, 7.6, 4.8, 7, 100),
    ("spinach", "Spinach", ["palak", "spinach", "পালং"], "Vegetables", "cooked", 23, 3, 3.8, 0.3, 2.4, 0.4, 70, 100),
    ("potato", "Boiled potato", ["potato", "আলু"], "Vegetables", "cooked", 87, 1.9, 20.1, 0.1, 1.8, 0.9, 4, 120),
    ("oil", "Cooking oil", ["oil", "তেল"], "Fats", "unspecified", 884, 0, 0, 100, 0, 0, 0, 5),
    ("milk", "Whole milk", ["milk", "দুধ"], "Dairy", "plain", 61, 3.2, 4.8, 3.3, 0, 5, 43, 200),
    ("fish", "Cooked fish", ["fish", "মাছ"], "Protein", "cooked", 128, 26, 0, 2.7, 0, 0, 56, 100),
]


def demo_catalog() -> Catalog:
    records = []
    for row in DEMO_FOODS:
        food_id, name, aliases, category, preparation, energy, protein, carbs, fat, fiber, sugar, sodium, serving = row
        records.append(FoodRecord(
            id=f"demo:{food_id}", name=name, aliases=aliases, category=category, preparation=preparation,
            nutrients=Nutrients(
                energy_kcal=energy, protein_g=protein, carbohydrate_g=carbs,
                fat_g=fat, fiber_g=fiber, sugar_g=sugar, sodium_mg=sodium,
            ),
            source=Source(
                provider="NutriTensor demo fixture", record_id=food_id,
                title="Illustrative example — replace with verified data", retrieved_at="2026-10-17",
                license="Project-authored UI fixture", is_demo=True,
            ),
            servings=[Serving(label="Example portion", grams=serving)],
            notes="Demonstration values only. Recipes, brands, cooking and portions vary.",
        ))
    return Catalog(records, allow_demo=True)
