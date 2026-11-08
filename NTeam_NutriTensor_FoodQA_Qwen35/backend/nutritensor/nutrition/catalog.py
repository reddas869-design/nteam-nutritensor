"""Immutable, provenance-preserving catalog with deterministic lexical retrieval."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from nutritensor.core.errors import CatalogUnavailable, NotFound
from nutritensor.domain.models import FoodMatch, FoodRecord


def normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE).split())


class Catalog:
    def __init__(self, records: list[FoodRecord], allow_demo: bool = False):
        self._records: dict[str, FoodRecord] = {}
        self._terms: dict[str, list[tuple[str, str]]] = {}
        for record in records:
            if record.id in self._records:
                raise ValueError(f"Duplicate catalog ID: {record.id}")
            if record.source.is_demo and not allow_demo:
                raise ValueError("Demo nutrition records are forbidden in the live catalog")
            self._records[record.id] = record
            terms = [record.name, *record.aliases]
            self._terms[record.id] = [(term, normalize(term)) for term in terms]
        serialized = json.dumps(
            [record.model_dump(mode="json") for record in sorted(records, key=lambda item: item.id)],
            sort_keys=True, ensure_ascii=False,
        )
        self.version = hashlib.sha256(serialized.encode()).hexdigest()[:16]

    @classmethod
    def load(cls, path: Path, allow_demo: bool = False) -> Catalog:
        if not path.exists():
            return cls([], allow_demo=allow_demo)
        if path.stat().st_size > 200 * 1024 * 1024:
            raise CatalogUnavailable("Catalog exceeds the 200 MB safety bound; use a selected subset")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload = payload.get("foods", [])
        if not isinstance(payload, list):
            raise CatalogUnavailable("Catalog must be a list of validated food records")
        return cls([FoodRecord.model_validate(item) for item in payload], allow_demo=allow_demo)

    def __len__(self) -> int:
        return len(self._records)

    def get(self, food_id: str) -> FoodRecord:
        if food_id not in self._records:
            raise NotFound("Food record not found in the current catalog")
        return self._records[food_id].model_copy(deep=True)

    def all(self, category: str | None = None) -> list[FoodRecord]:
        records = self._records.values()
        return [record.model_copy(deep=True) for record in records if not category or record.category == category]

    def categories(self) -> list[str]:
        return sorted({record.category for record in self._records.values()})

    def search(self, query: str, limit: int = 10, category: str | None = None) -> list[FoodMatch]:
        needle = normalize(query)
        if not needle:
            return [FoodMatch(food=record, score=0, matched_alias=record.name) for record in self.all(category)[:limit]]
        needle_tokens = set(needle.split())
        matches: list[FoodMatch] = []
        for food_id, terms in self._terms.items():
            record = self._records[food_id]
            if category and record.category != category:
                continue
            best_score, best_alias, exact = 0.0, record.name, False
            for alias, haystack in terms:
                if needle == haystack:
                    score, is_exact = 1.0, True
                else:
                    tokens = set(haystack.split())
                    overlap = len(tokens & needle_tokens) / max(1, len(tokens | needle_tokens))
                    sequence = SequenceMatcher(None, needle, haystack).ratio()
                    prefix = 0.15 if haystack.startswith(needle) else 0
                    contained = 0.2 if needle in haystack else 0
                    score = min(0.96, 0.55 * overlap + 0.35 * sequence + prefix + contained)
                    is_exact = False
                if score > best_score:
                    best_score, best_alias, exact = score, alias, is_exact
            if best_score >= 0.2:
                matches.append(FoodMatch(
                    food=record.model_copy(deep=True), score=round(best_score, 4),
                    matched_alias=best_alias, exact=exact,
                ))
        return sorted(matches, key=lambda item: (-item.score, item.food.name.casefold()))[:limit]

    def match_description(self, description: str, limit: int = 12) -> list[FoodMatch]:
        text = f" {normalize(description)} "
        matched: list[FoodMatch] = []
        for food_id, terms in self._terms.items():
            for alias, term in sorted(terms, key=lambda item: -len(item[1])):
                if term and f" {term} " in text:
                    matched.append(FoodMatch(food=self.get(food_id), score=1, matched_alias=alias, exact=True))
                    break
        return matched[:limit]

    def require_available(self) -> None:
        if not self._records:
            raise CatalogUnavailable("No nutrition catalog loaded. Import FoodData Central data before analysis.")
