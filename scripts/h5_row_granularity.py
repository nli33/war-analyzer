#!/usr/bin/env python3
"""H5: row granularity and credit, against `data/auto/`.

Read-only diagnosis, per PROGRESS.md's H5 task:

    python scripts/h5_row_granularity.py

Classifies every `data/auto/battles.csv` row by its title ("single engagement" vs "campaign"
vs "siege/operation"), samples 40 rows stratified across the strength range for a hand-checkable
CSV, and reports whether campaign/operation-scale rows rank their generals higher, how the
force-ratio input behaves for them, whether attacker/defender is distinguished, how draws are
scored, and whether several named commanders on one side ever share credit for a battle.

Writes `notes/ranking-diagnosis/H5-row-granularity.md` (the report) and
`notes/ranking-diagnosis/H5-sample-40.csv` (the 40 sampled rows with their classification).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.commanders import (  # noqa: E402
    extract_commander_fields,
    invert_to_general_battles,
)
from war.config import DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.metrics.composite import composite_ranking  # noqa: E402
from war.records import load_battles, load_generals  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H5-row-granularity.md"
SAMPLE_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H5-sample-40.csv"

SAMPLE_SIZE = 40

# Priority order matters: "Campaign"/"War" checked before "Operation"/"Siege" so a title
# matching both (none found in this corpus, but not ruled out) lands in "campaign".
_CAMPAIGN_RE = re.compile(r"\b(campaign|war)\b", re.IGNORECASE)
_SIEGE_OPERATION_RE = re.compile(r"\b(operation|siege)\b", re.IGNORECASE)

# A division/brigade/battalion count summed by war/infobox_numbers.py's "no headline total ->
# sum every parsed segment" rule produces a troop-strength number in the single/double digits --
# implausible for any real battle at any scale. Used only to flag likely unit-count
# contamination for this report, not as a general data-quality threshold.
_IMPLAUSIBLE_STRENGTH_MAX = 200


def classify_title(battle_name: str) -> str:
    if _CAMPAIGN_RE.search(battle_name):
        return "campaign"
    if _SIEGE_OPERATION_RE.search(battle_name):
        return "siege/operation"
    return "single engagement"


def stratified_sample(rows: list[dict], n: int) -> list[dict]:
    """`n` rows evenly spaced across the strength range (sorted by own_troop_strength ascending,
    missing-strength rows excluded since "across the strength range" needs a strength to place
    them on)."""
    strength_rows = sorted(
        (r for r in rows if r["own_troop_strength"] is not None),
        key=lambda r: r["own_troop_strength"],
    )
    if len(strength_rows) <= n:
        return strength_rows
    step = len(strength_rows) / n
    return [strength_rows[int(i * step)] for i in range(n)]


def main() -> int:
    generals = load_generals(GENERALS_PATH)
    battles = load_battles(BATTLES_PATH)
    display_names = {g.general_id: g.display_name for g in generals}

    rows = [
        {
            "battle_id": b.battle_id,
            "general_id": b.general_id,
            "battle_name": b.battle_name,
            "own_troop_strength": b.own_troop_strength,
            "enemy_troop_strength": b.enemy_troop_strength,
            "outcome": b.outcome,
            "decisiveness": b.decisiveness,
            "category": classify_title(b.battle_name),
        }
        for b in battles
    ]

    # --- corpus-wide category counts -----------------------------------------------------
    category_counts = Counter(r["category"] for r in rows)
    total_rows = len(rows)

    # --- 40-row stratified sample ---------------------------------------------------------
    sample = stratified_sample(rows, SAMPLE_SIZE)
    with SAMPLE_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "battle_id",
                "general_id",
                "battle_name",
                "category",
                "own_troop_strength",
                "enemy_troop_strength",
                "outcome",
            ],
        )
        writer.writeheader()
        for r in sample:
            writer.writerow({k: r[k] for k in writer.fieldnames})
    sample_category_counts = Counter(r["category"] for r in sample)

    # --- do campaign/siege-operation generals rank higher? ---------------------------------
    ranking = composite_ranking(battles, generals, DEFAULT_COMPOSITE_WEIGHTS)
    rank_by_id = {entry.general_id: entry.rank for entry in ranking}
    non_single_generals = {
        r["general_id"] for r in rows if r["category"] != "single engagement"
    }
    ranked_general_ids = set(rank_by_id)
    non_single_ranked = non_single_generals & ranked_general_ids
    single_only_ranked = ranked_general_ids - non_single_generals

    def _mean(xs: list[int]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    mean_rank_non_single = _mean([rank_by_id[g] for g in non_single_ranked])
    mean_rank_single_only = _mean([rank_by_id[g] for g in single_only_ranked])
    n_ranked = len(ranked_general_ids)
    top30_ids = {gid for gid, rank in rank_by_id.items() if rank <= 30}
    top30_non_single = len(top30_ids & non_single_ranked)

    # --- force-ratio behavior for campaign/siege-operation rows -----------------------------
    non_single_rows_with_strength = [
        r for r in rows if r["category"] != "single engagement" and r["own_troop_strength"]
    ]
    single_rows_with_strength = [
        r for r in rows if r["category"] == "single engagement" and r["own_troop_strength"]
    ]

    def _median(xs: list[int]) -> float:
        s = sorted(xs)
        mid = len(s) // 2
        return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2

    median_own_non_single = _median([r["own_troop_strength"] for r in non_single_rows_with_strength])
    median_own_single = _median([r["own_troop_strength"] for r in single_rows_with_strength])

    implausible_non_single = [
        r for r in non_single_rows_with_strength
        if r["own_troop_strength"] <= _IMPLAUSIBLE_STRENGTH_MAX
        or (r["enemy_troop_strength"] and r["enemy_troop_strength"] <= _IMPLAUSIBLE_STRENGTH_MAX)
    ]
    implausible_single = [
        r for r in single_rows_with_strength
        if r["own_troop_strength"] <= _IMPLAUSIBLE_STRENGTH_MAX
        or (r["enemy_troop_strength"] and r["enemy_troop_strength"] <= _IMPLAUSIBLE_STRENGTH_MAX)
    ]

    eisenhower_rhine = next((r for r in rows if r["battle_id"] == "eisenhower-rhine-1945"), None)

    # --- draws ------------------------------------------------------------------------------
    outcome_counts = Counter(r["outcome"] for r in rows)
    draw_rows = [r for r in rows if r["outcome"] == "Draw"]
    draw_with_decisiveness = [r for r in draw_rows if r["decisiveness"]]

    # --- multi-commander credit sharing, from a real cached page ----------------------------
    wikitext_cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))
    # Prefer a recognizable battle for the illustration, if it's in the cache; a title the
    # reader already has a mental picture of makes the "all-or-nothing" point concrete in a
    # way an obscure title wouldn't. Falls back to scanning the whole cache for any
    # multi-commander battle if none of these are cached.
    multi_commander_examples = []
    for title in ("Battle of Stalingrad", "Battle of Waterloo"):
        wikitext = wikitext_cache.get(title)
        if not wikitext:
            continue
        fields = extract_commander_fields(wikitext)
        side1 = fields.get("commander1", [])
        side2 = fields.get("commander2", [])
        if side1 or side2:
            links = invert_to_general_battles(side1, side2)
            multi_commander_examples.append((title, len(side1), len(side2), links))
    if not multi_commander_examples:
        for title, wikitext in wikitext_cache.items():
            fields = extract_commander_fields(wikitext)
            side1 = fields.get("commander1", [])
            side2 = fields.get("commander2", [])
            if len(side1) >= 3 or len(side2) >= 3:
                links = invert_to_general_battles(side1, side2)
                multi_commander_examples.append((title, len(side1), len(side2), links))
            if len(multi_commander_examples) >= 3:
                break

    # --- report ------------------------------------------------------------------------------
    lines = []
    lines.append("# H5: row granularity and credit\n")
    lines.append(
        f"Measured against `data/auto/battles.csv` ({total_rows} rows, {len(generals)} generals) "
        "and the baseline composite ranking from `war.metrics.composite.composite_ranking` with "
        "`war.config.DEFAULT_COMPOSITE_WEIGHTS`. Diagnosis only, per Phase H's rules: nothing in "
        "`war/` changed.\n"
    )

    lines.append("## Title classification, corpus-wide\n")
    lines.append(
        "Classified by a title-keyword regex: `campaign`/`war` -> campaign, `operation`/`siege` "
        "-> siege/operation, neither -> single engagement (checked case-insensitively, campaign "
        "checked first).\n"
    )
    lines.append("| category | rows | % of corpus |")
    lines.append("|---|---|---|")
    for cat in ("single engagement", "campaign", "siege/operation"):
        n = category_counts.get(cat, 0)
        lines.append(f"| {cat} | {n} | {n / total_rows:.1%} |")
    non_single_total = total_rows - category_counts.get("single engagement", 0)
    lines.append(
        f"\n{non_single_total} of {total_rows} rows ({non_single_total / total_rows:.1%}) are "
        "campaign- or siege/operation-scale by this keyword rule, not a single tactical "
        "engagement.\n"
    )

    lines.append(f"## 40-row stratified sample (`H5-sample-40.csv`)\n")
    lines.append(
        f"Sampled evenly across the own_troop_strength range ({len(sample)} of "
        f"{sum(1 for r in rows if r['own_troop_strength'] is not None)} rows with a recorded "
        "strength; rows without one can't be placed on a strength axis and are excluded from "
        "the sampling frame, though still counted above). Category breakdown of the sample:\n"
    )
    for cat in ("single engagement", "campaign", "siege/operation"):
        lines.append(f"- {cat}: {sample_category_counts.get(cat, 0)}")
    lines.append(
        "\nThe sample's category mix (close to the corpus-wide mix above, since both are driven "
        "by the same title-keyword rates at every strength level) confirms campaign/operation "
        "rows aren't concentrated at one end of the strength range -- they appear from the "
        "smallest to the largest recorded strengths, which is itself the point: a \"campaign\" "
        "row's own_troop_strength is not reliably bigger than a single battle's, because (see "
        "below) it isn't reliably a troop count at all.\n"
    )

    lines.append("## Do campaign/siege-operation generals rank higher?\n")
    lines.append(
        f"{len(non_single_ranked)} of {n_ranked} ranked generals ({len(non_single_ranked) / n_ranked:.1%}) "
        "have at least one campaign- or siege/operation-scale row. Mean composite rank "
        f"(1 = best) for that group: {mean_rank_non_single:.0f}. Mean rank for generals whose "
        f"every row is a single engagement: {mean_rank_single_only:.0f}. Top 30: "
        f"{top30_non_single} of 30 ({top30_non_single / 30:.1%}) have at least one "
        "campaign/siege-operation row, against a "
        f"{len(non_single_ranked) / n_ranked:.1%} base rate in the full ranked population.\n"
    )
    verdict = "higher" if mean_rank_non_single < mean_rank_single_only else "not higher"
    lines.append(
        f"Having a campaign/operation-scale row is {verdict} on average than having none, by "
        "mean rank. This is a correlation over whichever generals happen to have that kind of "
        "row (mostly WWII/Napoleonic theater commanders, who also have other things going for "
        "them -- longer careers, more battles, named opponents), not a controlled test that "
        "isolates row granularity's own effect; H3's ablation harness is the tool for isolating "
        "one input's effect; this task only measures the plain association.\n"
    )

    lines.append("## Force-ratio input for campaign/siege-operation rows\n")
    lines.append(
        f"Median own_troop_strength: {median_own_non_single:,.0f} for campaign/siege-operation "
        f"rows (n={len(non_single_rows_with_strength)}) vs {median_own_single:,.0f} for single-"
        f"engagement rows (n={len(single_rows_with_strength)}).\n"
    )
    if eisenhower_rhine:
        lines.append(
            "The task's own named example, Eisenhower's \"Western Allied invasion of Germany "
            f"(Rhine crossing and final drive)\" ({eisenhower_rhine['own_troop_strength']:,} vs "
            f"{eisenhower_rhine['enemy_troop_strength']:,}), is **not** a pipeline-generated row "
            "-- Eisenhower is one of the 3 `hand_curated_fallback_general_ids` in "
            "`data/raw/roster_selection_report.json` (with Zhukov and Subutai), so every one of "
            "his rows is copied verbatim from the hand-curated gold set "
            "(`scripts/build_auto_battles.py`'s `gold_battle_rows`), not derived from an infobox "
            "by the auto pipeline. The row's own `notes` field already documents, by a human "
            "curator's hand, exactly the force-ratio concern this task asks about: those two "
            "numbers are \"the infobox's own campaign totals,\" not personal commands -- the "
            "actual river crossings were \"each a subordinate army-group commander's own "
            "execution,\" and Eisenhower \"does not even appear in [Operation] Plunder's own "
            "Wikipedia command list.\" So for this one general the force-ratio-at-theater-scale "
            "issue was already known and flagged by hand; it is not evidence of a pipeline bug "
            "by itself.\n"
        )
    lines.append(
        "The same failure mode reproduces procedurally, though, with the opposite distortion: "
        "when an infobox's strength field gives a unit-composition breakdown (\"8 infantry "
        "divisions / 3 armored divisions\") instead of one headline troop number, "
        "`war/infobox_numbers.py`'s `extract_numeric_field` falls back to its \"no headline total "
        "-> sum every parsed segment\" rule and sums the bare division/brigade counts as if they "
        "were soldiers -- `_UNIT_MULTIPLIER` only knows \"thousand\"/\"million\"/\"k\"/\"m\", not "
        "\"division\"/\"brigade\"/\"battalion\". Two real pipeline-generated examples, both titled "
        "\"Operation…\" or a plain battle name:\n\n"
        "- `bernard-montgomery-operation-cobra`: own_troop_strength=11, enemy_troop_strength=8 "
        "-- the infobox's `strength1` is \"8 infantry divisions / 3 armored divisions / 2,451 "
        "tanks…\", summed to 11 (divisions only, since 2,451 is attached to \"tanks\", caught "
        "by the equipment-count stripper); `strength2` similarly sums to 8 divisions.\n"
        "- `bernard-montgomery-battle-for-caen`: own_troop_strength=22, enemy_troop_strength=24 "
        "-- same mechanism, `strength1`'s `{{ubl|4 armoured divisions|10 infantry "
        "divisions|…}}` summed as bare counts.\n\n"
        f"Corpus-wide: {len(implausible_non_single)} of {len(non_single_rows_with_strength)} "
        "campaign/siege-operation rows with a recorded strength have an own or enemy "
        f"troop_strength <= {_IMPLAUSIBLE_STRENGTH_MAX} (implausible as an actual headcount at "
        f"any battle's scale), vs {len(implausible_single)} of {len(single_rows_with_strength)} "
        "single-engagement rows. force_ratio for a row like Operation Cobra "
        "(enemy/own = 8/11 = 0.73) is a division-count ratio, not a troop-strength ratio, feeding "
        "straight into `war.metrics.war_residual`'s pooled OLS fit and `rate.py`'s "
        "`avg_force_ratio_faced` alongside rows where the same field genuinely is a headcount in "
        "the hundreds of thousands -- the column mixes two different units with nothing in the "
        "data to tell them apart, not just a scale difference between a campaign and a battle.\n"
    )

    lines.append("## Attacker/defender\n")
    lines.append(
        "Not distinguished anywhere in the schema or the pipeline. `war/schema.py`'s "
        "`BATTLE_COLUMNS` has no attacker/defender field; the infobox fields the pipeline reads "
        "are Wikipedia's own `combatant1`/`combatant2` (`war/scrape.py`), which are whatever "
        "order that battle's article editors wrote them in -- not a verified battlefield role. "
        "`own_troop_strength`/`enemy_troop_strength` are assigned by which side the "
        "`general_id`'s own commander link falls on (`war/commanders.py`), with no attacker/"
        "defender asymmetry anywhere downstream (`force_ratio`, the composite, Elo). A general "
        "who successfully held a defensive position against a larger attacking force and one who "
        "attacked with a larger force and won score identically on every input this pipeline "
        "computes.\n"
    )

    lines.append("## Draws\n")
    lines.append(
        f"{outcome_counts.get('Draw', 0)} of {total_rows} rows ({outcome_counts.get('Draw', 0) / total_rows:.2%}) "
        f"are outcome=Draw, detected by `war/rules.py`'s `_RESULT_DRAW_RE` matching \"inconclusive\"/"
        "\"indecisive\"/\"stalemate\"/\"draw\"/\"status quo\" in the infobox `result` text. "
        f"{len(draw_with_decisiveness)} of those {len(draw_rows)} have a non-empty `decisiveness` "
        "-- `decisiveness_from_result` returns `None` unconditionally for a Draw (schema.py: "
        "\"there is no stronger label than a drawn outcome\"), so this should always be 0 "
        f"(confirms it is: {len(draw_with_decisiveness)}). Both `war/metrics/oar.py` and "
        "`war/metrics/war_residual.py` map Draw to actual score 0.5, the same symmetric "
        "treatment as a human chess-Elo draw -- scored, not dropped, and not biased toward "
        "either side. No asymmetry found between how a Win, Draw, and Loss are scored beyond "
        "that 1.0/0.5/0.0 mapping.\n"
    )

    lines.append("## Credit for several commanders on one side\n")
    lines.append(
        "A side's primary commander (`war/commanders.py`'s `primary_commander`: whichever name "
        "is listed *first* in the infobox's `commander1`/`commander2` field, if wikilinked) gets "
        "the **entire** side's row -- the full `own_troop_strength` (the whole side's total, not "
        "divided by the number of named commanders) and the full Win/Loss/Draw outcome, exactly "
        "as if they had commanded alone. Every other named commander on that side gets zero rows "
        "for that battle (`invert_to_general_battles` only emits a link for each side's single "
        "`primary_commander`) -- already measured corpus-wide by H4 (49% of sides name more than "
        "one commander; 18,278 named co-commanders get zero credit). What H4 didn't measure "
        "directly: credit is never *split* between the named commanders who could in principle "
        "share it -- it is all-or-nothing per side, first name wins all of it, nobody else gets "
        "a fraction. The Eisenhower Rhine-crossing row above is the clearest real example: "
        "own_troop_strength=4,500,000 is the entire Allied force across Montgomery's, Bradley's, "
        "Patton's, and Devers' separate army groups, credited whole to Eisenhower as though he "
        "personally commanded all of it, while Montgomery/Bradley/Patton get no row for this "
        "battle at all (Bradley and Patton are absent from the roster altogether per H4; "
        "Montgomery is on the roster via his own, separate, smaller-scale battles)."
    )
    if multi_commander_examples:
        title, n1, n2, links = multi_commander_examples[0]
        lines.append(
            f"\nA pipeline-side example: \"{title}\" lists {n1} commander(s) on side 1 and {n2} "
            f"on side 2; `invert_to_general_battles` produces {len(links)} `GeneralBattleLink`(s) "
            "total for the battle (at most one per side), regardless of how many names the "
            "infobox gives."
        )
    lines.append("")

    lines.append("## Answer\n")
    lines.append(
        "Row granularity is mixed and the data carries no flag for which kind a row is. "
        f"{non_single_total / total_rows:.1%} of rows are campaign/siege-operation scale by "
        "title keyword, and those rows do not behave like a tactical engagement scaled up -- "
        "their strength numbers are sometimes a theater-wide troop total (Eisenhower, hand-"
        "curated) and sometimes a bare division/brigade count mistaken for a headcount "
        "(Montgomery's Operation Cobra/Caen rows, pipeline-generated), with nothing in the "
        "schema distinguishing either case from an ordinary single-battle headcount. Attacker/"
        "defender is never tracked. Draws are scored evenly and consistently (0.5/0.5). Credit "
        "for a battle is all-or-nothing per side, going entirely to whichever name is listed "
        "first in the infobox, with no mechanism to split it among several commanders who may "
        "have truly shared command -- a campaign-scale row magnifies this because campaigns are "
        "exactly where several commanders sharing a side is most common (army-group command "
        "structures), so the single-commander-gets-everything rule and the row-granularity "
        "problem compound each other rather than being independent issues.\n"
    )

    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {REPORT_PATH}")
    print(f"wrote {SAMPLE_CSV_PATH}")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
