# Measuring your RTX 3060

The application ships conservative configuration and measurement tools, not invented hardware results. Run these commands on the workstation that actually has your model and GPU. Stop other inference processes before measuring; do not run the API model and standalone benchmark simultaneously on the same device.

## Establish correctness first

```bash
python scripts/doctor.py --require-cuda --output reports/environment.json
python scripts/smoke_model.py
```

For a supported vision checkpoint, also run `python scripts/smoke_model.py --image /path/to/a/test-meal.jpg`. Use a small image and verify that the final answer describes visible food without making up nutrient measurements. Text-only checkpoints must reject this image request. The diagnostic records actual library versions, device identity, compute capability, and a small CUDA matrix operation when available.

Validate several manually selected food calculations against source records. For photo evaluation, collect consented test images with independently known food identity and weighed portions. Separate food recognition accuracy from portion error and from source matching accuracy. An end-to-end plausible calorie number does not establish any of those measures.

## Baseline inference measurement

```bash
python scripts/benchmark.py --runs 12 --warmups 2 --tokens 128 --output reports/nf4-baseline.json
```

This version benchmarks a fixed set of text questions with thinking disabled. It reports:

- Cold model load plus the first request separately.
- Wall latency for each measured warm request and p50/p95/mean.
- Actual prompt and completion token counts from the provider.
- Model-call duration including prompt processing, not decode-only duration.
- Peak PyTorch allocated GPU memory for in-process Transformers generation.
- Checkpoint label, configured context/output budgets, quantization and attention backend.

`tokens_per_second` is completion tokens divided by the measured model-call duration, which includes prefill. There is no time-to-first-token metric because the provider returns a final completion. PyTorch peak allocated memory excludes some non-PyTorch allocations and is not equivalent to the whole process's `nvidia-smi` memory. Remote endpoints report only what their response supplies; the adapter cannot measure remote GPU memory.

The first load occurs outside the provider's generation timeout. A local compatible server controls its own model-loading/context policy. Benchmark hardware identity and cache state separately for such a server. Never compare browser demo timing to model throughput.

## Change one variable

Keep checkpoint, prompts, output budget, system load and warmup count the same. Start by comparing a smaller context or different quantization only if it fits. A 4B fp16 model plus KV cache, image encoder, and runtime overhead can approach or exceed practical VRAM headroom. Do not assume an unquantized checkpoint fits because parameters alone appear to fit.

```bash
NTEAM_CONTEXT_TOKENS=2048 python scripts/benchmark.py --runs 12 --warmups 2 --tokens 128 --output reports/context-2048.json
python scripts/compare_benchmarks.py reports/nf4-baseline.json reports/context-2048.json
```

Environment variables override `.env`. The comparison tool refuses different checkpoint labels/output budgets and shows output token counts; different completion lengths can still affect measured latency. Use enough repeated runs for your decision. Small samples are diagnostic evidence, not a general benchmark claim.

Evaluate answer quality as well as speed. Quantization, shorter context, constrained output, greedy decoding, and a different attention implementation can change answers. NF4 is the default primarily to reduce memory; it is not asserted to be the fastest method for batch size one. FlashAttention is optional and not needed for the default SDPA path. Do not add `torch.compile`, CUDA graphs, or custom kernels without measuring the actual workload and failure modes.

## PyTorch and Nsight

```bash
python scripts/benchmark.py --runs 6 --warmups 2 --tokens 128 --torch-trace reports/torch-trace.json
bash scripts/profile.sh inference
```

The PyTorch trace is recorded in a separate request after latency samples. Nsight Systems records CUDA/CPU scheduling but adds overhead; keep its result separate from an uninstrumented baseline. Look for model reloads, CPU preprocessing stalls, repeated transfers, small kernel launch overhead, synchronization, and allocator churn before choosing an optimization.

The profiling scripts neither install Nsight nor alter system permissions. GPU performance-counter access may require administrator configuration; the script does not bypass a restriction. Review trace files before sharing, because profiling tools can capture paths, shapes, process details, and other workstation context.

## Optional C++/CUDA exercise

This is a standalone HWC uint8 RGB → normalized CHW float benchmark. It compares two kernel mappings against a CPU reference, uses pinned buffers, a dedicated CUDA stream, warmups and CUDA events, and reports kernel-only versus transfer-inclusive GPU time. The normalization constants are generic lab constants and are **not** asserted to be Qwen's image processor configuration. The app does not call these kernels.

```bash
cmake -S cuda -B cuda/build -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_ARCHITECTURES=86
cmake --build cuda/build -j
ctest --test-dir cuda/build --output-on-failure
cuda/build/normalize_benchmark --kernel scalar --width 1280 --height 720 --block 256 --iterations 100
cuda/build/normalize_benchmark --kernel pixel --width 1280 --height 720 --block 256 --iterations 100
bash scripts/profile.sh kernel
```

The default architecture is sm_86 for RTX 3060. A separate CPU-only reference build works without nvcc:

```bash
cmake -S cuda -B cuda/build-cpu -DNTEAM_WITH_CUDA=OFF
cmake --build cuda/build-cpu
ctest --test-dir cuda/build-cpu --output-on-failure
```

`effective_kernel_gb_s` counts expected input/output bytes divided by kernel duration; it is not a measured DRAM traffic counter. The CPU timing is one reference pass and is not a carefully tuned CPU performance baseline. The benchmark checks maximum absolute error before reporting results. A faster isolated normalization kernel does not prove faster end-to-end vision inference, and cannot replace model-specific resizing, tiling, normalization, and tokenization without a correctness study.

## Acceptance observations to record

Record model directory/version, model format, exact torch/Transformers/bitsandbytes versions, driver, GPU power/temperature, free VRAM before load, context/output/image sizes, quantization, attention, warmups, completion tokens, p50/p95 latency, errors, and whether concurrent cancellation preserves one active model call. Re-run numerical/source and model-output checks after each optimization.
