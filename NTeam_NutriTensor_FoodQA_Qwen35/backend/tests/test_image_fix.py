"""Regression checks for Qwen photo predictions and conservative catalog matching."""
import pytest
from nutritensor.agents.roles import RetrievalAgent, match_visual_label
from nutritensor.domain.models import Candidate
from nutritensor.inference.parsing import parse_food_observation
from nutritensor.core.errors import NoFoodDetected
from test_food_only import context


def test_appearance_adjectives_match_exact_fruit():
    from pathlib import Path
    from nutritensor.nutrition.catalog import Catalog

    catalog = Catalog.load(Path('backend/nutritensor/resources/fruit_catalog.json'))
    food, _ = match_visual_label(catalog, 'a sliced red apple')
    assert food is not None
    assert food.name.lower() == 'apple'
    assert len(catalog) >= 8


def test_appearance_adjectives_are_strict(catalog):
    for label in ('rice cake', 'fried rice', 'unknown stone', 'rice pudding'):
        food, _ = match_visual_label(catalog, label)
        assert food is None
    food, _ = match_visual_label(catalog, 'fresh rice')
    assert food is None


def test_positive_observation_without_confidence_has_conservative_threshold():
    parsed = parse_food_observation('{"contains_food":true,"foods":[{"label":"rice"}]}')
    assert parsed[0].confidence == 0.75


@pytest.mark.asyncio
async def test_one_unmatched_prediction_does_not_discard_valid_food(catalog):
    ctx = context()
    ctx.candidates = [
        Candidate(label='rice', confidence=0.98),
        Candidate(label='unknown object', confidence=0.88),
    ]
    await RetrievalAgent(catalog).run(ctx)
    assert len(ctx.selections) == 1
    assert ctx.selections[0].food_id == 'demo:rice'
    assert ctx.evidence.missing_information


@pytest.mark.asyncio
async def test_no_safe_catalog_matches_still_fails(catalog):
    ctx = context()
    ctx.candidates = [Candidate(label='unknown object', confidence=0.98)]
    with pytest.raises(NoFoodDetected):
        await RetrievalAgent(catalog).run(ctx)
