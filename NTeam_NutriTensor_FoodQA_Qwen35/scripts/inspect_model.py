#!/usr/bin/env python3
"""Inspect a downloaded checkpoint without loading weights or accessing the network."""

import argparse
import json
from pathlib import Path

from nutritensor.inference.transformers import VISION_TYPES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", type=Path, help="Directory containing config.json")
    args = parser.parse_args()
    config_path = args.model.expanduser().resolve() / "config.json"
    try:
        config = json.loads(config_path.read_text())
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Cannot read model config: {exc}") from exc
    architecture = config.get("model_type", "unknown")
    vision = architecture in VISION_TYPES and (architecture not in {"gemma3", "qwen3_5"} or config.get("vision_config") is not None)
    print(json.dumps({"directory": str(config_path.parent), "model_type": architecture,
                      "architectures": config.get("architectures", []), "vision_supported_by_app": vision,
                      "note": "ntemma is multimodal (image + text). does not guarantee food accuracy."}, indent=2))
    if not vision:
        print("Image recognition needs a supported vision checkpoint.")


if __name__ == "__main__":
    main()
