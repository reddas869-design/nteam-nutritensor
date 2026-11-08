#!/usr/bin/env python3
"""Compare actual benchmark reports, refusing demo results or incompatible workloads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_report(path: Path) -> dict:
    payload = json.loads(path.read_text())
    if payload.get("hardware", {}).get("backend") == "demo":
        raise ValueError(f"{path.name}: demo output is not a benchmark")
    if not payload.get("observations") or payload.get("runs") != len(payload["observations"]):
        raise ValueError(f"{path.name}: missing or inconsistent measured observations")
    if payload["latency_ms"]["p50"] <= 0:
        raise ValueError(f"{path.name}: invalid latency")
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    baseline = read_report(args.baseline)
    candidate = read_report(args.candidate)
    for field in ("max_new_tokens", "thinking"):
        if baseline["settings"][field] != candidate["settings"][field]:
            raise SystemExit(f"Reports have different {field}; compare the same output workload")
    if baseline["hardware"]["model_label"] != candidate["hardware"]["model_label"]:
        raise SystemExit("Reports identify different checkpoints; these are not a runtime-only comparison")
    print("Metric                         Baseline      Candidate")
    for field in ("p50", "p95", "mean"):
        print(f"Warm {field} latency (ms)     {baseline['latency_ms'][field]:12.2f} {candidate['latency_ms'][field]:14.2f}")
    ratio = baseline["latency_ms"]["p50"] / candidate["latency_ms"]["p50"]
    print(f"Observed p50 latency ratio: {ratio:.3f}×")
    for label, payload in (("Baseline", baseline), ("Candidate", candidate)):
        tokens = [row["completion_tokens"] for row in payload["observations"]]
        print(f"{label} completion-token counts: {tokens}")
    print("Different output lengths affect latency. Evaluate answer quality and source fidelity separately.")
    print("Small local samples do not establish general hardware performance.")


if __name__ == "__main__":
    main()
