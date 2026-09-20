#!/usr/bin/env python3
"""CLI entry point: fetch a draft strength/casualties scaffold for a battle.

    python scripts/scrape_wikipedia_infobox.py "Battle of Cannae"

Prints the raw infobox fields as JSON. This is a DRAFT ONLY — per PLAN.md Section 3,
cross-check every number against an academic source (Clodfelter, Osprey, etc.) before writing
a data/battles.csv row. Never copy these numbers in as source_citation="Wikipedia" alone.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.scrape import draft_for_battle  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} '<Wikipedia page title>'", file=sys.stderr)
        return 2

    title = sys.argv[1]
    draft = draft_for_battle(title)
    if not draft.fields:
        print(
            f"No military conflict infobox found for {title!r} — research this one by hand.",
            file=sys.stderr,
        )
        return 1

    print(json.dumps(draft.to_dict(), indent=2))
    print(
        "\n^ DRAFT, UNVERIFIED. Cross-check every field against Clodfelter/Osprey/an academic "
        "source before writing a battles.csv row.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
