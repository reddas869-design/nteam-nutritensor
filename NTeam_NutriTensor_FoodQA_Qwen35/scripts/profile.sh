#!/usr/bin/env bash
# Profiles only explicitly selected workloads. Never changes drivers or permissions.
set -euo pipefail
task_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$task_root"
mkdir -p reports
profile_mode="${1:-help}"
case "$profile_mode" in
  inference)
    command -v nsys >/dev/null || { echo "nsys is unavailable in this environment" >&2; exit 1; }
    nsys profile --trace=cuda,nvtx,osrt --sample=none \
      --output=reports/inference \
      python scripts/benchmark.py --runs 3 --warmups 1 --tokens 128 --output reports/profiled-inference.json
    ;;
  kernel)
    command -v ncu >/dev/null || { echo "ncu is unavailable in this environment" >&2; exit 1; }
    test -x cuda/build/normalize_benchmark || { echo "Build the CUDA exercise first; see docs/BENCHMARKING.md" >&2; exit 1; }
    ncu --set basic --launch-skip 5 --launch-count 1 --export reports/normalize \
      cuda/build/normalize_benchmark --kernel pixel --iterations 10
    ;;
  *)
    echo "Usage: bash scripts/profile.sh inference|kernel"
    echo "Profiling is optional. GPU counter access may require your administrator's configuration."
    exit 2
    ;;
esac
