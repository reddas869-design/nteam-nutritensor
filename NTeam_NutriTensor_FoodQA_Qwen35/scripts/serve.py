#!/usr/bin/env python3
"""Serve the built React app and API from one origin with one GPU worker."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--access-log", action="store_true", help="Log per-request HTTP status for diagnostics")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.chdir(ROOT)
    if not (ROOT / "dist" / "index.html").is_file():
        raise SystemExit("Frontend build is missing. Run: npm ci && npm run build")
    if args.demo:
        os.environ["NTEAM_MODE"] = "demo"
        os.environ["NTEAM_MODEL_BACKEND"] = "demo"
        os.environ["NTEAM_DATABASE_PATH"] = "data/demo.sqlite3"
    if not os.getenv("NTEAM_ALLOWED_ORIGINS"):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    os.environ.setdefault("NTEAM_ALLOWED_ORIGINS", f"http://localhost:{args.port},http://127.0.0.1:{args.port}")
    from fastapi.staticfiles import StaticFiles
    from nutritensor.main import create_app
    import uvicorn
    app = create_app()
    app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
    print(f"Open http://localhost:{args.port}")
    print("The application uses one process so a model is not duplicated across workers.")
    uvicorn.run(app, host=args.host, port=args.port, workers=1, access_log=args.access_log, timeout_graceful_shutdown=180)


if __name__ == "__main__":
    main()
