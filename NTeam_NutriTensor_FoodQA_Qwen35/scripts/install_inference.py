#!/usr/bin/env python3
"""Install optional inference packages while constraining existing PyTorch packages."""

from __future__ import annotations

import argparse
import importlib.metadata
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Ask pip to resolve without installing")
    args = parser.parse_args()
    try:
        import torch
    except ImportError:
        raise SystemExit("PyTorch is missing. Activate your existing working CUDA environment first.")
    if not torch.cuda.is_available():
        raise SystemExit("PyTorch cannot access CUDA. Run scripts/doctor.py; this installer does not replace drivers or torch.")
    constraints = []
    for name in ("torch", "torchvision", "torchaudio"):
        try:
            constraints.append(f"{name}=={importlib.metadata.version(name)}")
        except importlib.metadata.PackageNotFoundError:
            pass
    print("Preserving installed packages: " + ", ".join(constraints))
    with tempfile.TemporaryDirectory(prefix="nteam-inference-") as directory:
        path = Path(directory) / "preserve-torch.txt"
        path.write_text("\n".join(constraints) + "\n")
        command = [
            sys.executable, "-m", "pip", "install",
            "--upgrade-strategy", "only-if-needed", "-c", str(path),
            "-c", str(ROOT / "backend" / "requirements-tested.txt"),
        ]
        if args.dry_run:
            command.append("--dry-run")
        command.append(str(ROOT / "backend") + "[inference]")
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            raise SystemExit("Inference installation did not complete. Resolve the reported compatibility conflict in a separate environment; existing torch versions were constrained.")


if __name__ == "__main__":
    main()
