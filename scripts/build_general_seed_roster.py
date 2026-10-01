#!/usr/bin/env python3
"""C4a: crawl Wikipedia general/commander categories into a candidate general-name list.

    python scripts/build_general_seed_roster.py

Fetches the ~85 category pages in `war.scrape.GENERAL_SEED_CATEGORIES` (by century, by war, by
nationality — see that constant's docstring for how the list was chosen) and lists their
member article titles. This is "Wikipedia's lists of commanders and generals by era" from
PROGRESS.md's C4a line; the other half of that line ("online top X generals" published
rankings) was dropped — see the dev log's C4a entry for why.

This is a candidate list, not a verified roster: a title here is any Wikipedia article a human
editor filed under one of these categories, which includes some non-general military figures
(an admiral miscategorized, a politician who briefly held a general's rank) and excludes real
generals whose articles were never category-tagged. C4b's battle-match filter is the precision
step on this list, the same way C2's infobox extractor is the precision filter on C1's battle
universe.

Member lists per category are cached at data/raw/general_seed_cache.json (gitignored) so reruns
are resumable: a category already in the cache is not re-fetched. Delete that file, or pass
--refresh, to force a fresh crawl.

Output: data/raw/general_seed_roster.csv (gitignored, regenerable), columns `general_title`,
`source_category` — one row per distinct candidate title, naming the first category it was
found in.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.scrape import GENERAL_SEED_CATEGORIES, fetch_category_members  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "raw" / "general_seed_cache.json"
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "general_seed_roster.csv"


def _load_cache() -> dict[str, list[str]]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict[str, list[str]]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def crawl(refresh: bool = False) -> dict[str, list[str]]:
    """Fetch (or reuse cached) member titles for every seed category.

    Resumable: only categories missing from the cache are fetched over the network.
    """
    cache = {} if refresh else _load_cache()
    for category in GENERAL_SEED_CATEGORIES:
        if category in cache:
            continue
        cache[category] = fetch_category_members(category)
        _save_cache(cache)
    return cache


def build_roster(cache: dict[str, list[str]]) -> list[tuple[str, str]]:
    """Dedupe candidate general titles across all cached categories, first-seen category wins.

    Drops "List of ..." pages — a navigational article (e.g. "List of Roman generals") can be
    filed in the same category as the people it lists, the same false-positive shape C1's
    `extract_battle_titles` already filters for "List of sieges" on a battle index page.
    """
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for category in GENERAL_SEED_CATEGORIES:
        for title in cache.get(category, []):
            if title in seen:
                continue
            if title.lower().startswith("list of") or title.lower().startswith("lists of"):
                continue
            seen.add(title)
            rows.append((title, category))
    rows.sort()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="ignore the cache, re-fetch all categories"
    )
    args = parser.parse_args()

    cache = crawl(refresh=args.refresh)
    missing = [c for c in GENERAL_SEED_CATEGORIES if c not in cache]
    if missing:
        print(f"warning: {len(missing)} categor(ies) could not be fetched: {missing}", file=sys.stderr)

    rows = build_roster(cache)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["general_title", "source_category"])
        writer.writerows(rows)

    print(
        f"{len(cache)}/{len(GENERAL_SEED_CATEGORIES)} categories cached; "
        f"{len(rows)} candidate general titles -> {OUTPUT_PATH}"
    )
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
