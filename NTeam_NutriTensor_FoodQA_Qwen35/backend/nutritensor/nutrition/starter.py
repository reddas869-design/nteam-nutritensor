"""Install the bundled eight-fruit USDA catalog without network access."""

import json
import os
import tempfile
from importlib.resources import files
from pathlib import Path

from nutritensor.domain.models import FoodRecord
from nutritensor.nutrition.catalog import Catalog


def starter_records() -> list[FoodRecord]:
    payload = json.loads(files("nutritensor").joinpath("resources/fruit_catalog.json").read_text(encoding="utf-8"))
    return [FoodRecord.model_validate(row) for row in payload["foods"]]


def install_starter(destination: Path, merge: bool = False) -> int:
    records = {}
    if destination.exists():
        if not merge:
            raise ValueError("Catalog already exists; use --merge to add only missing starter records.")
        records = {food.id: food for food in Catalog.load(destination).all()}
    for food in starter_records():
        # A reviewed local override has priority over the shipped starter.
        records.setdefault(food.id, food)
    catalog = Catalog(list(records.values()))
    payload = json.dumps({"schema_version": 1, "foods": [food.model_dump(mode="json") for food in catalog.all()]}, ensure_ascii=False, indent=2)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, filename = tempfile.mkstemp(dir=destination.parent, suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(filename).replace(destination)
    finally:
        Path(filename).unlink(missing_ok=True)
    return len(catalog)
