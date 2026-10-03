#!/usr/bin/env python3
"""H4: missing-battles diagnosis.

    python scripts/h4_missing_battles.py

Read-only: reuses the cached wikitext crawl and the regenerated `data/auto/battles.csv`, no
network calls. Three measurements PROGRESS.md's H4 task asks for:

1. Named-case funnel trace: Waterloo (no rows for either side), a sample of Rommel's famous
   battles (only 2 of his usable-strength appearances became rows), and why Patton/Bradley never
   join the roster at all. Reuses `scripts/funnel_analysis.py`'s `classify_title` plus a direct
   look at parsed commander order, so the trace can't drift from what the real pipeline does.
2. Multi-commander credit loss: across every candidate title, how many infobox sides name more
   than one commander, and how many named subordinates/co-commanders get zero credit because
   `war.commanders.primary_commander` only counts the first-listed name per side.
3. Famous-battle probe: for the reference-list generals NOT in `data/must_include.csv` (so the
   check exercises the real auto funnel, not a hand-curated fallback row), whether 1-2 of their
   best-known battles are even a candidate title and whether they produce a row. Probe titles are
   named from general historical knowledge, not a new web search or sub-agent call -- the same
   convention PROGRESS.md's own H4 task text uses when it names Waterloo/Rommel/Patton/Bradley.

Writes `data/raw/h4_report.json`; prints a human-readable summary.
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.funnel_analysis import classify_title  # noqa: E402
from war.commanders import extract_commander_fields  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
AUTO_BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "h4_report.json"

NAMED_CASES = [
    "Battle of Waterloo",
    "Battle of Arras (1940)",
    "Siege of Tobruk",
    "Battle of Gazala",
    "Battle of the Kasserine Pass",
    "Second Battle of El Alamein",
    "Battle for Caen",
    "Battle of the Bulge",
]

# (general_id as the pipeline would assign it -- accented names slug the same way
# `general_id_from_title` does, see H4 report -- display name, probe battle title). Excludes
# Colin Powell and Sun Tzu: neither has one discrete, well-attested personally-commanded battle
# to probe (Powell was JCS Chairman, not a field commander; Sun Tzu's battles are semi-legendary).
FAMOUS_BATTLE_PROBES = [
    ("cyrus-the-great", "Cyrus the Great", "Battle of Thymbra"),
    ("cyrus-the-great", "Cyrus the Great", "Battle of Opis"),
    ("charlemagne", "Charlemagne", "Battle of Roncevaux Pass (824)"),
    ("khalid-ibn-al-walid", "Khalid ibn al-Walid", "Battle of Yarmouk"),
    ("khalid-ibn-al-walid", "Khalid ibn al-Walid", "Battle of Walaja"),
    ("leonidas-i", "Leonidas I", "Battle of Thermopylae"),
    ("themistocles", "Themistocles", "Battle of Salamis"),
    ("joan-of-arc", "Joan of Arc", "Siege of Orléans (1428–1429)"),
    ("joan-of-arc", "Joan of Arc", "Battle of Patay"),
    ("sim-n-bol-var", "Simon Bolivar", "Battle of Boyacá"),
    ("sim-n-bol-var", "Simon Bolivar", "Battle of Carabobo"),
    ("tamerlane", "Tamerlane", "Battle of Ankara"),
    ("v-nguy-n-gi-p", "Vo Nguyen Giap", "Battle of Dien Bien Phu"),
    ("norman-schwarzkopf", "Norman Schwarzkopf", "Battle of Khafji"),
    ("hern-n-cort-s", "Hernan Cortes", "Fall of Tenochtitlan"),
    ("george-s-patton", "George S. Patton", "Battle of the Bulge"),
    ("omar-bradley", "Omar Bradley", "Battle of the Bulge"),
    ("omar-bradley", "Omar Bradley", "Operation Cobra"),
]


def named_case_trace(cache: dict[str, str]) -> list[dict]:
    trace = []
    for title in NAMED_CASES:
        wikitext = cache.get(title)
        result = classify_title(wikitext)
        commander_fields = extract_commander_fields(wikitext) if wikitext else {}
        sides = {
            key: [ref.display_name for ref in commander_fields.get(key, [])]
            for key in ("commander1", "commander2")
        }
        trace.append(
            {
                "title": title,
                "stage": result.stage,
                "reason": result.reason,
                "detail": result.detail,
                "commander1": sides["commander1"],
                "commander2": sides["commander2"],
            }
        )
    return trace


def multi_commander_loss(titles: list[str], cache: dict[str, str]) -> dict:
    sides_with_any = sides_with_multiple = lost_names = 0
    for title in titles:
        wikitext = cache.get(title)
        if not wikitext:
            continue
        commander_fields = extract_commander_fields(wikitext)
        for key in ("commander1", "commander2"):
            side = commander_fields.get(key, [])
            if not side:
                continue
            sides_with_any += 1
            if len(side) > 1:
                sides_with_multiple += 1
                lost_names += len(side) - 1
    return {
        "sides_with_any_named_commander": sides_with_any,
        "sides_with_more_than_one_named_commander": sides_with_multiple,
        "subordinate_or_co_commander_names_credited_to_nobody": lost_names,
    }


def famous_battle_probe(
    candidate_titles: set[str], cache: dict[str, str], auto_rows: list[dict]
) -> dict:
    rows_by_title_general = {(r["battle_name"], r["general_id"]) for r in auto_rows}
    results = []
    for general_id, display_name, title in FAMOUS_BATTLE_PROBES:
        results.append(
            {
                "general_id": general_id,
                "display_name": display_name,
                "title": title,
                "is_candidate": title in candidate_titles,
                "is_cached": title in cache,
                "has_row": (title, general_id) in rows_by_title_general,
            }
        )
    return {
        "probes": results,
        "n_candidate": sum(r["is_candidate"] for r in results),
        "n_cached": sum(r["is_cached"] for r in results),
        "n_row": sum(r["has_row"] for r in results),
        "n_total": len(results),
    }


def main() -> int:
    with BATTLE_UNIVERSE_PATH.open(newline="", encoding="utf-8") as handle:
        titles = [row["battle_title"] for row in csv.DictReader(handle)]
    cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))
    with AUTO_BATTLES_PATH.open(newline="", encoding="utf-8") as handle:
        auto_rows = list(csv.DictReader(handle))

    report = {
        "named_case_trace": named_case_trace(cache),
        "multi_commander_loss": multi_commander_loss(titles, cache),
        "famous_battle_probe": famous_battle_probe(set(titles), cache, auto_rows),
    }

    print("Named-case funnel trace:")
    for case in report["named_case_trace"]:
        print(f"  {case['title']}: stage={case['stage']} reason={case['reason']}")
        print(f"    commander1={case['commander1']}")
        print(f"    commander2={case['commander2']}")

    loss = report["multi_commander_loss"]
    print("\nMulti-commander credit loss (all 8,824 candidate titles):")
    print(f"  sides with >=1 named commander: {loss['sides_with_any_named_commander']}")
    print(f"  sides with >1 named commander: {loss['sides_with_more_than_one_named_commander']}")
    print(f"  names credited to nobody: {loss['subordinate_or_co_commander_names_credited_to_nobody']}")

    probe = report["famous_battle_probe"]
    print(f"\nFamous-battle probe ({probe['n_total']} battles, non-must-include generals):")
    for p in probe["probes"]:
        print(
            f"  {p['title']:<35} {p['display_name']:<20} candidate={p['is_candidate']} "
            f"cached={p['is_cached']} row={p['has_row']}"
        )
    print(f"  {probe['n_candidate']}/{probe['n_total']} are candidate titles")
    print(f"  {probe['n_row']}/{probe['n_total']} produce a row for the named general")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
