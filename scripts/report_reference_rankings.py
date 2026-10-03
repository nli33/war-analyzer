#!/usr/bin/env python3
"""G3: compare the `data/auto/` composite ranking against published "top N greatest generals"
lists, as a reference/sanity check only (PROGRESS.md: "never a roster source or a weight").

    python scripts/report_reference_rankings.py

Reads `data/reference/top_n_lists.csv` (name/rank/source/url, collected by hand per G3's own
"fetch pages with plain HTTP, read names off a list page" rule -- no per-general research), and
for each listed name:

1. Resolves it to a canonical Wikipedia identity the same way E1 does for every commander wikilink
   title (MediaWiki redirects + Wikidata `pageprops`), reusing `data/raw/identity_map.json` where
   a name happens to already be a key and otherwise fetching fresh (cached, resumable, at
   `data/raw/reference_identity_cache.json`).
2. Merges that identity into the same Wikidata-sharing resolver `war.roster`'s pipeline already
   uses, so a reference-list name that's secretly the same person as an already-ingested
   commander (different title, same Wikidata item) lands on the same `general_id` the roster
   uses for them -- not a second, disconnected identity.
3. Checks membership in `data/auto/generals.csv` and, if present, looks up their composite rank
   from `data/auto/battles.csv` + `data/auto/generals.csv` via `composite_ranking_rows`.

Writes `data/raw/reference_ranking_report.json` (every entry's status, the Spearman correlation
per source over entries that resolved to a ranked roster general, and the biggest percentile
disagreements) and prints a human-readable summary.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.identity import (  # noqa: E402
    IdentityInfo,
    build_general_id_resolver,
    load_identity_map,
    resolve_identities,
)
from war.records import load_battles, load_generals  # noqa: E402
from war.reference_rankings import (  # noqa: E402
    biggest_disagreements,
    build_comparison_rows,
    load_reference_list,
    rank_correlation_by_source,
)
from war.roster import pipeline_general_id_for  # noqa: E402
from war.viz.ranking_tables import composite_ranking_rows  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_LIST_PATH = REPO_ROOT / "data" / "reference" / "top_n_lists.csv"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
REFERENCE_IDENTITY_CACHE_PATH = REPO_ROOT / "data" / "raw" / "reference_identity_cache.json"
AUTO_GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
AUTO_BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "reference_ranking_report.json"


def _load_reference_identity_cache() -> dict[str, IdentityInfo]:
    if not REFERENCE_IDENTITY_CACHE_PATH.exists():
        return {}
    raw = json.loads(REFERENCE_IDENTITY_CACHE_PATH.read_text(encoding="utf-8"))
    return {
        name: IdentityInfo(
            requested_title=entry["requested_title"],
            canonical_title=entry["canonical_title"],
            wikidata_id=entry["wikidata_id"],
            is_disambiguation=entry["is_disambiguation"],
        )
        for name, entry in raw.items()
    }


def _save_reference_identity_cache(cache: dict[str, IdentityInfo]) -> None:
    REFERENCE_IDENTITY_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw = {
        name: {
            "requested_title": info.requested_title,
            "canonical_title": info.canonical_title,
            "wikidata_id": info.wikidata_id,
            "is_disambiguation": info.is_disambiguation,
        }
        for name, info in cache.items()
    }
    REFERENCE_IDENTITY_CACHE_PATH.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_reference_names(names: list[str]) -> dict[str, IdentityInfo]:
    """Resolve every reference-list name to an `IdentityInfo`, reusing E1's pipeline cache first
    (a name might already be a commander wikilink title seen in the battle corpus) and falling
    back to a fresh, separately-cached MediaWiki lookup for the rest. Resumable: a name already
    in either cache is never re-fetched."""
    pipeline_identities = load_identity_map(IDENTITY_MAP_PATH)
    reference_cache = _load_reference_identity_cache()

    missing = [n for n in names if n not in pipeline_identities and n not in reference_cache]
    if missing:
        resolved = resolve_identities(missing)
        reference_cache.update(resolved)
        _save_reference_identity_cache(reference_cache)

    resolved_by_name: dict[str, IdentityInfo] = {}
    for name in names:
        resolved_by_name[name] = pipeline_identities.get(name) or reference_cache.get(name)
    return resolved_by_name, pipeline_identities, reference_cache


def main() -> int:
    entries = load_reference_list(REFERENCE_LIST_PATH)
    names = sorted({entry.name for entry in entries})
    print(f"{len(entries)} reference-list rows across {len({e.source for e in entries})} sources, "
          f"{len(names)} distinct names")

    name_identities, pipeline_identities, reference_cache = resolve_reference_names(names)

    # Build the same Wikidata-sharing resolver the pipeline itself uses, but informed by *both*
    # the corpus identities and the reference names -- so a reference name that shares a
    # Wikidata ID with an already-ingested commander title resolves to that commander's
    # general_id, not a disconnected second one.
    merged_identities = {**pipeline_identities, **reference_cache}
    resolver = build_general_id_resolver(merged_identities)

    name_to_general_id: dict[str, str | None] = {}
    for name in names:
        info = name_identities.get(name)
        if info is None or info.canonical_title is None or info.is_disambiguation:
            name_to_general_id[name] = None
        else:
            name_to_general_id[name] = pipeline_general_id_for(info.canonical_title, resolver)

    unresolved = [n for n in names if name_to_general_id[n] is None]
    if unresolved:
        print(f"{len(unresolved)} name(s) did not resolve to a Wikipedia identity: {unresolved}")

    generals = load_generals(AUTO_GENERALS_PATH)
    battles = load_battles(AUTO_BATTLES_PATH)
    roster_general_ids = {g.general_id for g in generals}
    ranking_rows = composite_ranking_rows(battles, generals)
    rank_by_general_id = {row.general_id: row.rank for row in ranking_rows}
    battle_count_by_general_id = {row.general_id: row.battle_count for row in ranking_rows}

    comparison_rows = build_comparison_rows(
        entries, name_to_general_id, roster_general_ids, rank_by_general_id, battle_count_by_general_id
    )

    list_size_by_source: dict[str, int] = {}
    for entry in entries:
        list_size_by_source[entry.source] = max(list_size_by_source.get(entry.source, 0), entry.rank)

    correlations = rank_correlation_by_source(comparison_rows)
    disagreements = biggest_disagreements(
        comparison_rows, list_size_by_source, roster_ranked_count=len(ranking_rows), top_k=10
    )

    status_counts: dict[str, int] = {}
    for row in comparison_rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1

    print(f"\nStatus breakdown across all {len(comparison_rows)} reference entries: {status_counts}")
    print(f"\nSpearman correlation (published rank vs. our composite rank), per source, over "
          f"'ranked' entries only:")
    for source, corr in sorted(correlations.items()):
        n_ranked = sum(1 for r in comparison_rows if r.source == source and r.status == "ranked")
        print(f"  {source}: {corr!r} (n={n_ranked})")

    print("\nMissing or unresolved listed generals:")
    for row in comparison_rows:
        if row.status in ("missing", "unresolved"):
            print(f"  [{row.source}] #{row.published_rank} {row.name!r} -> {row.status}"
                  f" (general_id={row.general_id!r})")

    print("\nBiggest published-rank vs. our-rank disagreements:")
    for d in disagreements:
        print(f"  [{d['source']}] {d['name']}: published #{d['published_rank']} "
              f"(pct {d['published_percentile']}), ours #{d['our_rank']} (pct {d['our_percentile']}), "
              f"disagreement {d['disagreement']}")

    report = {
        "status_counts": status_counts,
        "correlations_by_source": correlations,
        "biggest_disagreements": disagreements,
        "entries": [
            {
                "source": row.source,
                "published_rank": row.published_rank,
                "name": row.name,
                "general_id": row.general_id,
                "status": row.status,
                "our_rank": row.our_rank,
                "our_battle_count": row.our_battle_count,
            }
            for row in comparison_rows
        ],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
