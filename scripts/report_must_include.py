#!/usr/bin/env python3
"""E3/E4: report whether every must-include general clears the auto pipeline's roster bar.

    python scripts/report_must_include.py [--min-battles N]

Reads `data/must_include.csv` (the 19 gold-set generals plus Han Xin, each mapped to a canonical
Wikipedia title) and runs the same parsing `scripts/build_roster_selection.py` does -- C2/C3
extraction over every cached battle page (`data/raw/battle_wikitext_cache.json`), canonicalized
through E1/E2's identity resolver -- to count each must-include general's battle appearances and
classify why they are or are not in the roster `--min-battles` would select. Read-only: does not
crawl new pages or write `data/auto/generals.csv` (that stays build_roster_selection.py's job); a
battle_universe title missing from the wikitext cache is just counted as uncrawled, not fetched.

E4 dropped the seed-list gate and made every must-include general join the roster regardless of
`--min-battles` (falling back to hand-curated data when thin -- see
`scripts/build_roster_selection.py`'s module docstring). This script reports seed membership
alongside the roster verdict purely for visibility, not because it still gates anything.
"""

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.roster import (  # noqa: E402
    battle_appearances,
    pipeline_general_id_for,
    seed_general_ids,
    select_roster,
    usable_battle_counts,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
SEED_ROSTER_PATH = REPO_ROOT / "data" / "raw" / "general_seed_roster.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
HAN_XIN_GENERAL_ID = "han-xin"

DEFAULT_MIN_BATTLES = 4


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

    if usable >= min_battles:
        reason = "in roster" + (" (seed)" if is_seed else " (non-seed, clears the bar directly)")
    elif general_id == HAN_XIN_GENERAL_ID:
        reason = (
            f"thin ({usable} usable of {len(appearances)} total, need {min_battles}); "
            "forced in via must-include, no hand-curated fallback exists for Han Xin"
        )
    else:
        reason = (
            f"thin ({usable} usable of {len(appearances)} total, need {min_battles}); "
            "falls back to the hand-curated data/generals.csv row (build_roster_selection.py)"
        )

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
    must_include_pipeline_ids = frozenset(
        pipeline_general_id_for(row["canonical_title"], identity_resolver) for row in must_include_rows
    )
    roster = select_roster(appearances, args.min_battles, must_include_ids=must_include_pipeline_ids)

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

    kept = sum(1 for s in statuses if s.usable_appearances >= args.min_battles)
    thin = len(statuses) - kept
    print(
        f"\nmin_battles={args.min_battles}: {kept}/{len(statuses)} must-include generals clear the "
        f"bar directly, {thin} are thin and need the E4 fallback path\n"
    )
    for s in statuses:
        print(
            f"{s.general_id:25s} ({s.canonical_title}) -> general_id={s.pipeline_general_id} "
            f"seed={s.is_seed} appearances={s.total_appearances} usable={s.usable_appearances}: {s.reason}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
