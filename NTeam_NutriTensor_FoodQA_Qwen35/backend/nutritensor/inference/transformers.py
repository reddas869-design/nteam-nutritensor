"""One lazy-loaded Transformers model shared by all agent roles.

GPU work is serialized through a lock. Cancellation never releases the lock
while CUDA generation is still active. This avoids overlapping cancelled jobs.
"""

from __future__ import annotations

import gc
import logging
import threading
import time
from pathlib import Path

from nutritensor.core.config import Settings
from nutritensor.core.errors import GenerationCancelled, GenerationTimeout, ModelUnavailable, VisionUnavailable
from nutritensor.domain.models import ModelCapabilities, RuntimeStats
from nutritensor.inference.contracts import GenerationRequest, GenerationResult
from nutritensor.inference.parsing import decode_final


logger = logging.getLogger("nutritensor.inference")
VISION_TYPES = {"qwen3_5", "qwen3_vl", "qwen2_5_vl", "qwen2_vl", "gemma3"}


class TransformersProvider:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._model = None
        self._processor = None
        self._tokenizer = None
        self._model_type = "unknown"
        self._vision = False
        self._thinking = False
        self._device = "not loaded"
        self._lock = threading.Lock()
        self._config_read = False

    def _inspect(self) -> None:
        if self._config_read:
            return
        path = Path(self.settings.model_path)
        config_path = path / "config.json"
        if config_path.is_file():
            import json
            try:
                config = json.loads(config_path.read_text())
                self._model_type = config.get("model_type", "unknown")
                self._vision = self._model_type in VISION_TYPES and (
                    self._model_type not in {"gemma3", "qwen3_5"} or config.get("vision_config") is not None
                )
            except (OSError, ValueError):
                pass
        self._config_read = True

    def capabilities(self) -> ModelCapabilities:
        self._inspect()
        return ModelCapabilities(
            backend="transformers", model_label=Path(self.settings.model_path).name or "Local model",
            loaded=self._model is not None, vision=self._vision, thinking=self._thinking,
            quantization=self.settings.quantization, context_tokens=self.settings.context_tokens,
            max_new_tokens=self.settings.max_new_tokens, device=self._device,
        )

    def _load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoConfig, AutoModelForCausalLM, AutoProcessor, AutoTokenizer, BitsAndBytesConfig
        except ImportError as exc:
            raise ModelUnavailable("Install PyTorch and backend[inference] in your existing CUDA environment") from exc
        if not torch.cuda.is_available():
            raise ModelUnavailable("CUDA is unavailable. Verify PyTorch CUDA before enabling the local model.")
        common = {
            "local_files_only": self.settings.local_files_only,
            "trust_remote_code": False,
        }
        try:
            config = AutoConfig.from_pretrained(self.settings.model_path, **common)
            self._model_type = config.model_type
            self._vision = self._model_type in VISION_TYPES and (
                self._model_type not in {"gemma3", "qwen3_5"} or getattr(config, "vision_config", None) is not None
            )
            dtype = getattr(torch, self.settings.dtype)
            if dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
                raise ModelUnavailable("Requested bfloat16 is not supported by this CUDA device")
            quantization = None
            if self.settings.quantization == "nf4":
                quantization = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=dtype,
                )
            elif self.settings.quantization == "int8":
                quantization = BitsAndBytesConfig(load_in_8bit=True)
            kwargs = dict(
                **common, dtype=dtype, device_map={"": 0},
                attn_implementation=self.settings.attention,
                low_cpu_mem_usage=True,
            )
            if quantization is not None:
                kwargs["quantization_config"] = quantization
            # Reserve headroom rather than silently spilling a model into CPU RAM.
            free_bytes, _ = torch.cuda.mem_get_info()
            if free_bytes < 2 * 1024**3:
                raise ModelUnavailable("Less than 2 GiB GPU memory is free; close other GPU workloads")
            torch.cuda.set_per_process_memory_fraction(
                min(0.95, self.settings.gpu_memory_gib * 1024**3 / torch.cuda.get_device_properties(0).total_memory), 0,
            )
            if self._vision:
                self._processor = AutoProcessor.from_pretrained(self.settings.model_path, **common)
                if self._model_type == "qwen3_5":
                    # ntemma3.5 is natively multimodal. Its official HF model card
                    # loads the full vision + language checkpoint via this class.
                    from transformers import AutoModelForMultimodalLM
                    self._model = AutoModelForMultimodalLM.from_pretrained(self.settings.model_path, **kwargs)
                else:
                    from transformers import AutoModelForImageTextToText
                    self._model = AutoModelForImageTextToText.from_pretrained(self.settings.model_path, **kwargs)
                self._tokenizer = self._processor.tokenizer
            else:
                self._tokenizer = AutoTokenizer.from_pretrained(self.settings.model_path, **common)
                self._model = AutoModelForCausalLM.from_pretrained(self.settings.model_path, **kwargs)
            template = str(getattr(self._tokenizer, "chat_template", ""))
            self._thinking = self._model_type == "qwen3_5" or "enable_thinking" in template
            self._model.eval()
            self._device = torch.cuda.get_device_name(0)
            self._config_read = True
        except ModelUnavailable:
            self._clear()
            raise
        except torch.cuda.OutOfMemoryError as exc:
            self._clear()
            raise ModelUnavailable("Model load exceeded GPU memory. Use NF4, close other GPU tasks, or choose a smaller checkpoint.") from exc
        except Exception as exc:
            self._clear()
            logger.exception("Model loading failed", extra={"error_code": type(exc).__name__})
            raise ModelUnavailable("Could not load the configured checkpoint. Check its path, architecture and installed inference dependencies.") from exc

    def generate(self, request: GenerationRequest) -> GenerationResult:
        with self._lock:
            if request.cancel.is_set():
                raise GenerationCancelled("Analysis cancelled")
            self._inspect()
            if request.image_path and self._model_type != "unknown" and not self._vision:
                raise VisionUnavailable("Something went wrong. Try again.")
            self._load()
            import torch
            from transformers import StoppingCriteria, StoppingCriteriaList
            if request.image_path and not self._vision:
                raise VisionUnavailable("This checkpoint is text-only. Select foods manually or configure a supported vision checkpoint.")
            generation_started = time.perf_counter()
            deadline = generation_started + self.settings.inference_timeout
            cancelled = request.cancel

            class StopOnCancelOrDeadline(StoppingCriteria):
                def __call__(self, input_ids, scores, **kwargs):
                    return cancelled.is_set() or time.perf_counter() >= deadline

            thinking = bool(request.thinking and self._thinking and self.settings.thinking)
            messages = [{"role": "system", "content": request.system}]
            if request.image_path:
                messages.append({"role": "user", "content": [
                    {"type": "image", "path": str(request.image_path.resolve())},
                    {"type": "text", "text": request.prompt},
                ]})
                encoded = self._processor.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=True,
                    return_dict=True, return_tensors="pt",
                    **({"enable_thinking": thinking} if self._thinking else {}),
                )
            else:
                messages.append({"role": "user", "content": request.prompt})
                encoded = self._tokenizer.apply_chat_template(
                    messages, tokenize=True, add_generation_prompt=True,
                    return_dict=True, return_tensors="pt",
                    **({"enable_thinking": thinking} if self._thinking else {}),
                )
            if request.image_path and not any(key in encoded for key in ("pixel_values", "pixel_values_videos", "image_grid_thw")):
                raise ModelUnavailable("The image was not encoded into visual tensors. Check the installed Transformers processor.")
            prompt_tokens = encoded["input_ids"].shape[-1]
            maximum = min(request.max_new_tokens, self.settings.max_new_tokens)
            if prompt_tokens + maximum > self.settings.context_tokens:
                raise ModelUnavailable(
                    f"Image/prompt requires {prompt_tokens} tokens; configured context is "
                    f"{self.settings.context_tokens}. Reduce NTEAM_IMAGE_MAX_EDGE or raise NTEAM_CONTEXT_TOKENS "
                    "if your GPU has adequate memory."
                )
            encoded = encoded.to(self._model.device)
            torch.cuda.reset_peak_memory_stats()
            options = {
                "max_new_tokens": maximum,
                "use_cache": True,
                "do_sample": thinking,
                "stopping_criteria": StoppingCriteriaList([StopOnCancelOrDeadline()]),
                "pad_token_id": self._tokenizer.pad_token_id or self._tokenizer.eos_token_id,
            }
            if thinking:
                options.update(temperature=0.6, top_p=0.95, top_k=20)
            try:
                with torch.inference_mode():
                    generated = self._model.generate(**encoded, **options)
                torch.cuda.synchronize()
                output_ids = generated[0, prompt_tokens:]
                output_tokens = int(output_ids.shape[0])
                text = decode_final(self._tokenizer, output_ids, thinking)
                duration = time.perf_counter() - generation_started
                peak = torch.cuda.max_memory_allocated() / (1024 * 1024)
                del generated, output_ids, encoded
                if request.cancel.is_set():
                    raise GenerationCancelled("Analysis cancelled")
                if time.perf_counter() >= deadline:
                    raise GenerationTimeout("The generation budget expired; reduce context or output length")
                return GenerationResult(
                    text=text,
                    stats=RuntimeStats(
                        model_ms=duration * 1000, prompt_tokens=prompt_tokens,
                        completion_tokens=output_tokens,
                        tokens_per_second=output_tokens / duration if duration else None,
                        gpu_peak_mb=peak, backend="transformers",
                    ),
                )
            except torch.cuda.OutOfMemoryError as exc:
                gc.collect()
                torch.cuda.empty_cache()
                raise ModelUnavailable("Inference ran out of GPU memory. Reduce context/image size or use NF4.") from exc

    def _clear(self) -> None:
        self._model = None
        self._processor = None
        self._tokenizer = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass

    def close(self) -> None:
        with self._lock:
            self._clear()
