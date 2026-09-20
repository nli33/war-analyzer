#!/usr/bin/env python3
"""CLI entry point: `python scripts/validate_data.py` checks data/*.csv against war/schema.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.validate import validate_all  # noqa: E402


def main() -> int:
    errors = validate_all()
    if errors:
        for error in errors:
            print(error)
        print(f"\n{len(errors)} error(s)")
        return 1
    print("data/battles.csv and data/generals.csv are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
