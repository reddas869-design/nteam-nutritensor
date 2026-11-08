"""Meal-scoped LLM Q&A regression tests, without actual GPU requirements."""
from dataclasses import replace

import pytest

from nutritensor.domain.models import ChatRequest, RuntimeStats
from nutritensor.inference.contracts import GenerationResult
from nutritensor.services.chat import ChatService, REFUSAL, _topic_response
from conftest import completed_job


class FakeGateway:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return GenerationResult(self.replies.pop(0), RuntimeStats(backend="mock-qwen"))


@pytest.mark.parametrize("output", ["maybe", "{}", '{"food_related":"true"}', '{"food_related":1}', '{"food_related":false}', "<think>unclosed"])
def test_scope_fail_closed(output):
    assert _topic_response(output) is False


def test_scope_accepts_explicit_boolean():
    assert _topic_response('{"food_related":true}') is True


@pytest.mark.asyncio
async def test_qwen_food_question_generates_answer(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    gateway = FakeGateway('{"food_related":true}', "This meal has approximately 393 kcal; the portion is an estimate.")
    service = ChatService(client.app.state.database, gateway, replace(client.app.state.settings, mode="live"))
    # Find the stored owner through the session table, not by bypassing owner checks.
    import sqlite3
    with client.app.state.database.connection() as connection:
        owner = connection.execute("SELECT owner_id FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
    reply = await service.answer(owner, ChatRequest(message="How many calories does this meal have?", analysis_id=job["id"]))
    assert reply.stats.backend == "mock-qwen"
    assert "393" in reply.answer
    assert len(gateway.requests) == 2
    assert gateway.requests[0].purpose == "food_qa_scope"
    assert gateway.requests[1].purpose == "food_qa_answer"
    assert "393" in gateway.requests[1].prompt
    assert "only" in gateway.requests[1].system.lower()


@pytest.mark.asyncio
async def test_refuse_unrelated_after_classifier(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    with client.app.state.database.connection() as connection:
        owner = connection.execute("SELECT owner_id FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
    gateway = FakeGateway('{"food_related":false}')
    service = ChatService(client.app.state.database, gateway, replace(client.app.state.settings, mode="live"))
    reply = await service.answer(owner, ChatRequest(message="What happened in the election?", analysis_id=job["id"]))
    assert reply.answer == REFUSAL
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_block_poem_even_with_food_name(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    with client.app.state.database.connection() as connection:
        owner = connection.execute("SELECT owner_id FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
    gateway = FakeGateway('{"food_related":true}', 'should not run')
    service = ChatService(client.app.state.database, gateway, replace(client.app.state.settings, mode="live"))
    reply = await service.answer(owner, ChatRequest(message="Write a poem about mangoes", analysis_id=job["id"]))
    assert reply.answer == REFUSAL
    assert not gateway.requests


@pytest.mark.asyncio
async def test_fail_closed_if_model_classification_invalid(client, session, meal_request):
    job = completed_job(client, session, meal_request)
    with client.app.state.database.connection() as connection:
        owner = connection.execute("SELECT owner_id FROM jobs WHERE id=?", (job["id"],)).fetchone()[0]
    gateway = FakeGateway('I refuse to emit JSON')
    service = ChatService(client.app.state.database, gateway, replace(client.app.state.settings, mode="live"))
    reply = await service.answer(owner, ChatRequest(message="Is this food cooked?", analysis_id=job["id"]))
    assert reply.answer == REFUSAL
    assert len(gateway.requests) == 1


@pytest.mark.asyncio
async def test_analysis_ownership_is_enforced(client, session, meal_request):
    from nutritensor.core.errors import NotFound
    job = completed_job(client, session, meal_request)
    gateway = FakeGateway('{"food_related":true}', 'do not show')
    service = ChatService(client.app.state.database, gateway, replace(client.app.state.settings, mode="live"))
    with pytest.raises(NotFound):
        await service.answer("another-owner", ChatRequest(message="Calories in this food?", analysis_id=job["id"]))
    assert not gateway.requests
