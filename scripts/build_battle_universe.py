#!/usr/bin/env python3
"""C1: crawl Wikipedia's "List of battles" pages into a candidate battle-title list.

    python scripts/build_battle_universe.py

Fetches the 7 pages Wikipedia splits its battle index across (before 301, 301-1300,
1301-1600, 1601-1800, 1801-1900, 1901-2000, since 2001 — see `war.scrape.LIST_OF_BATTLES_PAGES`)
and extracts candidate battle-page titles from each (`war.scrape.extract_battle_titles`).

This is a candidate list, not a verified one: a title is kept if a wikilink's target contains a
battle-like keyword (Fall/Battle/Siege/Capture/Operation/Action/Recapture, per the A1 reuse note
in the dev log). Some candidates won't have a page, or won't have a military-conflict infobox at
all (a campaign page, a redirect to a disambiguation page) — C2's infobox extractor is the
precision filter; this script's job is cheap recall over the 7 index pages.

Wikitext for the 7 list pages is cached at data/raw/battle_universe_cache.json (gitignored) so
reruns are resumable: a page already in the cache is not re-fetched. Delete that file, or pass
--refresh, to force a fresh crawl.

Output: data/raw/battle_universe.csv (gitignored, regenerable), columns `battle_title`,
`source_list_page` — one row per distinct candidate title, naming the first list page it was
found on.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.scrape import (  # noqa: E402
    LIST_OF_BATTLES_PAGES,
    extract_battle_titles,
    fetch_wikitext_batch,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe_cache.json"
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text())
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))


def crawl(refresh: bool = False) -> dict[str, str]:
    """Fetch (or reuse cached) wikitext for every list-of-battles page.

    Resumable: only pages missing from the cache are fetched over the network; a page already
    cached from a prior run is skipped. Network fetch is a single batched call (throttled with
    backoff inside `fetch_wikitext_batch`), not one request per page.
    """
    cache = {} if refresh else _load_cache()
    missing = [title for title in LIST_OF_BATTLES_PAGES if title not in cache]
    if missing:
        cache.update(fetch_wikitext_batch(missing))
        _save_cache(cache)
    return cache


def build_universe(cache: dict[str, str]) -> list[tuple[str, str]]:
    """Extract and dedupe candidate battle titles across all cached list pages."""
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for page_title in LIST_OF_BATTLES_PAGES:
        wikitext = cache.get(page_title)
        if not wikitext:
            continue
        for battle_title in extract_battle_titles(wikitext):
            if battle_title in seen:
                continue
            seen.add(battle_title)
            rows.append((battle_title, page_title))
    rows.sort()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--refresh", action="store_true", help="ignore the cache, re-fetch all 7 list pages"
    )
    args = parser.parse_args()

    cache = crawl(refresh=args.refresh)
    missing_pages = [title for title in LIST_OF_BATTLES_PAGES if title not in cache]
    if missing_pages:
        print(
            f"warning: {len(missing_pages)} list page(s) could not be fetched: {missing_pages}",
            file=sys.stderr,
        )

    rows = build_universe(cache)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["battle_title", "source_list_page"])
        writer.writerows(rows)

    print(
        f"{len(cache)}/{len(LIST_OF_BATTLES_PAGES)} list pages cached; "
        f"{len(rows)} candidate battle titles -> {OUTPUT_PATH}"
    )
    return 1 if missing_pages else 0


if __name__ == "__main__":
    raise SystemExit(main())
