#!/usr/bin/env python3
"""Run the API and Vite development server; terminate both cleanly on Ctrl+C."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    environment = os.environ.copy()
    if args.demo:
        environment.update(NTEAM_MODE="demo", NTEAM_MODEL_BACKEND="demo", NTEAM_DATABASE_PATH="data/demo.sqlite3")
    processes = []
    try:
        processes.append(subprocess.Popen([
            sys.executable, "-m", "uvicorn", "nutritensor.main:create_app", "--factory",
            "--host", "127.0.0.1", "--port", "8000", "--workers", "1", "--no-access-log",
        ], cwd=ROOT, env=environment))
        processes.append(subprocess.Popen(["npm", "run", "dev"], cwd=ROOT, env=environment))
        print("Development UI: http://localhost:4173")
        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        failed = [process.returncode for process in processes if process.returncode]
        if failed:
            raise SystemExit(f"A development process exited with status {failed[0]}")
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        for process in processes:
            try:
                process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=10)


if __name__ == "__main__":
    main()
