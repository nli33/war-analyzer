#!/usr/bin/env python3
"""F1: funnel analysis -- where rows are lost between the 8,824 candidate battle titles
(`data/raw/battle_universe.csv`) and a row `war.battles_dataset.build_battle_rows` would
actually produce.

Read-only: reuses the already-cached wikitext crawl (`data/raw/battle_wikitext_cache.json`,
no network calls) and the same parsing functions the real pipeline calls
(`war.scrape`/`war.commanders`/`war.roster`/`war.infobox_numbers`/`war.rules`), rather than
re-implementing their logic, so the funnel can't drift from what the pipeline actually does.
The one exception is `_outcome_fail_reason`, which duplicates `war.rules.outcome_from_result`'s
internal steps on purpose -- that function only returns the final (Win/Loss/Draw/None) tuple,
not *which* step inside it gave up, and that sub-reason is the whole point of this report.

Classifies every candidate title into exactly one of five drop-out stages, or "produced_row" if
it clears all of them (a roster-independent question -- whether the general who commands a side
is actually selected onto the roster is Phase E's concern, not this one). Usable strength
(PROGRESS.md's fourth funnel stage) doesn't gate row production in the real pipeline -- a row
with a null strength is still written -- so it's reported as a split of `produced_row` rather
than a drop-out stage of its own.

    python scripts/funnel_analysis.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.commanders import extract_commander_fields, primary_commander  # noqa: E402
from war.infobox_numbers import extract_strength_and_casualties  # noqa: E402
from war.roster import extract_year  # noqa: E402
from war.rules import (  # noqa: E402
    _name_in_combatant,
    _POLITY_STOPWORDS,
    _RESULT_DRAW_RE,
    _RESULT_VICTORY_RE,
    _side_match_score,
    _trailing_victory_name,
    _WORD_RE,
    outcome_from_result,
)
from war.scrape import find_infobox_body, parse_military_infobox  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "funnel_report.json"

STAGE_NOT_FETCHED = "not_fetched"
STAGE_NO_INFOBOX = "no_infobox"
STAGE_NO_YEAR = "no_year"
STAGE_NO_COMMANDER = "no_commander"
STAGE_NO_OUTCOME = "no_outcome"
STAGE_PRODUCED = "produced_row"

# Order drop-out is checked in, matching the real gates in
# war.battles_dataset.build_battle_rows / war.roster.battle_appearances.
STAGE_ORDER = (
    STAGE_NOT_FETCHED,
    STAGE_NO_INFOBOX,
    STAGE_NO_YEAR,
    STAGE_NO_COMMANDER,
    STAGE_NO_OUTCOME,
    STAGE_PRODUCED,
)

_EXAMPLES_PER_REASON = 5


@dataclass(frozen=True)
class FunnelResult:
    """One candidate title's outcome: the stage it dropped out at (or `STAGE_PRODUCED`), a
    short machine-readable `reason` tag ("" for `STAGE_PRODUCED`), and a short human-readable
    `detail` snippet to use as a real example in the report."""

    stage: str
    reason: str
    detail: str
    has_usable_strength: bool = False


def _commander_fail_reason(commander_fields: dict) -> tuple[str, str]:
    side1 = commander_fields.get("commander1", [])
    side2 = commander_fields.get("commander2", [])
    if "commander1" not in commander_fields and "commander2" not in commander_fields:
        return "no_commander_fields", ""
    if not side1 and not side2:
        return "parsed_to_empty", ""
    first1 = side1[0].display_name if side1 else None
    first2 = side2[0].display_name if side2 else None
    detail = " / ".join(name for name in (first1, first2) if name)
    return "first_commander_not_wikilinked", detail


def _outcome_fail_reason(
    result_text: str | None, combatant1_text: str | None, combatant2_text: str | None
) -> str:
    """Duplicates `war.rules.outcome_from_result`'s internal steps to report *which* step gave
    up -- see module docstring for why this one function re-implements rather than reuses."""
    if not result_text:
        return "no_result_field"
    if _RESULT_DRAW_RE.search(result_text):
        return "unexpected_draw_match"  # should not happen; outcome_from_result would resolve
    match = _RESULT_VICTORY_RE.search(result_text)
    if not match:
        return "no_victory_or_draw_keyword"
    adjective_words = [
        w for w in _WORD_RE.findall(match.group(1).lower()) if w not in _POLITY_STOPWORDS
    ]
    if not adjective_words:
        name = _trailing_victory_name(result_text)
        if name is None:
            return "victory_keyword_no_adjective"
        in1 = _name_in_combatant(name, combatant1_text)
        in2 = _name_in_combatant(name, combatant2_text)
        if in1 == in2:
            return "ambiguous_trailing_victory_name"
        return "unexpected_resolved"  # should not happen; outcome_from_result would resolve
    score1 = _side_match_score(adjective_words, combatant1_text)
    score2 = _side_match_score(adjective_words, combatant2_text)
    if score1 == score2:
        return "ambiguous_side_match"
    return "unexpected_resolved"  # should not happen; outcome_from_result would resolve


def classify_title(wikitext: str | None) -> FunnelResult:
    """Run one candidate title's wikitext through the same gates
    `war.battles_dataset.build_battle_rows` applies, in order, stopping at the first one that
    fails. `wikitext=None` means the title was never fetched (no cache entry)."""
    if wikitext is None:
        return FunnelResult(STAGE_NOT_FETCHED, "page_not_in_cache", "")

    if find_infobox_body(wikitext) is None:
        return FunnelResult(STAGE_NO_INFOBOX, "no_military_conflict_infobox", "")

    infobox = parse_military_infobox(wikitext)
    year = extract_year(infobox.get("date"))
    if year is None:
        date_text = infobox.get("date")
        reason = "no_date_field" if not date_text else "date_field_unparseable"
        return FunnelResult(STAGE_NO_YEAR, reason, date_text or "")

    commander_fields = extract_commander_fields(wikitext)
    primary1 = primary_commander(commander_fields.get("commander1", []))
    primary2 = primary_commander(commander_fields.get("commander2", []))
    if primary1 is None and primary2 is None:
        reason, detail = _commander_fail_reason(commander_fields)
        return FunnelResult(STAGE_NO_COMMANDER, reason, detail)

    combatant1_text, combatant2_text = infobox.get("combatant1"), infobox.get("combatant2")
    result_text = infobox.get("result")
    outcome1, _ = outcome_from_result(result_text, combatant1_text, combatant2_text)
    if outcome1 is None:
        reason = _outcome_fail_reason(result_text, combatant1_text, combatant2_text)
        return FunnelResult(STAGE_NO_OUTCOME, reason, result_text or "")

    numbers = extract_strength_and_casualties(wikitext)
    s1, s2 = numbers.get("strength1"), numbers.get("strength2")
    has_strength = bool(s1 and s1.point and s1.point > 0 and s2 and s2.point and s2.point > 0)
    return FunnelResult(STAGE_PRODUCED, "", "", has_usable_strength=has_strength)


def run_funnel(titles: list[str], cache: dict[str, str]) -> dict:
    stage_counts: Counter[str] = Counter()
    reason_counts: Counter[tuple[str, str]] = Counter()
    examples: dict[tuple[str, str], list[str]] = defaultdict(list)
    usable_strength_counts: Counter[bool] = Counter()

    for title in titles:
        result = classify_title(cache.get(title))
        stage_counts[result.stage] += 1
        if result.stage == STAGE_PRODUCED:
            usable_strength_counts[result.has_usable_strength] += 1
            continue
        key = (result.stage, result.reason)
        reason_counts[key] += 1
        if len(examples[key]) < _EXAMPLES_PER_REASON:
            examples[key].append(f"{title}: {result.detail}" if result.detail else title)

    total = len(titles)
    survived = total
    funnel_table = []
    for stage in STAGE_ORDER:
        dropped = stage_counts[stage]
        funnel_table.append(
            {
                "stage": stage,
                "dropped_here": dropped,
                "survived_before_this_stage": survived,
            }
        )
        survived -= dropped

    return {
        "total_candidate_titles": total,
        "funnel": funnel_table,
        "produced_row_usable_strength": usable_strength_counts.get(True, 0),
        "produced_row_no_usable_strength": usable_strength_counts.get(False, 0),
        "loss_reasons": [
            {
                "stage": stage,
                "reason": reason,
                "count": count,
                "examples": examples[(stage, reason)],
            }
            for (stage, reason), count in sorted(reason_counts.items(), key=lambda kv: -kv[1])
        ],
    }


def _print_table(report: dict) -> None:
    print(f"{'stage':<16} {'dropped here':>14} {'survived before':>18}")
    for row in report["funnel"]:
        print(f"{row['stage']:<16} {row['dropped_here']:>14} {row['survived_before_this_stage']:>18}")
    produced = report["produced_row_usable_strength"] + report["produced_row_no_usable_strength"]
    print(f"\n{produced} titles would produce at least one battle row.")
    print(
        f"  of those: {report['produced_row_usable_strength']} have usable strength on both "
        f"sides, {report['produced_row_no_usable_strength']} do not."
    )
    print("\nTop loss causes:")
    for entry in report["loss_reasons"][:10]:
        print(f"  {entry['stage']}/{entry['reason']}: {entry['count']}")
        for example in entry["examples"][:3]:
            print(f"      e.g. {example}")


def main() -> int:
    with BATTLE_UNIVERSE_PATH.open(newline="", encoding="utf-8") as handle:
        import csv

        titles = [row["battle_title"] for row in csv.DictReader(handle)]
    cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))

    report = run_funnel(titles, cache)
    _print_table(report)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nwrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
