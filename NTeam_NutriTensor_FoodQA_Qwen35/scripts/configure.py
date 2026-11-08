#!/usr/bin/env python3
"""Create a private local configuration without downloading or replacing models."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import secrets
from pathlib import Path

from dotenv import set_key

from nutritensor.core.security import hash_password


ROOT = Path(__file__).resolve().parents[1]


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, help="Existing Transformers model directory")
    parser.add_argument("--endpoint", help="Existing local OpenAI-compatible endpoint, e.g. http://127.0.0.1:8080/v1")
    parser.add_argument("--endpoint-model", default="local-qwen")
    parser.add_argument("--demo", action="store_true", help="Run without a GPU model or verified catalog")
    parser.add_argument("--vision", action="store_true", help="Declare vision support for an existing compatible endpoint")
    parser.add_argument("--https", action="store_true", help="Enable secure cookies for HTTPS deployment")
    parser.add_argument("--origin", default="http://localhost:8000", help="Public origin for the local app")
    parser.add_argument("--force", action="store_true", help="Replace .env after explicitly choosing to do so")
    return parser.parse_args()


def main() -> None:
    args = arguments()
    destination = ROOT / ".env"
    if destination.exists() and not args.force:
        raise SystemExit(".env already exists. Edit it or use --force to replace it.")
    if args.model_path and args.endpoint:
        raise SystemExit("Choose one model directory or one endpoint.")
    if not args.demo and not (args.model_path or args.endpoint):
        raise SystemExit("Pass --model-path /your/model, --endpoint URL, or --demo.")
    if args.model_path:
        path = args.model_path.expanduser().resolve()
        if not (path / "config.json").is_file():
            raise SystemExit("Expected a Transformers directory containing config.json. For GGUF, use a local llama.cpp server and --endpoint.")
        config = json.loads((path / "config.json").read_text())
        print(f"Checkpoint architecture: {config.get('model_type', 'unknown')}")
        if config.get("model_type") == "qwen3":
            print("Photo recognition requires ntemma")
    password_hash = ""
    if not args.demo:
        password = getpass.getpass("Choose a local workspace password (12+ characters): ")
        confirmation = getpass.getpass("Repeat password: ")
        if password != confirmation or len(password) < 12:
            raise SystemExit("Passwords must match and contain at least 12 characters.")
        password_hash = hash_password(password)
        del password, confirmation
    from urllib.parse import urlparse
    origin = urlparse(args.origin)
    if origin.scheme not in {"http", "https"} or not origin.hostname:
        raise SystemExit("--origin must be an HTTP(S) origin.")
    if origin.path not in {"", "/"} or origin.query or origin.fragment or origin.username:
        raise SystemExit("Use an origin only, without a path, credentials or query.")
    values = {
        "NTEAM_MODE": "demo" if args.demo else "live",
        "NTEAM_MODEL_BACKEND": "demo" if args.demo else "openai-compatible" if args.endpoint else "transformers",
        "NTEAM_MODEL_PATH": str(args.model_path.expanduser().resolve()) if args.model_path else "",
        "NTEAM_LOCAL_FILES_ONLY": "true",
        "NTEAM_QUANTIZATION": "nf4",
        "NTEAM_DTYPE": "float16",
        "NTEAM_ATTENTION": "sdpa",
        "NTEAM_CONTEXT_TOKENS": "4096",
        "NTEAM_MAX_NEW_TOKENS": "384",
        "NTEAM_GPU_MEMORY_GIB": "9",
        "NTEAM_QUEUE_CAPACITY": "4",
        "NTEAM_THINKING": "false",
        "NTEAM_FAST_SCAN": "true",
        "NTEAM_USERS_PATH": "data/users.json",
        "NTEAM_DATABASE_PATH": "data/demo.sqlite3" if args.demo else "data/nutritensor.sqlite3",
        "NTEAM_CATALOG_PATH": "data/foods.json",
        "NTEAM_SESSION_SECRET": secrets.token_urlsafe(48),
        "NTEAM_ADMIN_PASSWORD_HASH": password_hash,
        "NTEAM_COOKIE_SECURE": str(args.https or origin.scheme == "https").lower(),
        "NTEAM_ALLOWED_ORIGINS": ",".join(dict.fromkeys([
            args.origin.rstrip("/"), "http://localhost:4173", "http://127.0.0.1:4173",
            "http://localhost:8000", "http://127.0.0.1:8000",
        ])),
        "NTEAM_ALLOWED_HOSTS": ",".join(dict.fromkeys([origin.hostname, "localhost", "127.0.0.1"])),
        "NTEAM_ENVIRONMENT": "development",
        "NTEAM_REMOTE_LLM_URL": args.endpoint or "http://127.0.0.1:8080/v1",
        "NTEAM_REMOTE_LLM_MODEL": args.endpoint_model,
        "NTEAM_REMOTE_SUPPORTS_VISION": str(args.vision).lower(),
        "NTEAM_ENABLE_OCR": "false",
    }
    temporary = destination.with_suffix(".env.tmp")
    temporary.touch(mode=0o600, exist_ok=False)
    try:
        for key, value in values.items():
            set_key(temporary, key, value, quote_mode="always")
        temporary.chmod(0o600)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    print("Configuration written to .env with private file permissions.")
    print("No model weights, drivers or existing PyTorch packages were changed.")
    if not args.demo:
        from backend.nutritensor.nutrition.starter import install_starter
        catalog_path = ROOT / "data/foods.json"
        if not catalog_path.exists():
            install_starter(catalog_path)
            print("Installed eight raw-fruit USDA records for offline nutrition.")
        print("Next: provision accounts with scripts/manage_users.py and run scripts/doctor.py.")


if __name__ == "__main__":
    main()
