"""API and persistence contracts. Nutrient absence is represented by null, never zero."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Stage(StrEnum):
    INTAKE = "intake"
    IDENTIFY = "identify"
    RETRIEVE = "retrieve"
    CALCULATE = "calculate"
    REVIEW = "review"
    EXPLAIN = "explain"
    COMPLETE = "complete"


class Nutrients(Contract):
    energy_kcal: float | None = Field(default=None, ge=0, le=100000)
    protein_g: float | None = Field(default=None, ge=0, le=100000)
    carbohydrate_g: float | None = Field(default=None, ge=0, le=100000)
    fat_g: float | None = Field(default=None, ge=0, le=100000)
    fiber_g: float | None = Field(default=None, ge=0, le=100000)
    sugar_g: float | None = Field(default=None, ge=0, le=100000)
    sodium_mg: float | None = Field(default=None, ge=0, le=1000000)

    def scaled(self, factor: float) -> Nutrients:
        if not math.isfinite(factor) or factor < 0:
            raise ValueError("Scaling factor must be finite and nonnegative")
        return Nutrients(**{
            key: None if value is None else round(value * factor, 4)
            for key, value in self.model_dump().items()
        })

    @classmethod
    def zero(cls) -> Nutrients:
        return cls(**{field: 0 for field in cls.model_fields})


class Source(Contract):
    provider: str = Field(min_length=1, max_length=120)
    record_id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=2000)
    retrieved_at: str = Field(max_length=64)
    license: str = Field(default="Unspecified; verify before redistribution", max_length=300)
    basis: Literal["per_100g", "recipe"] = "per_100g"
    is_demo: bool = False

    @field_validator("url")
    @classmethod
    def safe_source_url(cls, value: str | None) -> str | None:
        if value and not value.startswith(("https://", "http://")):
            raise ValueError("Source URLs must use HTTP or HTTPS")
        return value


class Serving(Contract):
    label: str = Field(min_length=1, max_length=80)
    grams: float = Field(gt=0, le=20000)


class FoodRecord(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_.:-]{1,120}$")
    name: str = Field(min_length=1, max_length=300)
    aliases: list[str] = Field(default_factory=list, max_length=40)
    category: str = Field(default="Other", max_length=80)
    preparation: str = Field(default="unspecified", max_length=120)
    nutrients: Nutrients
    source: Source
    servings: list[Serving] = Field(default_factory=list, max_length=20)
    allergens: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=2000)

    @field_validator("aliases", "allergens")
    @classmethod
    def bounded_strings(cls, values: list[str]) -> list[str]:
        if any(len(value) > 150 for value in values):
            raise ValueError("A metadata string is too long")
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class FoodMatch(Contract):
    food: FoodRecord
    score: float = Field(ge=0, le=1)
    matched_alias: str
    exact: bool = False


class FoodSelection(Contract):
    food_id: str = Field(min_length=1, max_length=120)
    grams: float = Field(gt=0, le=5000)
    portion_source: Literal["weighed", "user_estimate", "label", "image_estimate"] = "user_estimate"
    uncertainty_percent: float = Field(default=20, ge=0, le=80)

    @model_validator(mode="after")
    def require_image_uncertainty(self) -> FoodSelection:
        if self.portion_source == "image_estimate" and self.uncertainty_percent < 25:
            object.__setattr__(self, "uncertainty_percent", 25.0)
        return self


class Candidate(Contract):
    label: str = Field(min_length=1, max_length=160)
    confidence: float = Field(default=0.5, ge=0, le=1)
    grams: float | None = Field(default=None, gt=0, le=5000)
    evidence: str = Field(default="", max_length=300)
    food_id: str | None = None
    alternatives: list[FoodMatch] = Field(default_factory=list, max_length=5)


class AnalysisRequest(Contract):
    image_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    source_analysis_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    description: str = Field(default="", max_length=3000)
    items: list[FoodSelection] = Field(default_factory=list, max_length=30)
    meal_name: str = Field(default="My meal", min_length=1, max_length=100)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] = "lunch"
    language: Literal["en", "bn"] = "en"
    detailed: bool = False
    confirmed: bool = False

    @field_validator("description")
    @classmethod
    def trim_description(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def need_input(self) -> AnalysisRequest:
        if not self.image_id and not self.description and not self.items:
            raise ValueError("Provide an image, description, or food selections")
        if self.confirmed and not self.items:
            raise ValueError("Confirmed analyses must contain selected foods")
        return self


class PortionResult(Contract):
    food: FoodRecord
    grams: float
    portion_source: str
    uncertainty_percent: float
    nutrients: Nutrients
    lower: Nutrients
    upper: Nutrients


class QualityFlag(Contract):
    code: str
    severity: Literal["info", "warning", "error"]
    message: str
    item_id: str | None = None


class EvidenceSummary(Contract):
    statements: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)


class RuntimeStats(Contract):
    queue_ms: float = 0
    total_ms: float = 0
    model_ms: float = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tokens_per_second: float | None = None
    gpu_peak_mb: float | None = None
    cache_hit: bool = False
    backend: str = "none"


class AnalysisResult(Contract):
    id: str
    created_at: str
    meal_name: str
    meal_type: str
    mode: Literal["live", "demo"]
    needs_confirmation: bool
    candidates: list[Candidate]
    portions: list[PortionResult]
    totals: Nutrients
    lower: Nutrients
    upper: Nutrients
    coverage: dict[str, float]
    flags: list[QualityFlag]
    evidence: EvidenceSummary
    explanation: str
    stats: RuntimeStats
    catalog_version: str
    image_id: str | None = None


class JobEvent(Contract):
    sequence: int
    job_id: str
    stage: Stage
    state: Literal["started", "completed", "warning", "failed", "cancelled"]
    message: str
    timestamp: str
    progress: float = Field(ge=0, le=1)
    detail: dict = Field(default_factory=dict)


class JobView(Contract):
    id: str
    status: JobStatus
    created_at: str
    updated_at: str
    error: str | None = None
    result: AnalysisResult | None = None
    events: list[JobEvent] = Field(default_factory=list)


class JournalEntry(Contract):
    id: str
    analysis_id: str
    meal_name: str
    meal_type: str
    eaten_at: str
    notes: str = Field(default="", max_length=3000)
    result: AnalysisResult


class JournalCreate(Contract):
    analysis_id: str
    eaten_at: datetime = Field(default_factory=utc_now)
    notes: str = Field(default="", max_length=3000)

    @field_validator("eaten_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("eaten_at must include a timezone")
        return value.astimezone(timezone.utc)


class JournalUpdate(Contract):
    meal_name: str | None = Field(default=None, min_length=1, max_length=100)
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    eaten_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=3000)

    @field_validator("eaten_at")
    @classmethod
    def valid_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("eaten_at must include timezone")
        return value


class Preferences(Contract):
    language: Literal["en", "bn"] = "en"
    units: Literal["metric"] = "metric"
    reduced_motion: bool = False
    save_images: bool = False
    energy_target: int | None = Field(default=None, ge=500, le=10000)
    protein_target: int | None = Field(default=None, ge=10, le=500)
    dietary_notes: str = Field(default="", max_length=1000)
    timezone: str = Field(default="Asia/Kolkata", max_length=80)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("Unknown IANA timezone") from exc
        return value


class RecipeIngredient(Contract):
    food_id: str
    grams: float = Field(gt=0, le=20000)


class RecipeCreate(Contract):
    name: str = Field(min_length=1, max_length=150)
    ingredients: list[RecipeIngredient] = Field(min_length=1, max_length=60)
    cooked_weight_g: float = Field(gt=0, le=50000)
    servings: int = Field(default=1, ge=1, le=100)
    notes: str = Field(default="", max_length=2000)


class Recipe(RecipeCreate):
    id: str
    created_at: str
    per_100g: Nutrients
    total: Nutrients
    sources: list[Source]
    coverage: dict[str, float]


class ChatRequest(Contract):
    message: str = Field(min_length=1, max_length=2000)
    analysis_id: str | None = None
    language: Literal["en", "bn"] = "en"


class ChatAnswer(Contract):
    answer: str
    evidence: list[str]
    mode: str
    stats: RuntimeStats


class LoginRequest(Contract):
    username: str = Field(default="owner", min_length=1, max_length=32)
    password: str = Field(default="", max_length=1024)


class SessionView(Contract):
    authenticated: bool
    username: str = "owner"
    csrf_token: str | None = None
    mode: str
    expires_at: str | None = None


class ModelCapabilities(Contract):
    backend: str
    model_label: str
    loaded: bool
    vision: bool
    thinking: bool
    quantization: str
    context_tokens: int
    max_new_tokens: int
    device: str
    catalog_count: int = 0
    catalog_version: str = ""


class ErrorPayload(Contract):
    error: str
    message: str
    request_id: str | None = None
    details: list[dict] = Field(default_factory=list)
