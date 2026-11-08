"""Optional CPU OCR and conservative nutrition-label extraction."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from nutritensor.domain.models import Nutrients


LABEL_PATTERNS = {
    "energy_kcal": (r"(?:energy|calories)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(kcal|cal)", "kcal"),
    "protein_g": (r"protein\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "g"),
    "carbohydrate_g": (r"(?:total\s+)?carbohydrates?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "g"),
    "fat_g": (r"(?:total\s+)?fat\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "g"),
    "fiber_g": (r"(?:dietary\s+)?fi(?:ber|bre)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "g"),
    "sugar_g": (r"(?:total\s+)?sugars?\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "g"),
    "sodium_mg": (r"sodium\s*[:\-]?\s*(\d+(?:[.,]\d+)?)\s*(mg|g)", "mg"),
}


def parse_label(text: str) -> dict:
    values = {}
    for field, (pattern, desired) in LABEL_PATTERNS.items():
        found = re.search(pattern, text, flags=re.IGNORECASE)
        if not found:
            continue
        value = float(found.group(1).replace(",", "."))
        unit = found.group(2).lower()
        if desired == "mg" and unit == "g":
            value *= 1000
        elif desired == "g" and unit == "mg":
            value /= 1000
        values[field] = value
    basis_match = re.search(r"per\s*(100\s*g|serving|portion)", text, flags=re.IGNORECASE)
    serving_match = re.search(r"serving\s*(?:size)?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*g", text, flags=re.IGNORECASE)
    return {
        "nutrients": Nutrients(**values).model_dump(),
        "basis": basis_match.group(1).lower().replace(" ", "") if basis_match else "unknown",
        "serving_grams": float(serving_match.group(1)) if serving_match else None,
        "needs_confirmation": True,
        "warning": "OCR may misread columns, decimals or units. Verify every field against the package.",
    }


def read_label(path: Path, enabled: bool) -> dict:
    if not enabled:
        return {"available": False, "message": "CPU OCR is disabled. You can type the label text.", "text": ""}
    try:
        import pytesseract
    except ImportError:
        return {"available": False, "message": "Install the OCR extra and the Tesseract executable.", "text": ""}
    try:
        with Image.open(path) as image:
            text = pytesseract.image_to_string(image, config="--psm 6", timeout=15)[:10000]
    except (RuntimeError, pytesseract.TesseractNotFoundError):
        return {"available": False, "message": "OCR could not complete. Enter label text manually.", "text": ""}
    return {"available": True, "text": text, **parse_label(text)}
