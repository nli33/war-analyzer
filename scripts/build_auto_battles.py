#!/usr/bin/env python3
"""C6: full run into data/auto/battles.csv.

    python scripts/build_auto_battles.py

Reuses C4b's cached wikitext crawl (`data/raw/battle_wikitext_cache.json`, resumable — only
titles still missing are fetched) and C4b's selected roster (`data/auto/generals.csv`). For
every candidate battle title in C1's universe, builds 0-2 rows (one per roster general on
either side) with `war.battles_dataset.build_battle_rows`, folding in C5's LLM-resolved fields
(`data/auto/c5_resolved_fields.json`) as a fallback for strength/casualty fields C2's regex
parser couldn't read. Writes `data/auto/battles.csv`, validates it against `war/schema.py`
(`war.validate.validate_file`/`validate_ranges`, plus the general_id foreign-key check
`validate_all` does for the gold set), and logs row counts and per-field null rates.

Does not touch `data/battles.csv`/`data/generals.csv` (the hand-curated gold set) or
`data/auto/generals.csv` (C4b's roster, left as the input here).
"""

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.battles_dataset import build_battle_rows  # noqa: E402
from war.scrape import fetch_wikitext_batch  # noqa: E402
from war.schema import BATTLE_COLUMNS, BATTLE_FIELD_NAMES, GENERAL_COLUMNS  # noqa: E402
from war.validate import validate_file, validate_ranges  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
RESOLVED_FIELDS_PATH = REPO_ROOT / "data" / "auto" / "c5_resolved_fields.json"
OUTPUT_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "c6_report.json"

NULL_RATE_FIELDS = (
    "own_troop_strength",
    "enemy_troop_strength",
    "own_casualties",
    "enemy_casualties",
    "opponent_general_id",
    "decisiveness",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def crawl(titles: list[str]) -> dict[str, str]:
    """Fetch (or reuse cached) wikitext for every candidate title. Resumable, same as C4b."""
    cache = _load_json(WIKITEXT_CACHE_PATH)
    missing = [title for title in titles if title not in cache]
    if missing:
        fetched = fetch_wikitext_batch(missing)
        cache.update(fetched)
        WIKITEXT_CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False))
    return cache


def _unique_battle_id(general_id: str, title: str, used: set[str]) -> str:
    from war.commanders import general_id_from_title

    base = f"{general_id}-{general_id_from_title(title)}"
    battle_id = base
    suffix = 2
    while battle_id in used:
        battle_id = f"{base}-{suffix}"
        suffix += 1
    used.add(battle_id)
    return battle_id


def build_rows(titles: list[str], cache: dict[str, str], roster_ids: set[str], resolved: dict) -> list[dict]:
    used_ids: set[str] = set()
    rows: list[dict] = []
    for title in titles:
        wikitext = cache.get(title)
        if not wikitext:
            continue
        for row in build_battle_rows(title, wikitext, roster_ids, resolved.get(title)):
            battle_id = _unique_battle_id(row["general_id"], row["battle_title"], used_ids)
            csv_row = {"battle_id": battle_id, "battle_name": row["battle_title"]}
            csv_row.update({k: v for k, v in row.items() if k not in ("battle_title", "display_name")})
            rows.append(csv_row)
    return rows


def _format_cell(value) -> str:
    if value is None:
        return ""
    return str(value)


def write_csv(rows: list[dict]) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATTLE_FIELD_NAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _format_cell(row.get(name)) for name in BATTLE_FIELD_NAMES})


def validate_output() -> list[str]:
    errors = validate_file(OUTPUT_PATH, BATTLE_COLUMNS)
    errors += validate_file(GENERALS_PATH, GENERAL_COLUMNS)
    errors += validate_ranges(OUTPUT_PATH)

    known_generals = set(_read_column(GENERALS_PATH, "general_id"))
    with OUTPUT_PATH.open(newline="", encoding="utf-8") as handle:
        for line_number, row in enumerate(csv.DictReader(handle), start=2):
            general_id = row.get("general_id", "").strip()
            if general_id and general_id not in known_generals:
                errors.append(
                    f"battles.csv:{line_number}: general_id {general_id!r} has no row in generals.csv"
                )
    return errors


def null_rate_report(rows: list[dict]) -> dict:
    total = len(rows)
    report = {"total_rows": total}
    for field in NULL_RATE_FIELDS:
        present = sum(1 for row in rows if row.get(field) is not None)
        report[field] = {
            "present": present,
            "null": total - present,
            "coverage": present / total if total else 0.0,
        }
    report["generals_with_rows"] = len({row["general_id"] for row in rows})
    report["outcome_counts"] = dict(Counter(row["outcome"] for row in rows))
    return report


def main() -> int:
    titles = _read_column(BATTLE_UNIVERSE_PATH, "battle_title")
    roster_ids = set(_read_column(GENERALS_PATH, "general_id"))
    resolved = _load_json(RESOLVED_FIELDS_PATH)

    cache = crawl(titles)
    pages_found = sum(1 for title in titles if title in cache)
    print(f"{pages_found}/{len(titles)} battle pages available in wikitext cache")

    rows = build_rows(titles, cache, roster_ids, resolved)
    print(f"{len(rows)} battle rows built for {len(roster_ids)} roster generals")

    write_csv(rows)
    print(f"wrote {OUTPUT_PATH}")

    errors = validate_output()
    if errors:
        for error in errors[:20]:
            print(error)
        print(f"\n{len(errors)} validation error(s)")
        return 1
    print("data/auto/battles.csv is valid")

    report = null_rate_report(rows)
    report["candidate_battle_titles"] = len(titles)
    report["battle_pages_found"] = pages_found
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
