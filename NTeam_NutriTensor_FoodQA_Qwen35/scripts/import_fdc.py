#!/usr/bin/env python3
"""Import USDA JSON, selected API IDs, or a bounded subset of official bulk CSV."""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from nutritensor.domain.models import FoodRecord
from nutritensor.nutrition.catalog import Catalog
from nutritensor.nutrition.usda import FoodDataCentral, from_fdc


REQUIRED_CSV = {
    "food.csv": {"fdc_id", "description", "data_type"},
    "nutrient.csv": {"id", "name", "unit_name"},
    "food_nutrient.csv": {"fdc_id", "nutrient_id", "amount"},
}


def csv_rows(path: Path, required: set[str]):
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(f"{path.name} is missing required columns: {sorted(required)}")
        yield from reader


def import_csv(directory: Path, ids: set[int], contains: str | None, limit: int) -> list[FoodRecord]:
    if not ids and not contains:
        raise ValueError("Bulk CSV requires --ids or --contains to select a bounded subset")
    metadata = {}
    for row in csv_rows(directory / "food.csv", REQUIRED_CSV["food.csv"]):
        identifier = int(row["fdc_id"])
        selected = identifier in ids if ids else contains.casefold() in row["description"].casefold()
        if selected:
            metadata[identifier] = {
                "fdcId": identifier,
                "description": row["description"],
                "dataType": row["data_type"],
                "publicationDate": row.get("publication_date", ""),
                "foodNutrients": [],
            }
            if len(metadata) >= limit:
                break
    if not metadata:
        raise ValueError("No matching food records were found")
    nutrients = {}
    for row in csv_rows(directory / "nutrient.csv", REQUIRED_CSV["nutrient.csv"]):
        nutrients[int(row["id"])] = {"id": int(row["id"]), "name": row["name"], "unitName": row["unit_name"]}
    for row in csv_rows(directory / "food_nutrient.csv", REQUIRED_CSV["food_nutrient.csv"]):
        food_id = int(row["fdc_id"])
        if food_id not in metadata:
            continue
        nutrient_id = int(row["nutrient_id"])
        if nutrient_id not in nutrients:
            continue
        metadata[food_id]["foodNutrients"].append({"nutrient": nutrients[nutrient_id], "amount": row["amount"] or None})
    return [from_fdc(value) for value in metadata.values()]


def import_json(path: Path) -> list[FoodRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and "fdcId" in payload:
        items = [payload]
    elif isinstance(payload, dict):
        keys = ("FoundationFoods", "SRLegacyFoods", "BrandedFoods", "SurveyFoods", "foods")
        items = next((payload[key] for key in keys if isinstance(payload.get(key), list)), [])
    else:
        raise ValueError("Unsupported JSON structure")
    if not items:
        raise ValueError("No food records found in JSON")
    return [FoodRecord.model_validate(item) if "source" in item else from_fdc(item) for item in items]


def write_catalog(records: list[FoodRecord], destination: Path, merge: bool) -> None:
    by_id = {}
    if destination.exists():
        if not merge:
            raise ValueError(f"{destination} exists. Use --merge to update records by source ID.")
        existing = Catalog.load(destination)
        by_id.update({record.id: record for record in existing.all()})
    by_id.update({record.id: record for record in records})
    catalog = Catalog(list(by_id.values()))
    payload = {
        "schema_version": 1,
        "source": "USDA FoodData Central; provenance is preserved per record",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": catalog.version,
        "foods": [record.model_dump(mode="json") for record in catalog.all()],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=destination.parent, suffix=".json.tmp", delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    try:
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Wrote {len(catalog)} validated source records to {destination}")
    print(f"Catalog version: {catalog.version}")
    print("Review preparation and names; add aliases only when identity is correct.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--json", type=Path)
    source.add_argument("--csv-dir", type=Path)
    source.add_argument("--api", action="store_true")
    parser.add_argument("--ids", nargs="+", type=int, default=[])
    parser.add_argument("--contains")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, default=Path("data/foods.json"))
    parser.add_argument("--merge", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.limit <= 100000:
        parser.error("--limit must be 1 to 100000")
    try:
        if args.json:
            records = import_json(args.json)
        elif args.csv_dir:
            records = import_csv(args.csv_dir, set(args.ids), args.contains, args.limit)
        else:
            if not args.ids:
                parser.error("--api requires --ids")
            if len(args.ids) > 100:
                parser.error("Import at most 100 explicit IDs per API run")
            key = os.getenv("NTEAM_FDC_API_KEY")
            if not key:
                parser.error("Set NTEAM_FDC_API_KEY in this terminal. Do not put the key in a shell argument.")
            client = FoodDataCentral(key)
            records = [client.fetch(food_id) for food_id in dict.fromkeys(args.ids)]
        write_catalog(records, args.output, args.merge)
    except Exception as exc:
        # HTTP error strings can contain API keys in URLs, so print only the class for transport errors.
        import httpx
        if isinstance(exc, httpx.HTTPError):
            raise SystemExit(f"FoodData Central request failed: {type(exc).__name__}. Check key and rate limits.")
        raise SystemExit(str(exc))


if __name__ == "__main__":
    main()
