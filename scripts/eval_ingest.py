#!/usr/bin/env python3
"""A3: score a Wikipedia-infobox extractor against the 177-row gold set in data/battles.csv.

    python scripts/eval_ingest.py

For each gold battle, fetches the Wikipedia page named by `battle_name`, pulls the military
infobox (`war.scrape.parse_military_infobox`), and runs a NAIVE numeric parser (defined in this
file, not war/scrape.py) over strength1/strength2/casualties1/casualties2. The naive parser is a
throwaway baseline, not the production extractor: it takes the first number in each field and
does not handle ranges, per-nation breakdowns, or unit words beyond k/m. Its whole job is to find
where it breaks so C2 knows what the real parser has to handle (PROGRESS.md: "Add a test for each
failure mode that A3 shows").

Side matching (own vs. enemy <-> strength1/strength2) is not solved yet either — that is C3's
job (commander names -> sides). This script picks whichever of the two possible orientations
minimizes total log-error per battle, so the accuracy numbers below are an optimistic upper
bound, not a claim about the real pipeline's eventual accuracy.

Reports, per field, coverage (share of the 177 gold rows where a number was extracted) and the
share within 1.5x/2x/3x of the gold value, using log error: a field counts as "within Nx" iff
abs(log(extracted / gold)) <= log(N).

Wikitext is cached at data/raw/eval_ingest_cache.json (gitignored) so reruns during development
don't re-hit the network. Delete that file (or pass --no-cache) to force a fresh fetch.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.records import load_battles  # noqa: E402
from war.scrape import fetch_wikitext_batch, parse_military_infobox  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
CACHE_PATH = REPO_ROOT / "data" / "raw" / "eval_ingest_cache.json"

FACTORS = (1.5, 2.0, 3.0)

# Fields this script scores, and which raw infobox field feeds each orientation (1 = combatant1
# side, 2 = combatant2 side).
STRENGTH_FIELDS = ("own_troop_strength", "enemy_troop_strength")
CASUALTY_FIELDS = ("own_casualties", "enemy_casualties")
ALL_FIELDS = STRENGTH_FIELDS + CASUALTY_FIELDS

_BRACKET_RE = re.compile(r"\[[^\]]*\]")
_NUMBER_RE = re.compile(
    r"(?:c\.|ca\.|~|about\s+)?\s*([\d,]*\d(?:\.\d+)?)\s*(million|mil\b|m\b|thousand|k\b)?",
    re.IGNORECASE,
)
_UNIT_MULTIPLIER = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "mil": 1_000_000,
    "million": 1_000_000,
}


def naive_extract_number(text: str) -> int | None:
    """Best-effort "first number" baseline. See module docstring: not the real extractor.

    Returns None for qualitative-only text ("Heavy", "Unknown", "") with no digits at all.
    """
    if not text:
        return None
    cleaned = _BRACKET_RE.sub("", text)
    match = _NUMBER_RE.search(cleaned)
    if not match:
        return None
    digits, unit = match.group(1), match.group(2)
    value = float(digits.replace(",", ""))
    if unit:
        value *= _UNIT_MULTIPLIER[unit.lower()]
    return round(value)


def _load_cache() -> dict[str, str]:
    if CACHE_PATH.exists():
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    return {}


def _save_cache(cache: dict[str, str]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")


def fetch_all_wikitext(titles: list[str], use_cache: bool = True) -> dict[str, str]:
    """Fetch wikitext for every title, filling in from cache first. Network calls for misses."""
    cache = _load_cache() if use_cache else {}
    missing = [title for title in titles if title not in cache]
    if missing:
        fetched = fetch_wikitext_batch(missing)
        cache.update(fetched)
        if use_cache:
            _save_cache(cache)
    return cache


def _orientation_error(
    gold_own: int, gold_enemy: int, side1: int | None, side2: int | None
) -> float:
    """Total abs log-error for assigning side1->own, side2->enemy. inf if nothing comparable."""
    total = 0.0
    comparable = False
    for gold_value, extracted in ((gold_own, side1), (gold_enemy, side2)):
        if extracted is None or extracted <= 0 or gold_value <= 0:
            continue
        total += abs(math.log(extracted / gold_value))
        comparable = True
    return total if comparable else math.inf


def extract_for_battle(fields: dict[str, str], gold_own_strength: int, gold_enemy_strength: int):
    """Return {field_name: extracted_value_or_None} for one battle's four scored fields.

    Orientation (which raw side is "own") is chosen once per battle from the strength fields
    (the only pair both sides of the gold set always have), then reused for casualties.
    """
    s1 = naive_extract_number(fields.get("strength1", ""))
    s2 = naive_extract_number(fields.get("strength2", ""))
    c1 = naive_extract_number(fields.get("casualties1", ""))
    c2 = naive_extract_number(fields.get("casualties2", ""))

    forward_error = _orientation_error(gold_own_strength, gold_enemy_strength, s1, s2)
    reverse_error = _orientation_error(gold_own_strength, gold_enemy_strength, s2, s1)
    own_strength, enemy_strength = (s1, s2) if forward_error <= reverse_error else (s2, s1)
    own_casualties, enemy_casualties = (c1, c2) if forward_error <= reverse_error else (c2, c1)

    return {
        "own_troop_strength": own_strength,
        "enemy_troop_strength": enemy_strength,
        "own_casualties": own_casualties,
        "enemy_casualties": enemy_casualties,
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
        fields = parse_military_infobox(wikitext)
        extracted = extract_for_battle(
            fields, battle.own_troop_strength, battle.enemy_troop_strength
        )
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
