#!/usr/bin/env python3
"""C4b: select the automated general roster and write data/auto/generals.csv.

    python scripts/build_roster_selection.py [--min-battles N]

Fetches wikitext for every candidate battle title in C1's `data/raw/battle_universe.csv`
(cached/resumable at data/raw/battle_wikitext_cache.json, same pattern as every other crawl
script in this project), parses each page into 0-2 `war.roster.BattleAppearance`s (C2 strength
extraction + C3 commander/side extraction, combined side-aware by `war.roster.battle_appearances`),
and selects a roster: a C4a seed general is kept if they have at least `--min-battles` battles
with usable strength on both sides; a non-seed general may join if they clear the same bar and
face a kept general (see war.roster.select_roster's docstring for exactly what that does and
does not admit).

Output: data/auto/generals.csv (schema per war/schema.py GENERAL_COLUMNS). Does not touch
data/generals.csv (the hand-curated gold set, left untouched per PROGRESS.md's "Decisions
already made"). Also writes data/raw/roster_selection_report.json with the counts behind the
choice of --min-battles, so the number can be checked against PROGRESS.md's Notes entry rather
than re-run to reproduce it.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.roster import (  # noqa: E402
    battle_appearances,
    generals_csv_rows,
    seed_general_ids,
    select_roster,
)
from war.scrape import fetch_wikitext_batch  # noqa: E402
from war.schema import GENERAL_FIELD_NAMES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
SEED_ROSTER_PATH = REPO_ROOT / "data" / "raw" / "general_seed_roster.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
OUTPUT_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "roster_selection_report.json"


def _load_identity_resolver() -> dict[str, str | None] | None:
    """E2: `None` (raw-slug fallback for every title) if E1 hasn't been run yet; otherwise the
    full title -> canonical-general_id map built from `data/raw/identity_map.json`."""
    if not IDENTITY_MAP_PATH.exists():
        return None
    return build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))

DEFAULT_MIN_BATTLES = 2


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def _load_cache() -> dict[str, str]:
    if WIKITEXT_CACHE_PATH.exists():
        return json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    WIKITEXT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    WIKITEXT_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))


def crawl(titles: list[str], refresh: bool = False) -> dict[str, str]:
    """Fetch (or reuse cached) wikitext for every candidate battle title. Resumable: only
    titles missing from the cache are fetched over the network."""
    cache = {} if refresh else _load_cache()
    missing = [title for title in titles if title not in cache]
    if missing:
        fetched = fetch_wikitext_batch(missing)
        cache.update(fetched)
        _save_cache(cache)
    return cache


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--min-battles",
        type=int,
        default=DEFAULT_MIN_BATTLES,
        help=f"usable-strength battles required to keep a general (default {DEFAULT_MIN_BATTLES})",
    )
    parser.add_argument("--refresh", action="store_true", help="ignore the wikitext cache")
    args = parser.parse_args()

    titles = _read_column(BATTLE_UNIVERSE_PATH, "battle_title")
    seed_titles = _read_column(SEED_ROSTER_PATH, "general_title")

    cache = crawl(titles, refresh=args.refresh)
    pages_found = sum(1 for title in titles if title in cache)
    print(f"{pages_found}/{len(titles)} battle pages found in wikitext cache")

    identity_resolver = _load_identity_resolver()
    print(
        f"identity resolver: {len(identity_resolver)} titles"
        if identity_resolver is not None
        else "identity resolver: none (data/raw/identity_map.json not found, falling back to raw slugs)"
    )

    appearances = []
    for title in titles:
        wikitext = cache.get(title)
        if wikitext:
            appearances.extend(battle_appearances(title, wikitext, identity_resolver))
    print(f"{len(appearances)} general-perspective battle appearances parsed")

    seed_ids = seed_general_ids(seed_titles, identity_resolver)
    roster = select_roster(appearances, seed_ids, args.min_battles)
    rows = generals_csv_rows(roster)
    print(f"{len(roster)} generals cleared the bar; {len(rows)} have a dateable battle -> generals.csv")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=GENERAL_FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUTPUT_PATH}")

    report = {
        "min_battles": args.min_battles,
        "candidate_battle_titles": len(titles),
        "battle_pages_found": pages_found,
        "appearances_parsed": len(appearances),
        "seed_general_titles": len(seed_titles),
        "generals_kept": len(roster),
        "generals_written": len(rows),
        "generals_dropped_no_dateable_battle": len(roster) - len(rows),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
