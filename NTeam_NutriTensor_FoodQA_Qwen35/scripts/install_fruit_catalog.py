#!/usr/bin/env python3
"""Install eight verified raw-fruit source records. No API key or model download."""

import argparse
from pathlib import Path
from nutritensor.nutrition.starter import install_starter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("data/foods.json"))
    parser.add_argument("--merge", action="store_true", help="Preserve current records and add missing starter fruit IDs")
    args = parser.parse_args()
    try:
        count = install_starter(args.output, args.merge)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Installed catalog with {count} records: {args.output}")
    print("Restart the app to load catalog changes. Confirm raw preparation and edible weight.")


if __name__ == "__main__":
    main()
