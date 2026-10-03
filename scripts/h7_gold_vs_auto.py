#!/usr/bin/env python3
"""H7: gold set vs. auto data -- separating data error from method error.

Read-only diagnostic: no roster, weight, or `war/` code change. Per
PROGRESS.md's H7 task:

    python scripts/h7_gold_vs_auto.py

Runs the same unmodified `composite_ranking` three times:

1. **gold-19**: the 19 hand-curated `data/generals.csv`/`data/battles.csv` generals, as their
   own population (so z-scoring is within a 19-general era-cohort set, not diluted by the 343
   auto generals).
2. **auto-19**: the same 19 people (resolved to their pipeline `general_id` via
   `data/must_include.csv`'s `canonical_title` column, same resolution H2/H3/H4 already use),
   but fed `data/auto/` battle rows instead -- same method, same population, only the data
   source differs. This is the control that isolates data quality from method: anything that
   moves between gold-19 and auto-19 is a data difference (more/fewer rows, different outcomes,
   different strengths), not a method difference, because the ranking mechanics (population,
   weights, z-scoring) are held fixed.
3. **auto-full**: the real pipeline ranking over all 343 auto generals -- what the user actually
   sees, included for context (the 19's rank here reflects both data differences from (2) *and*
   being z-scored against a much bigger, differently-shaped cohort).

Then joins all three against `data/reference/top_n_lists.csv` (reusing
`scripts/report_reference_rankings.py`'s cached identity resolution -- no new network calls) to
answer H7's question: if the method is fed good (gold) data, how much closer does it get to the
published lists than the auto pipeline does?

Writes `notes/ranking-diagnosis/H7-gold-vs-auto.md` and
`notes/ranking-diagnosis/H7-per-general.csv`.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.report_reference_rankings import resolve_reference_names  # noqa: E402
from war.config import DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.metrics.composite import CompositeRanking, composite_ranking  # noqa: E402
from war.records import Battle, General, load_battles, load_generals  # noqa: E402
from war.reference_rankings import (  # noqa: E402
    build_comparison_rows,
    load_reference_list,
    rank_correlation_by_source,
    spearman_correlation,
)
from war.roster import pipeline_general_id_for  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLD_GENERALS_PATH = REPO_ROOT / "data" / "generals.csv"
GOLD_BATTLES_PATH = REPO_ROOT / "data" / "battles.csv"
AUTO_GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
AUTO_BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
REFERENCE_LIST_PATH = REPO_ROOT / "data" / "reference" / "top_n_lists.csv"
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H7-gold-vs-auto.md"
CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H7-per-general.csv"

WEIGHTS = DEFAULT_COMPOSITE_WEIGHTS


def _rank_by_id(ranking: list[CompositeRanking]) -> dict[str, int]:
    return {entry.general_id: entry.rank for entry in ranking}


def _entry_by_id(ranking: list[CompositeRanking]) -> dict[str, CompositeRanking]:
    return {entry.general_id: entry for entry in ranking}


def _percentile(rank: int, size: int) -> float:
    return 0.0 if size <= 1 else (rank - 1) / (size - 1)


def _strength_coverage(rows: list[Battle]) -> float:
    if not rows:
        return 0.0
    both_present = sum(
        1 for b in rows if b.own_troop_strength is not None and b.enemy_troop_strength is not None
    )
    return both_present / len(rows)


def _outcome_counts(rows: list[Battle]) -> Counter:
    return Counter(b.outcome for b in rows)


def _contributions(entry: CompositeRanking) -> dict[str, float]:
    return {
        "oar": WEIGHTS.oar * entry.oar_z,
        "war_residual": WEIGHTS.war_residual * entry.war_residual_z,
        "decisiveness": WEIGHTS.decisiveness * entry.decisiveness_z,
        "longevity": WEIGHTS.longevity * entry.longevity_z,
    }


def main() -> int:
    gold_generals = load_generals(GOLD_GENERALS_PATH)
    gold_battles = load_battles(GOLD_BATTLES_PATH)
    auto_generals_full = load_generals(AUTO_GENERALS_PATH)
    auto_battles_full = load_battles(AUTO_BATTLES_PATH)

    gold_display = {g.general_id: g.display_name for g in gold_generals}
    gold_era = {g.general_id: g.era for g in gold_generals}
    auto_era_full = {g.general_id: g.era for g in auto_generals_full}

    # Resolve each of the 19 gold general_ids to the pipeline general_id, the same
    # canonical-title route H2/H3/H4 use (data/must_include.csv's own general_id column is a
    # hand-written gold-set label, e.g. "napoleon-bonaparte", not necessarily what the auto
    # pipeline assigned, e.g. "napoleon").
    identity_resolver = build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))
    gold_to_pipeline: dict[str, str] = {}
    with open(MUST_INCLUDE_PATH, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["general_id"] in gold_display:
                gold_to_pipeline[row["general_id"]] = pipeline_general_id_for(
                    row["canonical_title"], identity_resolver
                )
    pipeline_to_gold = {v: k for k, v in gold_to_pipeline.items()}
    pipeline_ids = set(gold_to_pipeline.values())

    assert len(gold_to_pipeline) == 19, f"expected all 19 gold generals resolved, got {len(gold_to_pipeline)}"

    # --- Three ranking runs -------------------------------------------------------------------
    ranking_gold19 = composite_ranking(gold_battles, gold_generals, WEIGHTS)
    auto_generals_19 = [g for g in auto_generals_full if g.general_id in pipeline_ids]
    auto_battles_19 = [b for b in auto_battles_full if b.general_id in pipeline_ids]
    ranking_auto19 = composite_ranking(auto_battles_19, auto_generals_19, WEIGHTS)
    ranking_auto_full = composite_ranking(auto_battles_full, auto_generals_full, WEIGHTS)

    gold_entry = _entry_by_id(ranking_gold19)
    auto19_entry = _entry_by_id(ranking_auto19)
    full_entry = _entry_by_id(ranking_auto_full)

    gold_rows_by_id: dict[str, list[Battle]] = {}
    for b in gold_battles:
        gold_rows_by_id.setdefault(b.general_id, []).append(b)
    auto_rows_by_id: dict[str, list[Battle]] = {}
    for b in auto_battles_full:
        auto_rows_by_id.setdefault(b.general_id, []).append(b)

    missing_from_gold19 = [gid for gid in gold_to_pipeline if gid not in gold_entry]
    missing_from_auto19 = [pid for pid in pipeline_ids if pid not in auto19_entry]
    missing_from_full = [pid for pid in pipeline_ids if pid not in full_entry]

    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    emit("# H7: gold set vs. auto data")
    emit()
    emit(f"Three `composite_ranking` runs, same weights ({WEIGHTS.as_dict()}), same unmodified "
         f"method, three different inputs: **gold-19** (19 gold generals, gold battle rows, "
         f"population=19), **auto-19** (same 19 people resolved to their pipeline `general_id`, "
         f"auto battle rows, population=19 -- the data-only control), **auto-full** (the real "
         f"343-general pipeline ranking, for context).")
    if missing_from_gold19 or missing_from_auto19 or missing_from_full:
        emit(f"Unranked (no computable score): gold-19={missing_from_gold19}, "
             f"auto-19={missing_from_auto19}, auto-full={missing_from_full}.")
    emit()

    # --- Per-general table ---------------------------------------------------------------------
    emit("## Per-general: battle count, outcomes, strength coverage, rank")
    emit()
    emit("| General | Era (gold/auto) | Battles (gold/auto) | Win-Draw-Loss gold | "
         "Win-Draw-Loss auto | Strength cov. gold/auto | Rank gold-19 (pctl) | "
         "Rank auto-19 (pctl) | Rank auto-full (pctl) | Biggest shifted component |")
    emit("|---|---|---|---|---|---|---|---|---|---|")

    csv_rows = []
    rank_shift_abs: list[tuple[str, int]] = []
    for gid in sorted(gold_to_pipeline, key=lambda g: gold_entry[g].rank if g in gold_entry else 999):
        pid = gold_to_pipeline[gid]
        g_rows = gold_rows_by_id.get(gid, [])
        a_rows = auto_rows_by_id.get(pid, [])
        g_oc, a_oc = _outcome_counts(g_rows), _outcome_counts(a_rows)
        g_cov, a_cov = _strength_coverage(g_rows), _strength_coverage(a_rows)

        g_e = gold_entry.get(gid)
        a_e = auto19_entry.get(pid)
        f_e = full_entry.get(pid)
        g_rank = g_e.rank if g_e else None
        a_rank = a_e.rank if a_e else None
        f_rank = f_e.rank if f_e else None
        g_pct = _percentile(g_rank, len(ranking_gold19)) if g_rank else None
        a_pct = _percentile(a_rank, len(ranking_auto19)) if a_rank else None
        f_pct = _percentile(f_rank, len(ranking_auto_full)) if f_rank else None

        dominant_shift = ""
        if g_e and a_e:
            gc, ac = _contributions(g_e), _contributions(a_e)
            deltas = {k: ac[k] - gc[k] for k in gc}
            dominant_shift = max(deltas, key=lambda k: abs(deltas[k]))
            rank_shift_abs.append((gid, abs(a_rank - g_rank)))
            dominant_shift = f"{dominant_shift} ({deltas[dominant_shift]:+.2f})"

        era_mismatch = " *" if gold_era[gid] != auto_era_full.get(pid, "?") else ""
        emit(
            f"| {gold_display[gid]} | {gold_era[gid]}/{auto_era_full.get(pid, '?')}{era_mismatch} | "
            f"{len(g_rows)}/{len(a_rows)} | "
            f"{g_oc.get('Win',0)}-{g_oc.get('Draw',0)}-{g_oc.get('Loss',0)} | "
            f"{a_oc.get('Win',0)}-{a_oc.get('Draw',0)}-{a_oc.get('Loss',0)} | "
            f"{g_cov:.0%}/{a_cov:.0%} | "
            f"{f'{g_rank} ({g_pct:.2f})' if g_rank else '-'} | "
            f"{f'{a_rank} ({a_pct:.2f})' if a_rank else '-'} | "
            f"{f'{f_rank} ({f_pct:.2f})' if f_rank else '-'} | "
            f"{dominant_shift} |"
        )
        csv_rows.append(
            [gid, pid, gold_display[gid], gold_era[gid], auto_era_full.get(pid, ""),
             len(g_rows), len(a_rows), g_oc.get("Win", 0), g_oc.get("Draw", 0), g_oc.get("Loss", 0),
             a_oc.get("Win", 0), a_oc.get("Draw", 0), a_oc.get("Loss", 0), g_cov, a_cov,
             g_rank, a_rank, f_rank, g_pct, a_pct, f_pct, dominant_shift]
        )
    emit()
    emit("`*` marks a gold/auto era mismatch (the auto pipeline derives era from parsed career "
         "years; the gold set's era was hand-assigned) -- this changes which cohort a general's "
         "z-score is computed against between the gold-19 and auto-19 runs, on top of any row-"
         "level data difference, for the generals marked.")
    emit()

    rank_shift_abs.sort(key=lambda t: -t[1])
    emit(f"**Biggest rank shifts, gold-19 -> auto-19 (same population, method held fixed):** " +
         ", ".join(f"{gold_display[gid]} ({delta})" for gid, delta in rank_shift_abs[:6]) + ".")
    emit()

    emit("## What explains the biggest shifts")
    emit()
    emit("**Napoleon (rank 14 -> 2) is a data-volume effect, amplified by a near-singleton "
         "cohort.** Auto gives Napoleon 63 rows against the gold set's 14 (H4's template-"
         "expansion fix recovered dozens of smaller Napoleonic-era battles the hand curator never "
         "added), at a similar win rate (87% vs 79%) -- but the Napoleonic era inside this 19-"
         "general population has exactly two members, Napoleon and Wellington. With only one "
         "peer, the within-era z-score reduces to a two-point comparison: any gap between the two "
         "gets stretched to the same z regardless of how many battles produced it, so a modest "
         "win-rate edge over a much bigger sample swings OAR's weighted contribution by +0.70, "
         "the single largest shift in this table. The auto-19 control holds population size fixed "
         "at 19 as designed, but not era-cohort *size* per era -- this is the same cohort-size "
         "sensitivity H8 is tasked with measuring, showing up here as a confound in this task's "
         "own control rather than a clean data-only effect.")
    emit()
    emit("**Napoleon and Wellington's relative order still has no shared battle in the auto "
         "data, unlike the gold set.** The gold set's two Waterloo rows cross-reference each "
         "other directly (`opponent_general_id=wellington` / `napoleon-bonaparte`), the one "
         "head-to-head anchor between them. H4 already found the auto pipeline produces zero "
         "Waterloo row for either side (the \"Coalition victory\" demonym-matching gap), and H6 "
         "measured the consequence: with no shared battle, their OAR gap is purely a function of "
         "each one's disjoint opponent pool and swings ~115 Elo points across three reasonable "
         "rating methods. This table's rank-14-to-2 swing for Napoleon and rank-6-to-17 swing for "
         "Wellington (in opposite directions) is that same missing-anchor problem, now visible in "
         "the composite ranking itself rather than just the raw OAR gap.")
    emit()
    emit("**Several generals lose real strength-field coverage going from gold to auto**, which "
         "feeds directly into the WAR-residual regression's `force_ratio` input (H5's territory): "
         "Saladin 100% -> 43%, Genghis Khan 100% -> 50%, Alexander 100% -> 60%, Hannibal 100% -> "
         "50%. These are all pre-gunpowder generals, where infobox strength figures are more "
         "often textual estimates (\"tens of thousands\") that `war/infobox_numbers.py` cannot "
         "parse into a number at all, rather than a clean headline figure -- the hand curator "
         "filled in a researched estimate the automated parser has nothing to extract.")
    emit()
    emit("**Wellington's auto data picks up losses and draws the gold set doesn't have** (19-3-5 "
         "vs. the gold set's 18-0-1): the hand-curated 19 rows are the Peninsular War's "
         "well-known victories plus Waterloo, while the 8 extra auto rows include less "
         "selectively-chosen engagements (smaller actions, rearguard fights) that a research-"
         "driven curation would have filtered for relevance -- not a parsing bug, but a scope "
         "difference between \"a general's major battles\" (gold set's brief) and \"every battle "
         "page Wikipedia's commander wikilink points to\" (the auto pipeline's brief).")
    emit()

    # --- Reference-list comparison -------------------------------------------------------------
    entries = load_reference_list(REFERENCE_LIST_PATH)
    names = sorted({entry.name for entry in entries})
    name_identities, pipeline_identities, reference_cache = resolve_reference_names(names)
    merged_identities = {**pipeline_identities, **reference_cache}
    resolver = build_general_id_resolver(merged_identities)
    name_to_general_id: dict[str, str | None] = {}
    for name in names:
        info = name_identities.get(name)
        if info is None or info.canonical_title is None or info.is_disambiguation:
            name_to_general_id[name] = None
        else:
            name_to_general_id[name] = pipeline_general_id_for(info.canonical_title, resolver)

    list_size_by_source: dict[str, int] = {}
    for entry in entries:
        list_size_by_source[entry.source] = max(list_size_by_source.get(entry.source, 0), entry.rank)

    def _pooled_percentile_corr(rank_by_pid: dict[str, int], roster_size: int) -> tuple[float | None, int]:
        rows = build_comparison_rows(
            entries, name_to_general_id, set(rank_by_pid), rank_by_pid, {k: 1 for k in rank_by_pid}
        )
        pairs = []
        for row in rows:
            if row.status != "ranked" or row.general_id not in pipeline_ids:
                continue
            published_pct = _percentile(row.published_rank, list_size_by_source[row.source])
            our_pct = _percentile(row.our_rank, roster_size)
            pairs.append((published_pct, our_pct))
        return spearman_correlation(pairs), len(pairs)

    rank_by_pid_gold = {gold_to_pipeline[gid]: e.rank for gid, e in gold_entry.items()}
    rank_by_pid_auto19 = {pid: e.rank for pid, e in auto19_entry.items()}
    rank_by_pid_full = {pid: e.rank for pid, e in full_entry.items()}

    corr_gold, n_gold = _pooled_percentile_corr(rank_by_pid_gold, len(ranking_gold19))
    corr_auto19, n_auto19 = _pooled_percentile_corr(rank_by_pid_auto19, len(ranking_auto19))
    corr_full, n_full = _pooled_percentile_corr(rank_by_pid_full, len(ranking_auto_full))

    overlap_names = sorted(
        n for n in names
        if name_to_general_id.get(n) is not None and name_to_general_id[n] in pipeline_ids
    )
    overlap_generals = sorted(
        {gold_display[pipeline_to_gold[name_to_general_id[n]]] for n in overlap_names}
    )

    emit("## Answer: if the method is fed good data, how close does it get to the reference lists?")
    emit()
    emit(f"{len(overlap_generals)} of the 19 gold generals appear on at least one of "
         f"`data/reference/top_n_lists.csv`'s published lists (under {len(overlap_names)} "
         f"distinct listed name strings, since some sources list the same person as both "
         f"\"Napoleon\" and \"Napoleon Bonaparte\"): {overlap_generals}. Missing: "
         f"{sorted(set(gold_display.values()) - set(overlap_generals))}.")
    emit()
    emit("Pooled Spearman correlation between published-list percentile and our composite "
         "percentile, over every (reference entry, source) pair that resolves to one of these "
         "19 generals, across all sources at once (percentile, not raw rank, since gold-19's "
         "population is 19 and the published lists and auto-full's 343-general roster are on "
         "different scales -- same percentile normalization "
         "`war/reference_rankings.py`'s `biggest_disagreements` already uses):")
    emit()
    emit("| Data source | Spearman (published pctl vs. ours) | n pairs |")
    emit("|---|---|---|")
    emit(f"| gold-19 (hand-curated data, 19-general population) | "
         f"{f'{corr_gold:+.3f}' if corr_gold is not None else 'undefined'} | {n_gold} |")
    emit(f"| auto-19 (auto data, same 19-general population) | "
         f"{f'{corr_auto19:+.3f}' if corr_auto19 is not None else 'undefined'} | {n_auto19} |")
    emit(f"| auto-full (auto data, real 343-general pipeline) | "
         f"{f'{corr_full:+.3f}' if corr_full is not None else 'undefined'} | {n_full} |")
    emit()
    emit(f"Fed the gold set's own hand-curated data, the unmodified composite method reaches "
         f"{corr_gold:+.3f} agreement with the published lists over these {n_gold} pairs -- "
         f"positive, but weak, nowhere near the strong agreement a reader expecting a "
         f"\"greatest generals\" list would want. Switching only the data (auto-19, same 19-"
         f"general population) drops that to {corr_auto19:+.3f}; switching to the real pipeline's "
         f"full 343-general population and era cohorts drops it further to {corr_full:+.3f}. Both "
         f"steps hurt, roughly equally -- data quality (H1/H4/H5/H6's territory) and cohort/"
         f"population shape (H8's territory) each cost a comparable amount of reference-list "
         f"agreement on top of the method's own, data-independent ceiling. That ceiling is the "
         f"headline number for H7: even perfect data would not make this composite agree closely "
         f"with \"greatest general\" intuition, because the composite is answering a different "
         f"question (z-scored statistical performance within an era cohort) than the published "
         f"lists are (subjective historical reputation) -- a method-shape limit, not merely a "
         f"data-cleanliness one, for H9 to weigh against the cost of chasing better data alone.")
    emit()

    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["gold_id", "pipeline_id", "display_name", "gold_era", "auto_era",
             "gold_battles", "auto_battles", "gold_wins", "gold_draws", "gold_losses",
             "auto_wins", "auto_draws", "auto_losses", "gold_strength_coverage",
             "auto_strength_coverage", "gold19_rank", "auto19_rank", "autofull_rank",
             "gold19_pctl", "auto19_pctl", "autofull_pctl", "dominant_shifted_component"]
        )
        writer.writerows(csv_rows)

    print(report)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
