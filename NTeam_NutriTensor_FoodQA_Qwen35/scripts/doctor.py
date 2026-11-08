#!/usr/bin/env python3
"""Read-only diagnostics. Does not install packages or alter GPU drivers."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path


PACKAGES = ["fastapi", "pydantic", "torch", "transformers", "accelerate", "bitsandbytes", "Pillow", "uvicorn"]


def check_command(name: str, args: list[str]) -> dict:
    executable = shutil.which(name)
    if not executable:
        return {"available": False}
    try:
        result = subprocess.run([executable, *args], text=True, capture_output=True, timeout=15, check=False)
        return {"available": True, "exit_code": result.returncode, "output": result.stdout.strip()[:3000]}
    except subprocess.TimeoutExpired:
        return {"available": True, "error": "diagnostic timed out"}


def collect() -> dict:
    result = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {},
        "node": check_command("node", ["--version"]),
        "nvcc": check_command("nvcc", ["--version"]),
        "nvidia_smi": check_command("nvidia-smi", ["--query-gpu=name,driver_version,memory.total,memory.free", "--format=csv,noheader"]),
        "cuda": {"available": False},
    }
    for package in PACKAGES:
        try:
            result["packages"][package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result["packages"][package] = None
    try:
        import torch
        result["cuda"] = {
            "available": torch.cuda.is_available(),
            "torch_cuda_runtime": torch.version.cuda,
            "device_count": torch.cuda.device_count(),
        }
        if torch.cuda.is_available():
            device = torch.cuda.get_device_properties(0)
            result["cuda"].update(
                device=device.name,
                compute_capability=f"{device.major}.{device.minor}",
                total_memory_gib=round(device.total_memory / 1024**3, 2),
                bf16_supported=torch.cuda.is_bf16_supported(),
            )
            a = torch.arange(16, dtype=torch.float32, device="cuda").reshape(4, 4)
            b = a @ a.T
            torch.cuda.synchronize()
            result["cuda"]["matmul_smoke_test"] = bool(torch.isfinite(b).all().item())
            del a, b
    except ImportError:
        result["cuda"]["note"] = "PyTorch is not installed in this interpreter"
    except Exception as exc:
        result["cuda"]["error_type"] = type(exc).__name__
    result["notes"] = [
        "nvcc toolkit and torch.version.cuda describe different components and may differ.",
        "No performance or model-fit claim is made by this diagnostic.",
        "Run smoke_model.py to validate the configured checkpoint and quantization.",
    ]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--require-cuda", action="store_true")
    args = parser.parse_args()
    result = collect()
    encoded = json.dumps(result, indent=2)
    print(encoded)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n")
    if args.require_cuda and not result["cuda"].get("matmul_smoke_test"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
