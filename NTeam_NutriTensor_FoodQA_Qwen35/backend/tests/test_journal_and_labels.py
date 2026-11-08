from __future__ import annotations

from datetime import date

import pytest

from nutritensor.services.journal import csv_safe, date_bounds
from nutritensor.services.labels import parse_label


def test_india_date_range_crosses_utc_day_correctly():
    start, end = date_bounds(date(2026, 10, 17), date(2026, 10, 17), "Asia/Kolkata")
    assert start == "2026-10-16T18:30:00+00:00"
    assert end == "2026-10-17T18:30:00+00:00"


def test_dst_date_range_uses_calendar_day_not_fixed_24_hours():
    from datetime import datetime
    start, end = date_bounds(date(2026, 3, 8), date(2026, 3, 8), "America/New_York")
    elapsed = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    assert elapsed.total_seconds() == 23 * 3600


@pytest.mark.parametrize("text", ["=SUM(A1)", "+cmd", "-cmd", "@SUM(A1)", "  =bad"])
def test_export_neutralizes_spreadsheet_formulas(text):
    assert csv_safe(text).startswith("'")


def test_label_parser_preserves_basis_and_converts_units():
    result = parse_label("Per 100 g\nEnergy 120 kcal\nProtein 6000 mg\nCarbohydrate 18 g\nFat 3 g\nSodium 0.12 g")
    assert result["basis"] == "100g"
    assert result["nutrients"]["protein_g"] == 6
    assert result["nutrients"]["sodium_mg"] == 120
    assert result["nutrients"]["fiber_g"] is None
    assert result["needs_confirmation"]


def test_unknown_label_basis_does_not_assume_per_100g():
    result = parse_label("Energy 100 kcal. Protein 3 g")
    assert result["basis"] == "unknown"
    assert result["serving_grams"] is None
