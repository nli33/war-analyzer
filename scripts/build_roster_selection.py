#!/usr/bin/env python3
"""C4b/E4: select the automated general roster and write data/auto/generals.csv.

    python scripts/build_roster_selection.py [--min-battles N]

Fetches wikitext for every candidate battle title in C1's `data/raw/battle_universe.csv`
(cached/resumable at data/raw/battle_wikitext_cache.json, same pattern as every other crawl
script in this project), parses each page into 0-2 `war.roster.BattleAppearance`s (C2 strength
extraction + C3 commander/side extraction, combined side-aware by `war.roster.battle_appearances`),
and selects a roster: E4 dropped the old seed-list gate -- any general (seed-listed or not) with
at least `--min-battles` battles with usable strength on both sides joins. The seed list is kept
only as a flag in `generals.csv`'s `notes` column, not as a membership rule.

Every general in `data/must_include.csv` (E3: the 19 gold-set generals plus Han Xin) joins
regardless of `--min-battles`. If a must-include general's own pipeline battle count is still
below the bar ("thin"): the 19 gold-set generals (everyone in `data/must_include.csv` except
Han Xin) fall back to their hand-curated `data/generals.csv` row verbatim, with `notes` rewritten
to say so; Han Xin has no hand-curated rows, so the thin pipeline entry is kept as-is with a note
explaining why. See `war.roster.select_roster`/`generals_csv_rows` for the mechanics.

Output: data/auto/generals.csv (schema per war/schema.py GENERAL_COLUMNS). Does not touch
data/generals.csv (the hand-curated gold set, read-only here, left untouched per PROGRESS.md's
"Decisions already made"). Also writes data/raw/roster_selection_report.json with the counts
behind the choice of --min-battles and the must-include thin/fallback cases, so they can be
checked against PROGRESS.md's Notes entry rather than re-run to reproduce.
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
    pipeline_general_id_for,
    seed_general_ids,
    select_roster,
    usable_battle_counts,
)
from war.scrape import fetch_wikitext_batch  # noqa: E402
from war.schema import GENERAL_FIELD_NAMES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
SEED_ROSTER_PATH = REPO_ROOT / "data" / "raw" / "general_seed_roster.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
GOLD_GENERALS_PATH = REPO_ROOT / "data" / "generals.csv"
HAN_XIN_GENERAL_ID = "han-xin"
OUTPUT_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "roster_selection_report.json"

DEFAULT_MIN_BATTLES = 4


def _load_identity_resolver() -> dict[str, str | None] | None:
    """E2: `None` (raw-slug fallback for every title) if E1 hasn't been run yet; otherwise the
    full title -> canonical-general_id map built from `data/raw/identity_map.json`."""
    if not IDENTITY_MAP_PATH.exists():
        return None
    return build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def _read_dicts(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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


def resolve_must_include_fallbacks(
    must_include_rows: list[dict],
    resolver: dict[str, str | None],
    usable_count: dict[str, int],
    min_battles: int,
) -> tuple[dict[str, dict], dict[str, str], list[dict]]:
    """Classify each must-include general against the chosen `min_battles` bar.

    Returns `(hand_curated_fallback, extra_notes, thin_report)`:
    - `hand_curated_fallback`: `{gold_general_id: {"pipeline_general_id", "usable"}}` for the
      gold-set generals (everyone except Han Xin) whose own pipeline battle count is thin --
      these need their `data/generals.csv` row substituted in by the caller.
    - `extra_notes`: `{pipeline_general_id: note}` for Han Xin only, when thin (no hand-curated
      rows exist for Han Xin to fall back to).
    - `thin_report`: one dict per thin must-include general, for `roster_selection_report.json`.
    """
    hand_curated_fallback: dict[str, dict] = {}
    extra_notes: dict[str, str] = {}
    thin_report: list[dict] = []

    for row in must_include_rows:
        pipeline_id = pipeline_general_id_for(row["canonical_title"], resolver)
        usable = usable_count.get(pipeline_id, 0)
        if usable >= min_battles:
            continue

        if row["general_id"] == HAN_XIN_GENERAL_ID:
            fallback = "pipeline-thin (no hand-curated rows for Han Xin)"
            extra_notes[pipeline_id] = (
                f"THIN must-include (E4): only {usable} usable-strength battle(s) found "
                f"(need {min_battles}); no hand-curated rows exist for Han Xin, using "
                "pipeline data as-is."
            )
        else:
            fallback = "hand-curated fallback"
            hand_curated_fallback[row["general_id"]] = {
                "pipeline_general_id": pipeline_id,
                "usable": usable,
            }

        thin_report.append(
            {
                "general_id": row["general_id"],
                "canonical_title": row["canonical_title"],
                "pipeline_general_id": pipeline_id,
                "usable": usable,
                "fallback": fallback,
            }
        )

    return hand_curated_fallback, extra_notes, thin_report


def apply_hand_curated_fallbacks(
    rows: list[dict],
    hand_curated_fallback: dict[str, dict],
    min_battles: int,
) -> list[dict]:
    """Append each thin gold-set must-include general's verbatim `data/generals.csv` row, with
    `notes` rewritten to say so. Callers must have already popped `info["pipeline_general_id"]`
    out of the roster passed to `generals_csv_rows` before calling this, so `rows` doesn't still
    carry that general's thin pipeline-derived row under the same (or a different) general_id."""
    if not hand_curated_fallback:
        return rows

    gold_generals = {row["general_id"]: row for row in _read_dicts(GOLD_GENERALS_PATH)}
    for general_id, info in hand_curated_fallback.items():
        gold_row = dict(gold_generals[general_id])
        gold_row["notes"] = (
            f"hand-curated fallback (E4, must-include): pipeline found only {info['usable']} "
            f"usable-strength battle(s) under general_id={info['pipeline_general_id']!r} "
            f"(need {min_battles}); using data/generals.csv's gold-set row verbatim. "
            f"{gold_row.get('notes', '')}"
        ).strip()
        rows.append(gold_row)

    rows.sort(key=lambda row: row["general_id"])
    return rows


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
    must_include_rows = _read_dicts(MUST_INCLUDE_PATH)

    cache = crawl(titles, refresh=args.refresh)
    pages_found = sum(1 for title in titles if title in cache)
    print(f"{pages_found}/{len(titles)} battle pages found in wikitext cache")

    identity_resolver = _load_identity_resolver()
    print(
        f"identity resolver: {len(identity_resolver)} titles"
        if identity_resolver is not None
        else "identity resolver: none (data/raw/identity_map.json not found, falling back to raw slugs)"
    )
    resolver = identity_resolver if identity_resolver is not None else {}

    appearances = []
    for title in titles:
        wikitext = cache.get(title)
        if wikitext:
            appearances.extend(battle_appearances(title, wikitext, identity_resolver))
    print(f"{len(appearances)} general-perspective battle appearances parsed")

    seed_ids = seed_general_ids(seed_titles, identity_resolver)
    usable_count = usable_battle_counts(appearances)

    must_include_pipeline_ids = frozenset(
        pipeline_general_id_for(row["canonical_title"], resolver) for row in must_include_rows
    )
    roster = select_roster(appearances, args.min_battles, must_include_ids=must_include_pipeline_ids)

    hand_curated_fallback, extra_notes, thin_report = resolve_must_include_fallbacks(
        must_include_rows, resolver, usable_count, args.min_battles
    )
    for info in hand_curated_fallback.values():
        roster.pop(info["pipeline_general_id"], None)

    rows = generals_csv_rows(roster, seed_ids=frozenset(seed_ids), extra_notes=extra_notes)
    rows = apply_hand_curated_fallbacks(rows, hand_curated_fallback, args.min_battles)

    print(
        f"{len(roster)} generals cleared the bar (pipeline roster, pre-fallback); "
        f"{len(hand_curated_fallback)} must-include generals fell back to hand-curated data; "
        f"{len(rows)} total rows -> generals.csv"
    )
    for entry in thin_report:
        print(
            f"  thin must-include: {entry['general_id']} ({entry['canonical_title']}) "
            f"-> general_id={entry['pipeline_general_id']} usable={entry['usable']}: {entry['fallback']}"
        )

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
        "generals_dropped_no_dateable_battle": len(roster) - (len(rows) - len(hand_curated_fallback)),
        "must_include_total": len(must_include_rows),
        "must_include_thin": thin_report,
        "hand_curated_fallback_general_ids": sorted(hand_curated_fallback),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
