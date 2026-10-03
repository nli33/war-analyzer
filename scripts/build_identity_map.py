#!/usr/bin/env python3
"""E1: resolve every distinct commander wikilink title to a canonical identity.

    python scripts/build_identity_map.py

Scans every cached battle page (`data/raw/battle_wikitext_cache.json`, the same cache C1/C4b
crawl into) for `commander1`/`commander2` wikilinks (C3's `war.commanders.extract_commander_fields`),
collects the distinct linked titles, and batches them through `war.identity.resolve_identities`
(MediaWiki redirects + Wikidata `pageprops`, 50 titles per call). Results are cached at
`data/raw/identity_cache.json` (gitignored, resumable: a title already in the cache is not
re-fetched) and written to `data/raw/identity_map.json` (title -> canonical title / Wikidata ID /
disambiguation flag) for E2 to consume.

Prints the distinct-title count before resolution (raw wikilink titles) and after (distinct
Wikidata IDs among resolved, non-disambiguation titles, plus titles with no Wikidata ID counted
individually) — the gap between the two is exactly how much the E2 merge is expected to collapse
the roster by. Also prints the Napoleon/Wellington/Hannibal spot-check PROGRESS.md's E1 line asks
for, when those variants are present in this run's title set.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.commanders import extract_commander_fields  # noqa: E402
from war.identity import resolve_identities  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
IDENTITY_CACHE_PATH = REPO_ROOT / "data" / "raw" / "identity_cache.json"
OUTPUT_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"

_SPOT_CHECK_VARIANTS = {
    "Napoleon": ("Napoleon", "Napoleon I", "Napoleon Bonaparte"),
    "Wellington": (
        "Arthur Wellesley, 1st Duke of Wellington",
        "Duke of Wellington",
    ),
    "Hannibal": ("Hannibal", "Hannibal Barca"),
}


def collect_commander_titles(wikitext_cache: dict[str, str]) -> list[str]:
    titles: set[str] = set()
    for wikitext in wikitext_cache.values():
        fields = extract_commander_fields(wikitext)
        for side in fields.values():
            for ref in side:
                if ref.wikipedia_title:
                    titles.add(ref.wikipedia_title)
    return sorted(titles)


def _load_identity_cache() -> dict[str, dict]:
    if IDENTITY_CACHE_PATH.exists():
        return json.loads(IDENTITY_CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_identity_cache(cache: dict[str, dict]) -> None:
    IDENTITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    IDENTITY_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def resolve_cached(titles: list[str], refresh: bool = False) -> dict[str, dict]:
    """Resolve every title, reusing (and extending) the on-disk cache. Resumable: only titles
    missing from the cache are fetched over the network."""
    cache = {} if refresh else _load_identity_cache()
    missing = [title for title in titles if title not in cache]
    if missing:
        resolved = resolve_identities(missing)
        for title, info in resolved.items():
            cache[title] = {
                "requested_title": info.requested_title,
                "canonical_title": info.canonical_title,
                "wikidata_id": info.wikidata_id,
                "is_disambiguation": info.is_disambiguation,
            }
        _save_identity_cache(cache)
    return cache


def count_distinct_identities(cache: dict[str, dict], titles: list[str]) -> int:
    """Distinct identities among `titles`: titles sharing a Wikidata ID count once; a title with
    no Wikidata ID (unresolved, or resolved but no `wikibase_item`) counts on its own."""
    seen_wikidata_ids: set[str] = set()
    count = 0
    for title in titles:
        entry = cache.get(title, {})
        wikidata_id = entry.get("wikidata_id")
        if wikidata_id:
            if wikidata_id in seen_wikidata_ids:
                continue
            seen_wikidata_ids.add(wikidata_id)
        count += 1
    return count


def main() -> int:
    refresh = "--refresh" in sys.argv

    wikitext_cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))
    titles = collect_commander_titles(wikitext_cache)
    print(f"{len(titles)} distinct commander wikilink titles found in the battle wikitext cache")

    cache = resolve_cached(titles, refresh=refresh)

    after = count_distinct_identities(cache, titles)
    print(f"before resolution: {len(titles)} distinct titles")
    print(f"after resolution:  {after} distinct identities (shared Wikidata IDs merged)")

    for label, variants in _SPOT_CHECK_VARIANTS.items():
        present = [v for v in variants if v in cache]
        if not present:
            print(f"spot-check {label}: none of {variants} found in this run's title set")
            continue
        resolved = {(cache[v]["canonical_title"], cache[v]["wikidata_id"]) for v in present}
        status = "OK, single identity" if len(resolved) == 1 else "MISMATCH"
        print(f"spot-check {label}: {present} -> {resolved} ({status})")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
