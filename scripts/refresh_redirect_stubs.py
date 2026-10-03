#!/usr/bin/env python3
"""F2 fix 1: refresh stale wikitext-cache entries that are bare `#REDIRECT` stubs.

`data/raw/battle_wikitext_cache.json` was built before commit b57cc1b taught
`war.scrape.fetch_wikitext_batch` to follow redirects server-side (`redirects=1`). Any candidate
title that was itself a redirect page got cached as its own one-line `#REDIRECT [[Target]]`
stub instead of the target page's content, so it looks infobox-less (F1's "no_infobox" stage)
even though the target page has a real infobox. This script finds those stale entries among the
candidate battle titles, re-fetches just those titles (today's redirect-aware code resolves them
correctly), and overwrites their cache entries in place.

Anchor redirects (`#REDIRECT [[Page#Section]]`, e.g. "Battle of 1st Saratoga" ->
"Battles of Saratoga#First Saratoga: ...") are skipped — see `war.scrape.redirect_stub_target`'s
docstring for why re-fetching those would risk misattributing the wrong sub-battle's infobox.

    python scripts/refresh_redirect_stubs.py
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.scrape import fetch_wikitext_batch, redirect_stub_target  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"


def main() -> int:
    with BATTLE_UNIVERSE_PATH.open(newline="", encoding="utf-8") as handle:
        titles = [row["battle_title"] for row in csv.DictReader(handle)]
    cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))

    stale = [title for title in titles if title in cache and redirect_stub_target(cache[title])]
    print(f"{len(stale)} candidate titles are stale (bare, non-anchored) redirect stubs")
    if not stale:
        return 0

    fetched = fetch_wikitext_batch(stale)
    resolved = 0
    for title in stale:
        new_content = fetched.get(title)
        if new_content is not None and redirect_stub_target(new_content) is None:
            cache[title] = new_content
            resolved += 1
    print(f"{resolved}/{len(stale)} re-fetched as non-stub content (rest stayed as-is)")

    WIKITEXT_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))
    print(f"wrote {WIKITEXT_CACHE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
