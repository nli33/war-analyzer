#!/usr/bin/env python3
"""C7: score the real pipeline extractor against the 177-row gold set in data/battles.csv.

    python scripts/eval_ingest.py

For each gold battle, fetches the Wikipedia page named by `battle_name` and runs the actual
production modules: `war.commanders.extract_commander_fields`/`primary_commander` (C3) to find
which infobox side (1 or 2) the gold row's `general_id` personally commanded, and
`war.infobox_numbers.extract_strength_and_casualties` (C2) to parse that side's numbers. A gold
row with no commander-side match (slug mismatch, missing/unlinked commander field, etc.) is
"not covered" for every field, the same way a missing Wikipedia page is — both are real pipeline
misses, not scoring artifacts. This replaces A3's naive "first number, oracle-picked
orientation" baseline (see `notes/dev-log.md`'s A3 entry for that baseline's numbers) now that
C2/C3 are real code instead of a stand-in.

Reports, per field, coverage (share of the 177 gold rows where a number was extracted) and the
share within 1.5x/2x/3x of the gold value, using log error: a field counts as "within Nx" iff
abs(log(extracted / gold)) <= log(N).

Wikitext is cached at data/raw/eval_ingest_cache.json (gitignored) so reruns during development
don't re-hit the network. Delete that file (or pass --no-cache) to force a fresh fetch.
"""

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.commanders import extract_commander_fields, primary_commander  # noqa: E402
from war.infobox_numbers import extract_strength_and_casualties  # noqa: E402
from war.records import load_battles  # noqa: E402
from war.scrape import fetch_wikitext_batch  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "raw" / "eval_ingest_cache.json"

FACTORS = (1.5, 2.0, 3.0)

STRENGTH_FIELDS = ("own_troop_strength", "enemy_troop_strength")
CASUALTY_FIELDS = ("own_casualties", "enemy_casualties")
ALL_FIELDS = STRENGTH_FIELDS + CASUALTY_FIELDS

# The gold set's `general_id` predates this pipeline and was hand-chosen per general (B1/A6),
# not derived from a Wikipedia title the way the auto pipeline's roster ids always are (C4b's
# `general_id_from_title`). For these 5 gold generals, infobox commander wikilinks resolve to a
# different (but same-person) slug than the gold id — e.g. Hannibal's own Wikipedia page is
# titled "Hannibal", not "Hannibal Barca". Without this map, the eval would score a real same-
# person match as a miss purely because of a naming convention gap that doesn't exist in the
# auto pipeline (where the roster id and the infobox-derived id always come from the same
# title). Confirmed by hand against every mismatch this produced (see dev log's C7 entry) that
# every id listed here is the *same individual*, not a co-commander or opponent.
GOLD_ID_ALIASES: dict[str, set[str]] = {
    "napoleon-bonaparte": {"napoleon", "napoleon-i"},
    "frederick-the-great": {"frederick-ii-of-prussia"},
    "genghis-khan": {"temujin"},
    "hannibal-barca": {"hannibal"},
    "wellington": {"arthur-wellesley-1st-duke-of-wellington"},
}


def _matches_gold_id(extracted_id: str, gold_general_id: str) -> bool:
    return extracted_id == gold_general_id or extracted_id in GOLD_ID_ALIASES.get(
        gold_general_id, set()
    )


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def fetch_all_wikitext(titles: list[str], use_cache: bool = True) -> dict[str, str]:
    """Fetch wikitext for every title, filling in from cache first. Network calls for misses.

    `use_cache=False` ("--no-cache") means start from an empty cache (force a fresh fetch for
    every title), not "never touch disk" — any newly-fetched wikitext is still written back, as
    the CLI help text ("ignore/overwrite the wikitext cache") promises. Skipping the save here
    silently discarded a fresh fetch's results once already caught this exact way (C7): the
    on-disk cache kept serving pre-bugfix wikitext indefinitely, even right after a `--no-cache`
    run that fetched the corrected content.
    """
    cache = _load_cache() if use_cache else {}
    missing = [title for title in titles if title not in cache]
    if missing:
        fetched = fetch_wikitext_batch(missing)
        cache.update(fetched)
        _save_cache(cache)
    return cache


def find_own_side(wikitext: str, gold_general_id: str) -> str | None:
    """Which infobox side ("1" or "2") this gold general personally commanded (C3's rule),
    or None if neither side's primary commander's `general_id` matches (via `GOLD_ID_ALIASES`)
    — a real pipeline miss (unlinked/missing commander field, a command-attribution granularity
    the first-listed-commander rule can't see), not fetched/skipped here."""
    commander_fields = extract_commander_fields(wikitext)
    for side in ("1", "2"):
        primary = primary_commander(commander_fields.get(f"commander{side}", []))
        if primary is not None and _matches_gold_id(primary.general_id, gold_general_id):
            return side
    return None


def extract_for_battle(wikitext: str, gold_general_id: str) -> dict[str, int | None]:
    """Return {field_name: extracted_value_or_None} for one battle's four scored fields, using
    the real C2/C3 extractor (no gold-value peeking to pick an orientation)."""
    own_side = find_own_side(wikitext, gold_general_id)
    if own_side is None:
        return {field: None for field in ALL_FIELDS}
    enemy_side = "2" if own_side == "1" else "1"

    numbers = extract_strength_and_casualties(wikitext)
    own_strength = numbers.get(f"strength{own_side}")
    enemy_strength = numbers.get(f"strength{enemy_side}")
    own_casualties = numbers.get(f"casualties{own_side}")
    enemy_casualties = numbers.get(f"casualties{enemy_side}")

    return {
        "own_troop_strength": own_strength.point if own_strength else None,
        "enemy_troop_strength": enemy_strength.point if enemy_strength else None,
        "own_casualties": own_casualties.point if own_casualties else None,
        "enemy_casualties": enemy_casualties.point if enemy_casualties else None,
    }


def score_field(pairs: list[tuple[int, int | None]]) -> dict:
    """pairs: list of (gold_value, extracted_value_or_None). Returns coverage + factor buckets."""
    total = len(pairs)
    present = [(gold, extracted) for gold, extracted in pairs if extracted is not None]
    coverage = len(present) / total if total else 0.0

    result = {"total": total, "covered": len(present), "coverage": coverage}
    for factor in FACTORS:
        within = sum(
            1
            for gold, extracted in present
            if gold > 0 and extracted > 0 and abs(math.log(extracted / gold)) <= math.log(factor)
        )
        key = f"within_{factor}x"
        result[key] = within
        result[f"{key}_share"] = within / len(present) if present else 0.0
    return result


def run_eval(limit: int | None = None, use_cache: bool = True) -> dict:
    battles = load_battles()
    if limit is not None:
        battles = battles[:limit]

    titles = [battle.battle_name for battle in battles]
    wikitext_by_title = fetch_all_wikitext(titles, use_cache=use_cache)

    per_field_pairs: dict[str, list[tuple[int, int | None]]] = {field: [] for field in ALL_FIELDS}
    pages_found = 0

    for battle in battles:
        wikitext = wikitext_by_title.get(battle.battle_name)
        if wikitext is None:
            for field in ALL_FIELDS:
                per_field_pairs[field].append((getattr(battle, field), None))
            continue
        pages_found += 1
        extracted = extract_for_battle(wikitext, battle.general_id)
        for field in ALL_FIELDS:
            per_field_pairs[field].append((getattr(battle, field), extracted[field]))

    report = {
        "gold_rows": len(battles),
        "pages_found": pages_found,
        "page_found_share": pages_found / len(battles) if battles else 0.0,
        "fields": {field: score_field(pairs) for field, pairs in per_field_pairs.items()},
    }
    return report


def print_report(report: dict) -> None:
    print(f"gold rows: {report['gold_rows']}")
    print(
        f"wikipedia page found for battle_name as-is: {report['pages_found']}/"
        f"{report['gold_rows']} ({report['page_found_share']:.0%})"
    )
    print()
    header = f"{'field':<22}{'coverage':<16}" + "".join(f"<={f}x".rjust(9) for f in FACTORS)
    print(header)
    print("-" * len(header))
    for field, stats in report["fields"].items():
        coverage_str = f"{stats['covered']}/{stats['total']} ({stats['coverage']:.0%})"
        row = f"{field:<22}{coverage_str:<16}"
        row += "".join(f"{stats[f'within_{f}x_share']:.0%}".rjust(9) for f in FACTORS)
        print(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="score only the first N gold rows")
    parser.add_argument("--no-cache", action="store_true", help="ignore/overwrite the wikitext cache")
    parser.add_argument("--json", type=Path, default=None, help="also write the report as JSON")
    args = parser.parse_args()

    report = run_eval(limit=args.limit, use_cache=not args.no_cache)
    print_report(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
