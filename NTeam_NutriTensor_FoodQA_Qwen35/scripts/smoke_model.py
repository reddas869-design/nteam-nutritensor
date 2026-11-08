#!/usr/bin/env python3
"""Load the configured checkpoint and perform one bounded generation."""

import argparse
import json
from pathlib import Path

from nutritensor.core.config import Settings
from nutritensor.inference.contracts import GenerationRequest
from nutritensor.inference.factory import create_provider


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path)
    args = parser.parse_args()
    settings = Settings.from_env()
    if settings.is_demo:
        raise SystemExit("Configure live mode first; this command must test an actual model.")
    provider = create_provider(settings)
    try:
        result = provider.generate(GenerationRequest(
            system="Give a concise final answer without internal reasoning.",
            prompt="Name visible foods, without estimating nutrients." if args.image else "In one sentence, explain why a food portion's weight matters.",
            image_path=args.image, max_new_tokens=96,
        ))
        print(json.dumps({
            "capabilities": provider.capabilities().model_dump(),
            "stats": result.stats.model_dump(),
            "final_answer": result.text,
        }, ensure_ascii=False, indent=2))
        if not result.text.strip():
            raise SystemExit("Model loaded but no final answer was produced. Inspect the checkpoint's chat template.")
    finally:
        provider.close()


if __name__ == "__main__":
    main()
