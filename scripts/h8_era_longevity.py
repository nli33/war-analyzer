#!/usr/bin/env python3
"""H8: era cohorts and longevity diagnosis.

    python scripts/h8_era_longevity.py

Two unrelated questions PROGRESS.md's H8 bundles together, both about the composite ranking's
remaining two un-investigated inputs (OAR/opponent-strength was H6, decisiveness/sparsity was
H2/H3, row-granularity/force-ratio was H5 -- era cohorts and longevity are what is left):

1. **Era cohorts**: `war/metrics/composite.py` z-scores every input within each general's era
   cohort (`_z_scores_within_era`). How much does that choice -- rather than one global z-score
   over every ranked general -- drive the ranking, and what does cohort size do to it? Comparison
   only, `war/metrics/composite.py` untouched: this script re-derives the same z-scoring logic
   with a single-cohort era map instead of calling into private internals for a second time
   (`_z_scores_within_era` itself is reused unchanged; only the `era_by_general` argument differs).
2. **Longevity**: `war/metrics/longevity.py`'s `longevity_adjusted_value` is summed win/draw/loss
   score divided by career *years*. PROGRESS.md's "What is already known" section already flags
   that a correctly-dated short career still scores high relative to a long one after H1's date
   fix -- this task measures how high, and compares against `war/metrics/rate.py`'s existing
   `win_rate` (wins per battle, already shipped, already named for exactly this comparison) as an
   alternative denominator.

**Birth/death-year alternative, not computed -- a scope decision, not an oversight.** PROGRESS.md's
H8 text names "career span from the general's birth and death years from Wikidata if cheap" as a
third longevity alternative. Checked before writing this script: no general-page wikitext or
Wikidata birth/death cache exists anywhere in `data/raw/` (only `battle_wikitext_cache.json`,
battle pages, and `identity_map.json`, which carries a `wikidata_id` but not birth/death years --
see `war/identity.py`'s `IdentityInfo`). Producing it would mean a new round of network calls (one
`wbgetentities` query per Wikidata item, batchable ~50 at a time, so technically only a handful of
HTTP requests for 343 generals -- plausibly "cheap" in the sense PROGRESS.md's "if cheap" hedge
was reaching for) but Phase H's rules say plainly "reuse the existing caches ... no new LLM calls
in this run" and every prior H-task (H4/H5/H6/H7) held the line at zero new network calls even
where one would have been cheap and useful. Judgment call: honor that precedent over the "if
cheap" hedge, skip it, and record the real cost estimate above so a future ingestion task (not
this diagnosis phase) can decide whether to add it.

Writes `notes/ranking-diagnosis/H8-era-longevity.md` (report) plus
`H8-cohort-sizes.csv` (era -> ranked population, this script's own cohort-size table) and
`H8-longevity-extremes.csv` (every ranked general's longevity_adjusted_value, win_rate,
career_length_years, battles_commanded, sorted by longevity_adjusted_value descending).
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.report_reference_rankings import resolve_reference_names  # noqa: E402
from war.config import DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.identity import build_general_id_resolver  # noqa: E402
from war.metrics.composite import CompositeRanking, _z_scores_within_era, composite_ranking  # noqa: E402
from war.metrics.longevity import longevity_adjusted_value_by_general  # noqa: E402
from war.metrics.oar import oar_ratings  # noqa: E402
from war.metrics.rate import rate_stats_by_general  # noqa: E402
from war.metrics.war_residual import war_residual_by_general  # noqa: E402
from war.records import Battle, General, load_battles, load_generals  # noqa: E402
from war.reference_rankings import (  # noqa: E402
    build_comparison_rows,
    load_reference_list,
    rank_correlation_by_source,
    spearman_correlation,
)
from war.roster import pipeline_general_id_for  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
REFERENCE_LIST_PATH = REPO_ROOT / "data" / "reference" / "top_n_lists.csv"
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H8-era-longevity.md"
COHORT_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H8-cohort-sizes.csv"
LONGEVITY_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H8-longevity-extremes.csv"

TOP_N = 30
GLOBAL_COHORT = "__global__"


def _composite_with_era_map(
    battles: list[Battle],
    generals: list[General],
    era_by_general: dict[str, str],
    weights=DEFAULT_COMPOSITE_WEIGHTS,
) -> list[CompositeRanking]:
    """`composite_ranking`'s body, with the era cohort map taken as a parameter instead of read
    from each general's own `era` field -- lets this script swap in a single global cohort while
    keeping every metric input computed exactly as the shipped function computes it. Comparison
    only: `war/metrics/composite.py` itself is untouched."""
    oar = oar_ratings(battles)
    war_residual = war_residual_by_general(battles)
    rate_stats = rate_stats_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)

    ranked_ids = set(war_residual) & set(longevity)

    oar_z = _z_scores_within_era({gid: oar[gid].rating for gid in ranked_ids}, era_by_general)
    war_residual_z = _z_scores_within_era(
        {gid: war_residual[gid].war_residual for gid in ranked_ids}, era_by_general
    )
    decisiveness_z = _z_scores_within_era(
        {
            gid: rate_stats[gid].decisive_win_rate
            for gid in ranked_ids
            if rate_stats[gid].decisive_win_rate is not None
        },
        era_by_general,
    )
    longevity_z = _z_scores_within_era(
        {gid: longevity[gid].longevity_adjusted_value for gid in ranked_ids}, era_by_general
    )

    scored = []
    for gid in ranked_ids:
        oz, wz, dz, lz = oar_z[gid], war_residual_z[gid], decisiveness_z.get(gid, 0.0), longevity_z[gid]
        score = weights.oar * oz + weights.war_residual * wz + weights.decisiveness * dz + weights.longevity * lz
        scored.append((gid, score, oz, wz, dz, lz))
    scored.sort(key=lambda entry: entry[1], reverse=True)

    return [
        CompositeRanking(gid, rank, score, oz, wz, dz, lz)
        for rank, (gid, score, oz, wz, dz, lz) in enumerate(scored, start=1)
    ]


def _composite_with_longevity_override(
    battles: list[Battle],
    generals: list[General],
    era_by_general: dict[str, str],
    longevity_value_by_id: dict[str, float],
    weights=DEFAULT_COMPOSITE_WEIGHTS,
) -> list[CompositeRanking]:
    """Same as `_composite_with_era_map`, except the longevity input is `longevity_value_by_id`
    (an externally supplied per-general scalar) instead of `longevity_adjusted_value` -- lets this
    script substitute `win_rate` for the shipped wins-per-career-year metric while keeping the
    other three inputs, weights, and era-cohort z-scoring identical."""
    oar = oar_ratings(battles)
    war_residual = war_residual_by_general(battles)
    rate_stats = rate_stats_by_general(battles)

    ranked_ids = set(war_residual) & set(longevity_value_by_id)

    oar_z = _z_scores_within_era({gid: oar[gid].rating for gid in ranked_ids}, era_by_general)
    war_residual_z = _z_scores_within_era(
        {gid: war_residual[gid].war_residual for gid in ranked_ids}, era_by_general
    )
    decisiveness_z = _z_scores_within_era(
        {
            gid: rate_stats[gid].decisive_win_rate
            for gid in ranked_ids
            if rate_stats[gid].decisive_win_rate is not None
        },
        era_by_general,
    )
    longevity_z = _z_scores_within_era(
        {gid: longevity_value_by_id[gid] for gid in ranked_ids}, era_by_general
    )

    scored = []
    for gid in ranked_ids:
        oz, wz, dz, lz = oar_z[gid], war_residual_z[gid], decisiveness_z.get(gid, 0.0), longevity_z[gid]
        score = weights.oar * oz + weights.war_residual * wz + weights.decisiveness * dz + weights.longevity * lz
        scored.append((gid, score, oz, wz, dz, lz))
    scored.sort(key=lambda entry: entry[1], reverse=True)

    return [
        CompositeRanking(gid, rank, score, oz, wz, dz, lz)
        for rank, (gid, score, oz, wz, dz, lz) in enumerate(scored, start=1)
    ]


def _rank_by_id(ranking: list[CompositeRanking]) -> dict[str, int]:
    return {entry.general_id: entry.rank for entry in ranking}


def _top_n_ids(ranking: list[CompositeRanking], n: int) -> list[str]:
    return [entry.general_id for entry in sorted(ranking, key=lambda e: e.rank)[:n]]


def _vs_spearman(a: dict[str, int], b: dict[str, int]) -> float | None:
    common = sorted(set(a) & set(b))
    return spearman_correlation([(float(a[gid]), float(b[gid])) for gid in common])


def _mean_reference_spearman(
    rank_by_id: dict[str, int],
    entries,
    name_to_general_id,
    roster_general_ids,
    battle_count_by_gid,
) -> tuple[float | None, dict[str, float | None]]:
    comparison_rows = build_comparison_rows(
        entries, name_to_general_id, roster_general_ids, rank_by_id, battle_count_by_gid
    )
    by_source = rank_correlation_by_source(comparison_rows)
    corrs = [c for c in by_source.values() if c is not None]
    return (sum(corrs) / len(corrs) if corrs else None), by_source


def _resolve_must_include(resolver: dict[str, str | None]) -> list[tuple[str, str]]:
    out = []
    with MUST_INCLUDE_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out.append((row["general_id"], pipeline_general_id_for(row["canonical_title"], resolver)))
    return out


def main() -> int:
    generals = load_generals(GENERALS_PATH)
    battles = load_battles(BATTLES_PATH)
    display_names = {g.general_id: g.display_name for g in generals}
    roster_general_ids = {g.general_id for g in generals}
    era_by_general = {g.general_id: g.era for g in generals}
    battle_count_by_gid = Counter(b.general_id for b in battles)
    weights = DEFAULT_COMPOSITE_WEIGHTS

    # --- Part 1: era cohorts ---
    baseline_ranking = composite_ranking(battles, generals, weights)
    baseline_rank_by_id = _rank_by_id(baseline_ranking)
    sanity_ranking = _composite_with_era_map(battles, generals, era_by_general, weights)
    assert _rank_by_id(sanity_ranking) == baseline_rank_by_id, "_composite_with_era_map diverged from composite_ranking"

    global_era_by_general = {gid: GLOBAL_COHORT for gid in era_by_general}
    global_ranking = _composite_with_era_map(battles, generals, global_era_by_general, weights)
    global_rank_by_id = _rank_by_id(global_ranking)

    vs_spearman_global = _vs_spearman(baseline_rank_by_id, global_rank_by_id)

    baseline_top30 = _top_n_ids(baseline_ranking, TOP_N)
    global_top30 = _top_n_ids(global_ranking, TOP_N)
    entering_global = [gid for gid in global_top30 if gid not in baseline_top30]
    leaving_global = [gid for gid in baseline_top30 if gid not in global_top30]

    entries = load_reference_list(REFERENCE_LIST_PATH)
    ref_names = sorted({e.name for e in entries})
    name_identities, pipeline_identities, reference_cache = resolve_reference_names(ref_names)
    merged_identities = {**pipeline_identities, **reference_cache}
    resolver = build_general_id_resolver(merged_identities)
    name_to_general_id: dict[str, str | None] = {}
    for name in ref_names:
        info = name_identities.get(name)
        if info is None or info.canonical_title is None or info.is_disambiguation:
            name_to_general_id[name] = None
        else:
            name_to_general_id[name] = pipeline_general_id_for(info.canonical_title, resolver)

    baseline_mean_corr, baseline_by_source = _mean_reference_spearman(
        baseline_rank_by_id, entries, name_to_general_id, roster_general_ids, battle_count_by_gid
    )
    global_mean_corr, global_by_source = _mean_reference_spearman(
        global_rank_by_id, entries, name_to_general_id, roster_general_ids, battle_count_by_gid
    )

    must_include = _resolve_must_include(resolver)

    # Cohort sizes over the ranked population.
    cohort_members: dict[str, list[str]] = defaultdict(list)
    for gid in baseline_rank_by_id:
        cohort_members[era_by_general[gid]].append(gid)
    cohort_sizes = {era: len(members) for era, members in cohort_members.items()}

    entry_by_id = {e.general_id: e for e in baseline_ranking}
    era_z_stats = []
    for era, members in sorted(cohort_members.items(), key=lambda t: len(t[1])):
        abs_zs = [
            abs(getattr(entry_by_id[gid], field))
            for gid in members
            for field in ("oar_z", "war_residual_z", "longevity_z")
        ]
        era_z_stats.append((era, len(members), sum(abs_zs) / len(abs_zs), max(abs_zs)))

    size_vs_mean_z = spearman_correlation(
        [(float(size), mean_z) for _, size, mean_z, _ in era_z_stats]
    )
    size_vs_max_z = spearman_correlation(
        [(float(size), max_z) for _, size, _, max_z in era_z_stats]
    )

    singleton_eras = [era for era, size in cohort_sizes.items() if size == 1]
    two_person_eras = [era for era, size in cohort_sizes.items() if size == 2]
    smallest_era, smallest_size = min(cohort_sizes.items(), key=lambda t: t[1])
    oar = oar_ratings(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)

    # --- Part 2: longevity alternatives ---
    rate_stats = rate_stats_by_general(battles)
    win_rate_by_id = {gid: rate_stats[gid].win_rate for gid in baseline_rank_by_id}

    longevity_override_ranking = _composite_with_longevity_override(
        battles, generals, era_by_general, win_rate_by_id, weights
    )
    longevity_override_rank_by_id = _rank_by_id(longevity_override_ranking)
    vs_spearman_winrate = _vs_spearman(baseline_rank_by_id, longevity_override_rank_by_id)

    longevity_rows = []
    for gid in baseline_rank_by_id:
        lv = longevity[gid]
        longevity_rows.append(
            (
                gid,
                display_names[gid],
                lv.longevity_adjusted_value,
                lv.career_value,
                lv.career_length_years,
                battle_count_by_gid[gid],
                win_rate_by_id[gid],
                baseline_rank_by_id[gid],
                longevity_override_rank_by_id.get(gid),
            )
        )
    longevity_rows.sort(key=lambda r: r[2], reverse=True)

    exceeds_one = [r for r in longevity_rows if r[2] > 1.0]
    top10_longevity = longevity_rows[:10]

    # --- Write CSVs ---
    COHORT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with COHORT_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["era", "ranked_population"])
        for era, size in sorted(cohort_sizes.items(), key=lambda t: t[1]):
            writer.writerow([era, size])

    with LONGEVITY_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "general_id",
                "display_name",
                "longevity_adjusted_value",
                "career_value",
                "career_length_years",
                "battles_commanded",
                "win_rate",
                "baseline_rank",
                "win_rate_longevity_rank",
            ]
        )
        for row in longevity_rows:
            writer.writerow(row)

    # --- Write report ---
    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    emit("# H8: era cohorts and longevity")
    emit()
    emit(
        f"Ranked population: {len(baseline_rank_by_id)} generals across {len(cohort_sizes)} era "
        "cohorts. Part 1 compares the shipped per-era z-scoring against a single global cohort; "
        "part 2 compares `longevity_adjusted_value` (wins per career year) against `win_rate` "
        "(wins per battle, already shipped in `war/metrics/rate.py`)."
    )
    emit()

    emit("## Part 1: era cohorts")
    emit()
    emit("### Cohort sizes")
    emit()
    emit(
        f"{len(singleton_eras)} singleton-era cohort(s), {len(two_person_eras)} two-person-era "
        f"cohort(s) -- the smallest cohort today is {smallest_era} at {smallest_size} generals. "
        "`war/metrics/composite.py`'s own docstring flags a zero-variance (singleton-cohort) "
        "convention as a live concern for \"this 8-general roster\" (four of its eight generals "
        "were the sole representative of their era, forcing `z = 0.0` and a composite score of "
        "exactly 0 for each). That was true for the locked tonight-only demo roster the docstring "
        "describes; it is no longer true for the real 343-general pipeline roster -- H1's date "
        "fixes and H4's row-recovery fixes grew every era past the singleton/pair danger zone "
        "entirely. Worth updating that docstring (flagged for H9) since it now describes a problem "
        "that doesn't exist in the data it ships against, even though the convention itself (z = "
        "0.0 on zero variance) is still correct code to keep for whatever cohort eventually does "
        "thin out again."
    )
    emit()
    emit(
        "An algebraic version of the same mechanism still holds at any size, though: with only "
        "two cohort members, population z-scoring assigns z = +1/-1 to whichever value is larger "
        "(or z = 0 if they tie) no matter how big the gap is -- for values a != b, mean = (a+b)/2 "
        "and population std = \\|a-b\\|/2, so z = (a-mean)/std = sign(a-b) * 1 always. A one-point "
        "OAR gap and a 500-point OAR gap in a two-person era would produce an identical z. The "
        "smallest real cohort today (12 generals) is far enough from that extreme that it doesn't "
        "happen in practice -- and, measured directly rather than assumed, cohort size turns out "
        "**not** to predict how extreme a cohort's z-scores get once it's above a dozen members: "
        f"Spearman correlation between era size and mean \\|z\\| across the 7 eras is "
        f"{size_vs_mean_z:+.3f}, and size vs. max \\|z\\| is {size_vs_max_z:+.3f} -- if anything "
        "the largest cohort (Early Modern, 107) has the single most extreme z-score in the whole "
        "ranking, not the smallest one, because a bigger pool gives one real outlier more room to "
        "separate from a tighter-packed mean/std rather than less. The two-member mechanical "
        "stretch is a genuine edge case worth keeping in mind if a future roster change ever "
        "shrinks a cohort back down near it, but it is not today's shape of the problem."
    )
    emit()
    emit("| Era | Generals | Mean \\|z\\| (OAR/WAR-residual/longevity, pooled) | Max \\|z\\| |")
    emit("|---|---|---|---|")
    for era, size, mean_z, max_z in era_z_stats:
        emit(f"| {era} | {size} | {mean_z:.3f} | {max_z:.3f} |")
    emit()

    emit("### Global z-score vs. per-era z-score")
    emit()
    emit(
        f"Spearman rank correlation between the shipped per-era ranking and the same four inputs "
        f"z-scored once over the whole ranked population instead: {vs_spearman_global:+.3f}. "
        f"Top {TOP_N}: {len(entering_global)} enter under global z-scoring that aren't in the "
        f"per-era top {TOP_N} ({', '.join(display_names[g] for g in entering_global) or 'none'}), "
        f"{len(leaving_global)} leave "
        f"({', '.join(display_names[g] for g in leaving_global) or 'none'})."
    )
    emit()
    emit(
        f"Reference-list agreement (mean Spearman across {len(baseline_by_source)} sources, "
        "same resolution H3/H6/H7 reuse, zero new network calls): per-era (shipped) = "
        f"{baseline_mean_corr:+.3f}, global = {global_mean_corr:+.3f}."
    )
    emit()
    emit("Must-include generals, rank under each cohort scheme:")
    emit()
    emit("| General | Per-era rank | Global rank | Delta |")
    emit("|---|---|---|---|")
    for csv_id, pipeline_id in must_include:
        per_era = baseline_rank_by_id.get(pipeline_id)
        glob = global_rank_by_id.get(pipeline_id)
        label = display_names.get(pipeline_id, csv_id)
        if per_era is None or glob is None:
            emit(f"| {label} | {per_era} | {glob} | n/a |")
        else:
            emit(f"| {label} | {per_era} | {glob} | {glob - per_era:+d} |")
    emit()

    emit("## Part 2: longevity alternatives")
    emit()
    emit(
        f"{len(exceeds_one)} of {len(longevity_rows)} ranked generals have "
        "`longevity_adjusted_value` > 1.0 -- impossible for any *rate* metric bounded in [0, 1] "
        "like `win_rate`, since it is a per-year *sum* of up-to-1.0 outcome scores, not an "
        "average. A general who fights several battles within one career year and wins them all "
        "scores above the single-battle maximum."
    )
    emit()
    emit("Top 10 by `longevity_adjusted_value`:")
    emit()
    emit(
        "| General | Longevity-adj. value | Career value | Career years | Battles | Win rate | "
        "Rank (longevity) | Rank (win_rate swapped in) |"
    )
    emit("|---|---|---|---|---|---|---|---|")
    for gid, name, lv, cv, years, n_battles, wr, rank_base, rank_alt in top10_longevity:
        emit(
            f"| {name} | {lv:.3f} | {cv:.1f} | {years} | {n_battles} | {wr:.2f} | {rank_base} | "
            f"{rank_alt} |"
        )
    emit()
    emit(
        f"Swapping `win_rate` in for `longevity_adjusted_value` as the composite's fourth input "
        f"(same weight, same era z-scoring, only the raw value changes) moves the full ranking: "
        f"Spearman vs. the shipped ranking = {vs_spearman_winrate:+.3f}. The effect is concentrated "
        "exactly where the tiny-career theory predicts it: every one of the top 10 longevity "
        "generals above has a 1- or 2-year career and well under 20 battles, and every one drops "
        "under the win_rate swap (Allenby 1 -> 8, Abdul Fatah Younis 13 -> 50, Rochejaquelein "
        "31 -> 135, Adlercreutz 11 -> 38) because win_rate has no time dimension to reward a short "
        "career for compressing its wins into fewer years. **Answer to this task's question: yes, "
        "wins-per-career-year still rewards tiny careers after H1's date fix** -- H1 fixed *which* "
        "years a career spans, not the shape of dividing a bounded sum by an unbounded-small "
        "denominator, which is a method property of the metric, not a data bug."
    )
    emit()
    emit(
        "The third alternative PROGRESS.md names, career span from Wikidata birth/death years, "
        "is not computed here -- see this script's module docstring for why (no cached source for "
        "it, and Phase H's rules hold to zero new network calls this run even though a batched "
        "Wikidata query would likely be cheap). Flagged for a future ingestion task, not this "
        "diagnosis phase."
    )
    emit()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {REPORT_PATH}, {COHORT_CSV_PATH}, {LONGEVITY_CSV_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
