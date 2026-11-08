#!/usr/bin/env python3
"""Audit authored source lines; exclude dependencies, builds, lockfiles, data and documentation."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {".py", ".ts", ".tsx", ".css", ".cu", ".cpp", ".h", ".hpp", ".sh", ".mjs"}
EXCLUDED = {"node_modules", ".venv", ".git", "dist", ".sites-runtime", "__pycache__", "data", "models", "reports", ".pytest_cache", "build", "build-cpu", "backups"}


def count():
    records = []
    by_language = defaultdict(lambda: {"files": 0, "physical_lines": 0, "nonempty_lines": 0})
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.suffix not in SUFFIXES or any(part in EXCLUDED for part in path.relative_to(ROOT).parts):
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        record = {
            "path": str(path.relative_to(ROOT)),
            "physical_lines": len(lines),
            "nonempty_lines": sum(bool(line.strip()) for line in lines),
        }
        records.append(record)
        group = by_language[path.suffix]
        group["files"] += 1
        group["physical_lines"] += record["physical_lines"]
        group["nonempty_lines"] += record["nonempty_lines"]
    return {
        "scope": "Authored application, styling, tests and tooling; comments count, blank lines separately reported.",
        "excluded": "Third-party dependencies, build output, lockfiles, JSON fixtures, docs, generated API schema, model weights.",
        "file_count": len(records),
        "physical_lines": sum(record["physical_lines"] for record in records),
        "nonempty_lines": sum(record["nonempty_lines"] for record in records),
        "by_extension": dict(by_language),
        "files": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--minimum", type=int, default=10000)
    args = parser.parse_args()
    report = count()
    print(json.dumps({key: value for key, value in report.items() if key != "files"}, indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    if report["nonempty_lines"] < args.minimum:
        raise SystemExit(f"Nonempty authored source lines are below {args.minimum}")


if __name__ == "__main__":
    main()
