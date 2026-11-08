"""Bounded specialist agents; each role has fixed inputs, outputs and permissions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from nutritensor.agents.context import AgentContext
from nutritensor.core.config import Settings
from nutritensor.core.errors import AppError, GenerationCancelled, NoFoodDetected, VisionUnavailable
from nutritensor.domain.models import Candidate, FoodSelection, FoodRecord, Nutrients, QualityFlag, Source, Stage
from nutritensor.inference.contracts import GenerationRequest
from nutritensor.inference.gateway import ModelGateway
from nutritensor.inference.parsing import InvalidModelOutput, parse_food_observation, safe_explanation
from nutritensor.inference.prompts import EXPLANATION_SYSTEM, IDENTIFICATION_SYSTEM
from nutritensor.nutrition.calculator import aggregate, calculate_portions, quality_review
from nutritensor.nutrition.catalog import Catalog, normalize
from nutritensor.nutrition.policy import RETRY_MESSAGE, food_names_only
from nutritensor.agents.model_food import (
    VISION_SYSTEM, TEXT_FOOD_SYSTEM, NUTRITION_SYSTEM,
    parse_observations, parse_nutrition,
)



# Restrict vision label normalization to non-culinary visual adjectives.
# NEVER drop recipe/preparation words such as "pie", "juice", "cake",
# "fried", or "cooked": those have different nutrient composition.
_VISUAL_ADJECTIVES = frozenset({
    "a", "an", "the", "red", "green", "yellow", "ripe", "fresh", "whole",
    "sliced", "slice", "chopped", "cut", "halved",
    "small", "large", "medium", "single",
})


def match_visual_label(catalog: Catalog, label: str):
    """Find one unique exact catalog record, ignoring appearance-only words."""
    literal = normalize(label)
    stripped = " ".join(token for token in literal.split() if token not in _VISUAL_ADJECTIVES)
    for term in dict.fromkeys((literal, stripped)):
        if not term:
            continue
        matches = catalog.search(term, limit=2)
        if matches and matches[0].exact and not (len(matches) > 1 and matches[1].exact):
            # Appearance normalization is only valid for raw fruit records.
            # Never translate "fresh rice" to "steamed rice", for instance.
            if term != literal and matches[0].food.category.casefold() != "fruit":
                continue
            return matches[0].food, matches
    return None, catalog.search(label, limit=3)


class IdentificationAgent:
    def __init__(self, catalog: Catalog, gateway: ModelGateway, settings: Settings):
        self.catalog = catalog
        self.gateway = gateway
        self.settings = settings

    async def run(self, context: AgentContext) -> None:
        context.check_cancelled()
        active = context.transient_catalog or self.catalog
        if context.request.items:
            context.selections = context.request.items
            context.candidates = [Candidate(
                label=active.get(item.food_id).name,
                confidence=1, grams=item.grams,
                food_id=item.food_id, evidence="Selected by the user",
            ) for item in context.request.items]
            await context.emit(Stage.IDENTIFY, "completed", "Using confirmed foods", 0.3, None)
            return
        if not self.settings.is_demo and (context.image_path or context.request.description):
            context.model_only = True
            is_photo = context.image_path is not None
            system = VISION_SYSTEM if is_photo else TEXT_FOOD_SYSTEM
            prompt = (
                "Observe visible edible foods. Return compact JSON only. "
                "Report quantity and approximate total grams when reasonably visible."
                if is_photo else context.request.description[:2000]
            )
            generated = await self.gateway.generate(GenerationRequest(
                system=system, prompt=prompt, image_path=context.image_path,
                cancel=context.cancel, max_new_tokens=self.settings.max_new_tokens,
                purpose="identify",
            ))
            context.add_stats(generated.stats)
            try:
                observations = parse_observations(generated.text)
            except InvalidModelOutput:
                # One limited retry for malformed response, not for genuine non-food.
                retry = await self.gateway.generate(GenerationRequest(
                    system=system, prompt=prompt + "\nOutput one complete valid JSON object, no prose.",
                    image_path=context.image_path, cancel=context.cancel,
                    max_new_tokens=self.settings.max_new_tokens, purpose="identify_retry",
                ))
                context.add_stats(retry.stats)
                try:
                    observations = parse_observations(retry.text)
                except InvalidModelOutput as exc:
                    raise NoFoodDetected(RETRY_MESSAGE) from exc
            if not observations:
                raise NoFoodDetected(RETRY_MESSAGE)
            context.model_foods = observations
            context.candidates = [Candidate(
                label=food.name, confidence=food.confidence, grams=food.grams,
                evidence=((food.quantity + "; " if food.quantity else "") + food.evidence)[:300],
            ) for food in observations]
            context.evidence.statements.append(
                "Food recognition and portions are Qwen3.5 model observations, not measured facts."
            )
        else:
            context.candidates = food_names_only(context.request.description, self.catalog)
        await context.emit(
            Stage.IDENTIFY, "completed", f"Found {len(context.candidates)} food candidates",
            0.3, {"candidate_count": len(context.candidates)},
        )


class RetrievalAgent:
    def __init__(self, catalog: Catalog, gateway: ModelGateway | None = None, settings: Settings | None = None):
        self.catalog = catalog
        self.gateway = gateway
        self.settings = settings

    async def _model_records(self, context: AgentContext) -> None:
        """Use the ntemma model for unverified estimates, not a whitelist."""
        observations = context.model_foods
        records: list[FoodRecord] = []
        for start in range(0, len(observations), 2):
            chunk = observations[start:start + 2]
            request_data = [
                {"index": i, "food": item.name, "preparation": item.preparation}
                for i, item in enumerate(chunk)
            ]
            nutrients = None
            try:
                reply = await self.gateway.generate(GenerationRequest(
                    system=NUTRITION_SYSTEM,
                    prompt=json.dumps(request_data, ensure_ascii=False),
                    cancel=context.cancel, max_new_tokens=self.settings.max_new_tokens,
                    purpose="nutrition_estimate",
                ))
                context.add_stats(reply.stats)
                nutrients = parse_nutrition(reply.text, len(chunk))
            except GenerationCancelled:
                raise
            except (AppError, InvalidModelOutput, ValueError):
                # Fall back to per-food generation if a multi-item response was truncated.
                pass
            for i, item in enumerate(chunk):
                estimated = nutrients[i] if nutrients is not None else None
                if estimated is None:
                    try:
                        reply = await self.gateway.generate(GenerationRequest(
                            system=NUTRITION_SYSTEM,
                            prompt=json.dumps([{"index": 0, "food": item.name,
                                                "preparation": item.preparation}], ensure_ascii=False),
                            cancel=context.cancel, max_new_tokens=self.settings.max_new_tokens,
                            purpose="nutrition_estimate_retry",
                        ))
                        context.add_stats(reply.stats)
                        estimated = parse_nutrition(reply.text, 1)[0]
                    except GenerationCancelled:
                        raise
                    except (AppError, InvalidModelOutput, ValueError):
                        estimated = Nutrients()  # Unknown, never fabricated by code.
                        context.evidence.missing_information.append(
                            f"No reliable model estimate for {item.name}; its nutrients remain unknown."
                        )
                unique_id = f"ntemma:{context.job_id[:12]}:{start+i}"
                record = FoodRecord(
                    id=unique_id, name=item.name, aliases=[], category="Model-recognized food",
                    preparation=item.preparation,
                    nutrients=estimated,
                    source=Source(
                        provider="(unverified ntemma estimate)",
                        record_id=unique_id, title="Unverified model estimate per 100 g;",
                        retrieved_at=datetime.now(timezone.utc).isoformat(),
                        license="ntemma-generated estimate; not a licensed nutrient dataset",
                        basis="per_100g", is_demo=False,
                    ),
                    notes=(f"Estimated visible amount: {item.quantity}. " if item.quantity else "")
                          + ("100 g reference only: image weight unknown. " if item.grams is None else "Visually estimated edible mass, not measured. ")
                          + "Ingredients and weights cannot be verified from one photo.",
                )
                records.append(record)
                grams = item.grams if item.grams is not None else 100.0
                if item.grams is None:
                    context.evidence.missing_information.append(
                        f"The edible mass of {item.name} could not be estimated visually; "
                        "100 g is only a reference serving, NOT a measured or image-estimated weight."
                    )
                context.selections.append(FoodSelection(
                    food_id=record.id, grams=grams,
                    portion_source="image_estimate" if context.image_path else "user_estimate",
                    uncertainty_percent=80 if context.image_path and item.grams is None else (60 if context.image_path else 40),
                ))
                context.candidates[start + i].food_id = unique_id
                context.evidence.assumptions.append(
                    (f"{item.name}: visually estimated ~{grams:g} g, NOT measured."
                     if item.grams is not None else
                     f"{item.name}: 100 g reference only, visual quantity unknown.")
                )
        context.transient_catalog = Catalog(records)
        context.evidence.statements.append(
            "Per-100-g nutrient values are generated by ntemma; they are NOT verified database figures."
        )

    async def run(self, context: AgentContext) -> None:
        context.check_cancelled()
        if context.model_only:
            await self._model_records(context)
        elif not context.selections:
            selected_ids: set[str] = set()
            for candidate in context.candidates:
                food, matches = match_visual_label(self.catalog, candidate.label)
                candidate.alternatives = matches
                if candidate.food_id:
                    food = self.catalog.get(candidate.food_id)
                if food is None:
                    context.evidence.missing_information.append(
                        f"No nutrition record for identified item: {candidate.label[:80]}"
                    )
                    continue
                candidate.food_id = food.id
                if food.id in selected_ids:
                    continue
                selected_ids.add(food.id)
                grams = 100 if context.image_path else (candidate.grams or 100)
                context.selections.append(FoodSelection(
                    food_id=food.id, grams=grams,
                    portion_source="image_estimate" if context.image_path else "user_estimate",
                    uncertainty_percent=35 if context.image_path else 25,
                ))
        # The camera workflow has no manual grams editor. It saves the
        # explicitly labeled, unverified model estimate without a second job.
        # Other workflows still require explicit confirmation.
        context.needs_confirmation = not (context.request.confirmed or context.model_only)
        if not context.selections:
            raise NoFoodDetected(RETRY_MESSAGE)
        await context.emit(Stage.RETRIEVE, "completed", "Prepared food nutrition estimates", 0.5,
                           {"matched": len(context.selections), "model_only": context.model_only})


class CalculationAgent:
    def __init__(self, catalog: Catalog):
        self.catalog = catalog

    async def run(self, context: AgentContext) -> None:
        context.check_cancelled()
        context.portions = calculate_portions(context.transient_catalog or self.catalog, context.selections)
        context.aggregate = aggregate(context.portions)
        context.evidence.statements.extend([
            "Each nutrient is scaled as per-100-g value × estimated portion grams ÷ 100.",
            "Ranges reflect portion-weight uncertainty only, not model nutrition uncertainty or a statistical interval.",
            "Unknown nutrients remain unknown in the meal total.",
        ])
        await context.emit(Stage.CALCULATE, "completed", "Calculated portions and nutrient ranges", 0.7, None)


class ReviewAgent:
    async def run(self, context: AgentContext) -> None:
        context.check_cancelled()
        context.flags.extend(quality_review(context.portions, not context.needs_confirmation))
        if context.image_path:
            context.evidence.missing_information.append("")
        if context.model_only:
            context.evidence.assumptions.append("ntemma nutrient composition is a rough estimate, not food-table data; confirm recipes and ingredients.")
        else:
            context.evidence.assumptions.append("Source records describe the selected preparation; recipe composition may differ.")
        await context.emit(Stage.REVIEW, "completed", "Checked source coverage and assumptions", 0.84, {"flags": len(context.flags)})


class ExplanationAgent:
    def __init__(self, gateway: ModelGateway, settings: Settings):
        self.gateway = gateway
        self.settings = settings

    async def run(self, context: AgentContext) -> None:
        context.check_cancelled()
        if not context.portions:
            context.explanation = "Select the foods and portions first. There is not enough verified information to calculate this meal."
            return
        evidence = {
            "mode": self.settings.mode,
            "language": context.request.language,
            "totals": context.aggregate.totals.model_dump(),
            "foods": [{"name": item.food.name, "grams": item.grams, "source": item.food.source.provider} for item in context.portions],
            "assumptions": context.evidence.assumptions,
            "missing": context.evidence.missing_information,
        }
        fallback = (
            "The displayed range only covers portion uncertainty."
            "ntemma could be wrong"

        )
        if self.settings.fast_scan and not context.request.detailed:
            context.explanation = fallback
            await context.emit(Stage.EXPLAIN, "completed", "Prepared a calculation summary", 0.95, None)
            return
        try:
            generated = await self.gateway.generate(GenerationRequest(
                system=EXPLANATION_SYSTEM, prompt=json.dumps(evidence, ensure_ascii=False),
                max_new_tokens=self.settings.max_new_tokens,
                thinking=context.request.detailed, cancel=context.cancel, purpose="explanation",
            ))
            context.add_stats(generated.stats)
            answer = safe_explanation(generated.text)
            context.explanation = answer or fallback
            if not answer:
                context.flags.append(QualityFlag(
                    code="explanation_incomplete", severity="info",
                    message="The model did not finish a final answer within its budget. A calculation summary is shown.",
                ))
        except GenerationCancelled:
            raise
        except AppError:
            context.explanation = fallback
            context.flags.append(QualityFlag(
                code="explanation_unavailable", severity="info",
                message="",
            ))
        await context.emit(Stage.EXPLAIN, "completed", "Prepared an evidence-based summary", 0.95, None)
