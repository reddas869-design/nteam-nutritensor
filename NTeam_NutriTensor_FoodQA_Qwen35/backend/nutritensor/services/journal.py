"""Timezone-correct journal summaries and portable data exports."""

from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from nutritensor.domain.models import JournalEntry, Nutrients
from nutritensor.storage.database import Database, timestamp


def date_bounds(start: date, end: date, timezone_name: str) -> tuple[str, str]:
    zone = ZoneInfo(timezone_name)
    first = datetime.combine(start, time.min, tzinfo=zone)
    last = datetime.combine(end + timedelta(days=1), time.min, tzinfo=zone)
    return first.astimezone(timezone.utc).isoformat(), last.astimezone(timezone.utc).isoformat()


def sum_entries(entries: list[JournalEntry]) -> tuple[Nutrients, dict[str, float]]:
    data = {}
    coverage = {}
    for field in Nutrients.model_fields:
        values = [getattr(entry.result.totals, field) for entry in entries]
        known = [value for value in values if value is not None]
        coverage[field] = len(known) / len(entries) if entries else 0
        data[field] = round(sum(known), 3) if entries and len(known) == len(entries) else None
    return Nutrients(**data), coverage


def summarize(entries: list[JournalEntry], timezone_name: str, start: date, end: date) -> dict:
    zone = ZoneInfo(timezone_name)
    groups: dict[str, list[JournalEntry]] = defaultdict(list)
    for entry in entries:
        local_date = datetime.fromisoformat(entry.eaten_at).astimezone(zone).date().isoformat()
        groups[local_date].append(entry)
    days = []
    day = start
    while day <= end:
        matching = groups[day.isoformat()]
        totals, coverage = sum_entries(matching)
        days.append({
            "date": day.isoformat(), "meal_count": len(matching),
            "totals": totals.model_dump(), "coverage": coverage,
        })
        day += timedelta(days=1)
    totals, coverage = sum_entries(entries)
    recorded_days = sum(1 for group in days if group["meal_count"])
    return {
        "start": start.isoformat(), "end": end.isoformat(), "timezone": timezone_name,
        "meal_count": len(entries), "recorded_days": recorded_days,
        "totals": totals.model_dump(), "coverage": coverage, "days": days,
        "note": "This summarizes logged meals only; it does not estimate unlogged intake.",
    }


def csv_safe(value: object) -> str:
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def export_csv(entries: list[JournalEntry]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    nutrient_names = list(Nutrients.model_fields)
    writer.writerow(["entry_id", "eaten_at_utc", "meal", "meal_type", "mode", *nutrient_names, "notes"])
    for entry in entries:
        nutrients = entry.result.totals.model_dump()
        writer.writerow([
            entry.id, entry.eaten_at, csv_safe(entry.meal_name), entry.meal_type, entry.result.mode,
            *["" if nutrients[field] is None else nutrients[field] for field in nutrient_names], csv_safe(entry.notes),
        ])
    return buffer.getvalue()


def export_account(database: Database, owner: str) -> dict:
    entries = []
    offset = 0
    while True:
        page = database.list_journal(owner, limit=1000, offset=offset)
        entries.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return {
        "schema_version": 1, "application": "NTeam NutriTensor", "exported_at": timestamp(),
        "journal": [entry.model_dump(mode="json") for entry in entries],
        "recipes": [recipe.model_dump(mode="json") for recipe in database.list_recipes(owner)],
        "preferences": database.preferences(owner).model_dump(mode="json"),
    }
