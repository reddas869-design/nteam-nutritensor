from __future__ import annotations

import asyncio
import threading
import time

import pytest

from nutritensor.core.errors import QueueFull
from nutritensor.domain.models import AnalysisRequest, JobStatus, ModelCapabilities, RuntimeStats
from nutritensor.inference.contracts import GenerationRequest, GenerationResult
from nutritensor.inference.gateway import ModelGateway
from nutritensor.inference.parsing import InvalidModelOutput, decode_final, final_text, parse_candidates
from nutritensor.storage.database import timestamp


class BlockingProvider:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.active = 0
        self.maximum_active = 0
        self.finished = threading.Event()

    def generate(self, request):
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        self.started.set()
        self.release.wait(timeout=3)
        self.active -= 1
        self.finished.set()
        return GenerationResult("complete", RuntimeStats())

    def close(self):
        pass


@pytest.mark.asyncio
async def test_cancelled_caller_does_not_release_gpu_gate_before_worker_finishes():
    provider = BlockingProvider()
    gateway = ModelGateway(provider, capacity=3)
    first_request = GenerationRequest(system="test", prompt="one")
    first = asyncio.create_task(gateway.generate(first_request))
    await asyncio.to_thread(provider.started.wait, 1)
    assert provider.started.is_set()
    first.cancel()
    second = asyncio.create_task(gateway.generate(GenerationRequest(system="test", prompt="two")))
    await asyncio.sleep(0.02)
    assert first_request.cancel.is_set()
    assert not first.done()
    assert provider.active == 1
    provider.release.set()
    with pytest.raises(asyncio.CancelledError):
        await first
    await second
    assert provider.maximum_active == 1
    assert gateway.pending == 0


@pytest.mark.asyncio
async def test_model_admission_is_bounded():
    provider = BlockingProvider()
    gateway = ModelGateway(provider, capacity=1)
    first = asyncio.create_task(gateway.generate(GenerationRequest(system="test", prompt="one")))
    await asyncio.to_thread(provider.started.wait, 1)
    with pytest.raises(QueueFull):
        await gateway.generate(GenerationRequest(system="test", prompt="two"))
    provider.release.set()
    await first


def test_restart_marks_interrupted_jobs_failed(database):
    request = AnalysisRequest(description="rice")
    job_id, _ = database.create_job("alice", request)
    database.set_status(job_id, JobStatus.RUNNING)
    assert database.recover_interrupted_jobs() == 1
    recovered = database.get_job(job_id, "alice")
    assert recovered.status == JobStatus.FAILED
    assert "restarted" in recovered.error


def test_terminal_job_cannot_be_overwritten(database):
    job_id, _ = database.create_job("alice", AnalysisRequest(description="rice"))
    assert database.set_status(job_id, JobStatus.CANCELLED)
    assert not database.set_status(job_id, JobStatus.RUNNING)
    assert database.get_job(job_id, "alice").status == JobStatus.CANCELLED


def test_untrusted_output_is_parsed_without_execution():
    payload = '<think>hidden</think>```json\n{"foods":[{"label":"rice","confidence":0.8,"grams":null,"evidence":"visible grains"}]}\n```'
    result = parse_candidates(payload)
    assert result[0].label == "rice"
    assert result[0].grams is None
    assert "hidden" not in final_text(payload)


def test_incomplete_thinking_is_not_exposed():
    assert final_text("<think>unfinished private analysis") == ""
    assert final_text("<think>analysis</think>Final answer") == "Final answer"


def test_thinking_delimiters_survive_tokenizer_special_token_filtering():
    class Tokenizer:
        all_special_tokens = ["<think>", "</think>", "<end_of_turn>"]

        def decode(self, ids, skip_special_tokens):
            assert not skip_special_tokens
            return ids

    tokenizer = Tokenizer()
    assert decode_final(tokenizer, "private deliberation</think>Answer<end_of_turn>", True) == "Answer"
    assert decode_final(tokenizer, "unfinished private deliberation", True) == ""
    assert decode_final(tokenizer, "Simple answer<end_of_turn>", False) == "Simple answer"


@pytest.mark.asyncio
async def test_expired_queued_image_fails_without_killing_worker(settings, database, catalog):
    from nutritensor.agents.coordinator import Coordinator
    from nutritensor.core.telemetry import Metrics
    from nutritensor.inference.demo import DemoProvider
    from nutritensor.services.images import ImageService
    from test_security_and_images import image_bytes

    images = ImageService(settings, database)
    gateway = ModelGateway(DemoProvider(), capacity=4)
    coordinator = Coordinator(settings, database, catalog, gateway, images, Metrics())
    await coordinator.start()
    try:
        uploaded = images.save("alice", image_bytes())
        bad_id = coordinator.submit("alice", AnalysisRequest(image_id=uploaded["id"]))
        images.remove("alice", uploaded["id"])
        good_id = coordinator.submit("bob", AnalysisRequest(description="rice"))
        await asyncio.wait_for(coordinator.queue.join(), timeout=3)
        assert database.get_job(bad_id, "alice").status == JobStatus.FAILED
        assert database.get_job(good_id, "bob").status == JobStatus.COMPLETE
    finally:
        await coordinator.stop()


@pytest.mark.parametrize("payload", [
    "run __import__('os').system('bad')",
    '{"foods":"rice"}',
    '{"foods":[{"label":"rice","grams":-1}]}',
    '{"foods":[]}',
])
def test_invalid_model_output_is_rejected(payload):
    with pytest.raises(InvalidModelOutput):
        parse_candidates(payload)


@pytest.mark.asyncio
async def test_one_pending_job_per_owner_but_three_users_are_admitted(settings, database, catalog):
    from nutritensor.agents.coordinator import Coordinator
    from nutritensor.core.telemetry import Metrics
    from nutritensor.inference.demo import DemoProvider
    from nutritensor.services.images import ImageService

    gateway = ModelGateway(DemoProvider(), capacity=4)
    coordinator = Coordinator(settings, database, catalog, gateway, ImageService(settings, database), Metrics())
    await coordinator.start()
    try:
        request = AnalysisRequest(description="rice")
        first = coordinator.submit("alice", request, "retry")
        assert coordinator.submit("alice", request, "retry") == first
        with pytest.raises(QueueFull):
            coordinator.submit("alice", request)
        second = coordinator.submit("bravo", request)
        third = coordinator.submit("charlie", request)
        await asyncio.wait_for(coordinator.queue.join(), timeout=3)
        for job, owner in [(first, "alice"), (second, "bravo"), (third, "charlie")]:
            assert database.get_job(job, owner).status == JobStatus.COMPLETE
    finally:
        await coordinator.stop()
