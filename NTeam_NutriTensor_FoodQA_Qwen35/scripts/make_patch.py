#!/usr/bin/env python3
"""Export source changes against an exact Git revision without modifying the index."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from package_source import ROOT, source_files


def git(*arguments: str) -> bytes:
    result = subprocess.run(["git", *arguments], cwd=ROOT, capture_output=True, check=False)
    if result.returncode not in {0, 1}:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Exact base commit, not a moving branch")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    base = git("rev-parse", "--verify", args.base + "^{commit}").decode().strip()
    allowed = {str(relative) for _, relative in source_files()}
    changed = git("diff", "--name-only", "-z", base, "--").decode().split("\0")
    tracked = [path for path in changed if path and (path in allowed or not (ROOT / path).exists())]
    data = git("diff", "--no-ext-diff", "--binary", "--no-color", "--src-prefix=a/", "--dst-prefix=b/", base, "--", *tracked) if tracked else b""
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")
    for name in sorted(path for path in untracked if path in allowed):
        data += git("diff", "--no-ext-diff", "--binary", "--no-color", "--no-index", "--", "/dev/null", name)
    if not data:
        raise SystemExit("No source changes to package")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({"base": base, "patch": str(args.output.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}, indent=2))


if __name__ == "__main__":
    main()
