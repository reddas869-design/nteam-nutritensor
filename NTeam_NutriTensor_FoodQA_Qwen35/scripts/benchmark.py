#!/usr/bin/env python3
"""Measure the actual configured runtime; cold load is separated from warm requests."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from nutritensor.core.config import Settings
from nutritensor.inference.contracts import GenerationRequest
from nutritensor.inference.factory import create_provider


PROMPTS = [
    "Explain why 100 g of dry rice and 100 g of cooked rice are different portions.",
    "List three sources of uncertainty in estimating a mixed dish from a photo.",
    "Explain the arithmetic: 130 kcal per 100 g, portion 150 g. Keep it brief.",
]


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=6)
    parser.add_argument("--warmups", type=int, default=2)
    parser.add_argument("--tokens", type=int, default=128)
    parser.add_argument("--output", type=Path, default=Path("reports/inference-benchmark.json"))
    parser.add_argument("--torch-trace", type=Path)
    args = parser.parse_args()
    if not 1 <= args.runs <= 100 or not 1 <= args.warmups <= 10 or not 16 <= args.tokens <= 2048:
        parser.error("Use runs 1–100, warmups 1–10 and tokens 16–2048")
    settings = Settings.from_env()
    if settings.is_demo:
        raise SystemExit("Demo mode is not a performance benchmark. Configure the local model first.")
    settings = replace(settings, max_new_tokens=args.tokens).validate()
    provider = create_provider(settings)
    observations = []
    cold_start = None
    try:
        for index in range(args.warmups + args.runs):
            request = GenerationRequest(
                system="Answer the food-information question concisely, without internal reasoning.",
                prompt=PROMPTS[index % len(PROMPTS)], max_new_tokens=args.tokens,
            )
            started = time.perf_counter()
            result = provider.generate(request)
            wall_ms = (time.perf_counter() - started) * 1000
            if index == 0:
                cold_start = wall_ms
            if index >= args.warmups:
                observations.append({"wall_ms": wall_ms, **result.stats.model_dump()})
            print(f"{'warmup' if index < args.warmups else 'measured'} {index + 1}: {wall_ms:.1f} ms")
        if args.torch_trace:
            if settings.model_backend != "transformers":
                raise SystemExit("--torch-trace requires the in-process Transformers backend")
            import torch
            args.torch_trace.parent.mkdir(parents=True, exist_ok=True)
            with torch.profiler.profile(
                activities=[torch.profiler.ProfilerActivity.CPU, torch.profiler.ProfilerActivity.CUDA],
                record_shapes=True, profile_memory=True,
            ) as profiler:
                provider.generate(GenerationRequest(system="Be concise.", prompt=PROMPTS[0], max_new_tokens=args.tokens))
            profiler.export_chrome_trace(str(args.torch_trace))
        times = [row["wall_ms"] for row in observations]
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hardware": provider.capabilities().model_dump(),
            "settings": {
                "quantization": settings.quantization,
                "context_tokens": settings.context_tokens,
                "max_new_tokens": args.tokens,
                "attention": settings.attention,
                "thinking": False,
            },
            "warmups": args.warmups,
            "runs": args.runs,
            "cold_load_and_first_request_ms": cold_start,
            "latency_ms": {"p50": percentile(times, 0.5), "p95": percentile(times, 0.95), "mean": statistics.mean(times)},
            "observations": observations,
            "notes": [
                "Wall latency includes prompt preparation and generation; warm samples exclude model loading.",
                "tokens_per_second uses generated tokens divided by measured model-call duration, including prefill.",
                "No TTFT is claimed; this implementation returns final completions rather than token streams.",
                "Profiler runs are separate because instrumentation changes timing.",
            ],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"Saved measurements to {args.output}")
    finally:
        provider.close()


if __name__ == "__main__":
    main()
