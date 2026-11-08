"""Optional local llama.cpp/vLLM-compatible endpoint. URL is operator-configured."""

from __future__ import annotations

import base64
import threading
import time

import httpx

from nutritensor.core.config import Settings
from nutritensor.core.errors import GenerationCancelled, ModelUnavailable, VisionUnavailable
from nutritensor.domain.models import ModelCapabilities, RuntimeStats
from nutritensor.inference.contracts import GenerationRequest, GenerationResult
from nutritensor.inference.parsing import final_text


class CompatibleProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=settings.remote_llm_url.rstrip("/") + "/",
            timeout=httpx.Timeout(settings.inference_timeout, connect=10),
            follow_redirects=False,
            # Keep local model requests out of unrelated HTTP_PROXY/SOCKS settings.
            trust_env=False,
        )

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            backend="openai-compatible", model_label=self.settings.remote_llm_model,
            loaded=False, vision=self.settings.remote_supports_vision,
            thinking=False, quantization="endpoint-managed",
            context_tokens=self.settings.context_tokens, max_new_tokens=self.settings.max_new_tokens,
            device="configured inference server",
        )

    def generate(self, request: GenerationRequest) -> GenerationResult:
        with self._lock:
            if request.cancel.is_set():
                raise GenerationCancelled("Analysis cancelled")
            if request.image_path and not self.settings.remote_supports_vision:
                raise VisionUnavailable("The configured endpoint does not declare vision support")
            content: str | list = request.prompt
            if request.image_path:
                image = base64.b64encode(request.image_path.read_bytes()).decode()
                content = [
                    {"type": "text", "text": request.prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}},
                ]
            headers = {}
            if self.settings.remote_llm_key:
                headers["Authorization"] = f"Bearer {self.settings.remote_llm_key}"
            started = time.perf_counter()
            try:
                response = self._client.post("chat/completions", headers=headers, json={
                    "model": self.settings.remote_llm_model,
                    "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": content}],
                    "max_tokens": min(request.max_new_tokens, self.settings.max_new_tokens),
                    "temperature": 0, "stream": False,
                })
                response.raise_for_status()
                payload = response.json()
                text = payload["choices"][0]["message"]["content"]
                if not isinstance(text, str):
                    raise ValueError("Endpoint returned non-text content")
            except (httpx.HTTPError, ValueError, KeyError, IndexError) as exc:
                raise ModelUnavailable("The configured inference endpoint did not return a valid completion") from exc
            if request.cancel.is_set():
                raise GenerationCancelled("Analysis cancelled")
            elapsed = time.perf_counter() - started
            usage = payload.get("usage", {})
            output_tokens = int(usage.get("completion_tokens", 0))
            return GenerationResult(final_text(text), RuntimeStats(
                model_ms=elapsed * 1000, prompt_tokens=int(usage.get("prompt_tokens", 0)),
                completion_tokens=output_tokens,
                tokens_per_second=output_tokens / elapsed if output_tokens else None,
                backend="openai-compatible",
            ))

    def close(self) -> None:
        self._client.close()
