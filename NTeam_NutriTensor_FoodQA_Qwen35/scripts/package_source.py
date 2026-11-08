#!/usr/bin/env python3
"""Package a portable, secret-free source distribution with per-file SHA-256 hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = {"backend", "frontend", "scripts", "cuda", "deploy", "docs", ".github"}
ROOT_FILES = {
    "README.md", "START_HERE_BN.md", "LICENSE", "THIRD_PARTY_NOTICES.md",
    "package.json", "package-lock.json", "tsconfig.json", "vite.config.ts",
    "Dockerfile", "compose.yaml", ".dockerignore", ".editorconfig", ".gitignore",
    ".env.example", ".env.demo.example",
}
EXCLUDED = {
    "node_modules", ".venv", ".git", ".openai", ".sites-runtime", "dist",
    "data", "models", "reports", "backups", "__pycache__", ".pytest_cache",
    "build", "build-cpu",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo", ".so", ".pt", ".bin", ".safetensors", ".gguf", ".db", ".sqlite3", ".zip", ".tar", ".gz"}


def source_files():
    for path in sorted(ROOT.rglob("*")):
        relative = path.relative_to(ROOT)
        if not path.is_file() or path.is_symlink():
            continue
        if relative.parts[0] not in DIRECTORIES and str(relative) not in ROOT_FILES:
            continue
        if any(part in EXCLUDED or part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix in FORBIDDEN_SUFFIXES or (path.name.startswith(".env") and str(relative) not in ROOT_FILES):
            continue
        if path.stat().st_size > 25 * 1024 * 1024:
            raise ValueError(f"Unexpectedly large source file: {relative}")
        yield path, relative


def add_bytes(archive: zipfile.ZipFile, name: str, content: bytes, executable: bool = False):
    item = zipfile.ZipInfo("nteam-nutritensor/" + name, date_time=(2026, 10, 18, 0, 0, 0))
    item.compress_type = zipfile.ZIP_DEFLATED
    item.external_attr = (0o100755 if executable else 0o100644) << 16
    archive.writestr(item, content, compresslevel=9)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--attach-to-build", action="store_true", help="Copy source ZIP into the built app's download folder")
    args = parser.parse_args()
    if args.attach_to_build and not (ROOT / "dist/index.html").is_file():
        raise SystemExit("Build the frontend before attaching a download")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest = []
    with zipfile.ZipFile(args.output, "w") as archive:
        for path, relative in source_files():
            content = path.read_bytes()
            name = relative.as_posix()
            manifest.append(f"{hashlib.sha256(content).hexdigest()}  {name}")
            add_bytes(archive, name, content, path.suffix == ".sh")
        add_bytes(archive, "MANIFEST.sha256", ("\n".join(manifest) + "\n").encode())
    with zipfile.ZipFile(args.output) as archive:
        invalid = archive.testzip()
        if invalid:
            raise SystemExit(f"Archive integrity check failed: {invalid}")
    if args.attach_to_build:
        destination = ROOT / "dist/downloads/nteam-nutritensor.zip"
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.resolve() != args.output.resolve():
            shutil.copy2(args.output, destination)
    print(json.dumps({
        "archive": str(args.output.resolve()),
        "source_files": len(manifest),
        "bytes": args.output.stat().st_size,
        "sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "excluded": "Secrets, user data, model weights, dependencies, build output and original hosting identity",
    }, indent=2))


if __name__ == "__main__":
    main()
