#!/usr/bin/env python3
"""E3: report whether every must-include general clears the auto pipeline's roster bar.

    python scripts/report_must_include.py [--min-battles N]

Reads `data/must_include.csv` (the 19 gold-set generals plus Han Xin, each mapped to a canonical
Wikipedia title) and runs the same parsing `scripts/build_roster_selection.py` does -- C2/C3
extraction over every cached battle page (`data/raw/battle_wikitext_cache.json`), canonicalized
through E1/E2's identity resolver -- to count each must-include general's battle appearances and
classify why they are or are not in the roster `--min-battles` would select. Read-only: does not
crawl new pages or write `data/auto/generals.csv` (that stays C4b/G2's job); a battle_universe
title missing from the wikitext cache is just counted as uncrawled, not fetched.

E4 has not dropped the seed-list requirement yet, so `select_roster` still only keeps a non-seed
general if they clear the bar *and* face an already-kept general. This script reports seed
membership alongside the roster verdict so that distinction (seed bar vs. the E4 change still to
come) is visible rather than papered over.
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.commanders import general_id_from_title  # noqa: E402
from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.roster import (  # noqa: E402
    battle_appearances,
    seed_general_ids,
    select_roster,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
SEED_ROSTER_PATH = REPO_ROOT / "data" / "raw" / "general_seed_roster.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"

DEFAULT_MIN_BATTLES = 2


@dataclass(frozen=True)
class MustIncludeStatus:
    general_id: str
    canonical_title: str
    pipeline_general_id: str
    is_seed: bool
    total_appearances: int
    usable_appearances: int
    in_roster: bool
    reason: str


def pipeline_general_id_for(canonical_title: str, resolver: dict[str, str | None]) -> str:
    """The `general_id` the pipeline would assign to a person identified by their canonical
    Wikipedia title: the resolver's answer if that exact title was itself seen as a commander
    wikilink (and so is a resolver key), else the same raw-slug fallback every other pipeline
    caller uses for a title outside E1's scan."""
    resolved = resolver.get(canonical_title)
    return resolved if resolved is not None else general_id_from_title(canonical_title)


def classify(
    general_id: str,
    canonical_title: str,
    pipeline_general_id: str,
    is_seed: bool,
    appearances_by_general: dict[str, list],
    roster: dict[str, list],
    min_battles: int,
) -> MustIncludeStatus:
    appearances = appearances_by_general.get(pipeline_general_id, [])
    usable = sum(1 for a in appearances if a.has_usable_strength)
    in_roster = pipeline_general_id in roster

    if in_roster:
        reason = "in roster" + (" (seed)" if is_seed else " (opponent-joined)")
    elif not appearances:
        reason = "not a primary commander in any parsed battle page"
    elif usable < min_battles:
        reason = f"too few usable-strength battles ({usable} usable of {len(appearances)} total, need {min_battles})"
    elif not is_seed:
        reason = (
            f"clears the usable-battle bar ({usable} usable) but is not seed-listed and never "
            "faces an already-kept general (E4 is expected to drop this seed requirement)"
        )
    else:
        reason = "unresolved: clears the bar and is seed-listed but was not kept (investigate)"

    return MustIncludeStatus(
        general_id=general_id,
        canonical_title=canonical_title,
        pipeline_general_id=pipeline_general_id,
        is_seed=is_seed,
        total_appearances=len(appearances),
        usable_appearances=usable,
        in_roster=in_roster,
        reason=reason,
    )


def _read_must_include(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-battles", type=int, default=DEFAULT_MIN_BATTLES)
    args = parser.parse_args()

    must_include_rows = _read_must_include(MUST_INCLUDE_PATH)
    battle_titles = _read_column(BATTLE_UNIVERSE_PATH, "battle_title")
    seed_titles = _read_column(SEED_ROSTER_PATH, "general_title")
    wikitext_cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))
    identity_resolver = build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))

    pages_found = sum(1 for title in battle_titles if title in wikitext_cache)
    print(f"{pages_found}/{len(battle_titles)} battle pages found in wikitext cache (read-only, no crawl)")

    appearances = []
    for title in battle_titles:
        wikitext = wikitext_cache.get(title)
        if wikitext:
            appearances.extend(battle_appearances(title, wikitext, identity_resolver))

    appearances_by_general: dict[str, list] = {}
    for appearance in appearances:
        appearances_by_general.setdefault(appearance.general_id, []).append(appearance)

    seed_ids = seed_general_ids(seed_titles, identity_resolver)
    roster = select_roster(appearances, seed_ids, args.min_battles)

    statuses = []
    for row in must_include_rows:
        general_id = row["general_id"]
        canonical_title = row["canonical_title"]
        pipeline_general_id = pipeline_general_id_for(canonical_title, identity_resolver)
        statuses.append(
            classify(
                general_id,
                canonical_title,
                pipeline_general_id,
                pipeline_general_id in seed_ids,
                appearances_by_general,
                roster,
                args.min_battles,
            )
        )

    kept = sum(1 for s in statuses if s.in_roster)
    print(f"\nmin_battles={args.min_battles}: {kept}/{len(statuses)} must-include generals in roster\n")
    for s in statuses:
        print(
            f"{s.general_id:25s} ({s.canonical_title}) -> general_id={s.pipeline_general_id} "
            f"seed={s.is_seed} appearances={s.total_appearances} usable={s.usable_appearances} "
            f"in_roster={s.in_roster}: {s.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
