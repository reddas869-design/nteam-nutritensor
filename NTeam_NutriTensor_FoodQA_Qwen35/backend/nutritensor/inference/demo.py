"""Explicit deterministic demo provider. It never pretends to inspect a photograph."""

import json

from nutritensor.core.errors import GenerationCancelled, VisionUnavailable
from nutritensor.domain.models import ModelCapabilities, RuntimeStats
from nutritensor.inference.contracts import GenerationRequest, GenerationResult


class DemoProvider:
    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            backend="demo", model_label="Interactive demo · no model loaded", loaded=True,
            vision=False, thinking=False, quantization="none", context_tokens=4096,
            max_new_tokens=384, device="browser / CPU",
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if request.cancel.is_set():
            raise GenerationCancelled("Analysis cancelled")
        if request.image_path:
            raise VisionUnavailable("Demo mode cannot identify images. Enter foods or open the sample meal.")
        if request.purpose == "identify":
            return GenerationResult(json.dumps({"foods": []}), RuntimeStats(backend="demo"))
        return GenerationResult(
            "This is an illustrative meal. The application scales each food's per-100-g values "
            "by your selected portion and adds them. Review portions and source records before "
            "using a live analysis",
            RuntimeStats(backend="demo"),
        )

    def close(self) -> None:
        return None
