#!/usr/bin/env python3
"""H3: ablation harness for the composite ranking, against `data/auto/`.

    python scripts/ablation_harness.py

Comparison only, per PROGRESS.md: no change to `war/config.py`'s weights or
`war/metrics/composite.py`'s formula. This script recomputes the ranking
under named variants (each component alone, drop-one, equal weights, a
battle-count floor swept at 1/3/5/10/20, and a shrinkage version of the
decisiveness input) and scores each variant two ways:

* Spearman rank correlation against the baseline (`DEFAULT_COMPOSITE_WEIGHTS`)
  ranking, over the generals both rank.
* Spearman rank correlation against each source in
  `data/reference/top_n_lists.csv`, reusing `scripts/report_reference_rankings.py`'s
  own name-to-`general_id` resolution. All 32 reference names are already in
  `data/raw/identity_map.json` or `data/raw/reference_identity_cache.json`
  (checked before writing this script), so this makes zero new network
  calls -- it only recomputes rankings on the current `data/auto/battles.csv`,
  it does not re-resolve identities.

Writes `notes/ranking-diagnosis/H3-ablation.md` (the report) and
`notes/ranking-diagnosis/H3-variant-correlations.csv` (one row per variant:
its Spearman against baseline and against each reference source) plus
`notes/ranking-diagnosis/H3-variant-top20.csv` (top 20 general_ids per
variant). Also prints a shorter version of the report to stdout.

**Why decisiveness gets the shrinkage variant, not another input**: H3's
"average pulled toward 0.5 by a pseudo-count" only describes a metric that
*is* an average/rate in [0, 1] to begin with. Of the composite's four
inputs, only `rate.py`'s `decisive_win_rate` fits (OAR is an Elo-style
rating, not a rate; WAR-residual is an OLS residual; longevity is a
per-year career value) -- and H2's report already flagged it as the
sparsest input (41 of 1887 rows labeled, so `decisive_win_rate` is close to
binary for anyone with few rated wins), which is exactly what a pseudo-count
prior is for. Pseudo-count is 5, reusing `war/viz/ranking_tables.py`'s own
`MIN_BATTLES_FOR_HEADLINE_RANKING` -- the project's already-validated "enough
to compute metrics honestly" bar -- rather than picking an arbitrary number.

**Why the shrinkage variant re-derives z-scoring instead of calling
`composite_ranking`**: that function's z-scoring helper is private
(`war.metrics.composite._z_scores_within_era`) and this script imports it
directly rather than duplicating it, since this is exactly the convention
(population z-score, zero-variance cohort -> z=0.0) whose effect on a
sparse input H3 is testing -- a second, hand-copied implementation could
silently drift from the real one and misreport the comparison.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.report_reference_rankings import resolve_reference_names  # noqa: E402
from war.config import CompositeWeights, DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.identity import build_general_id_resolver  # noqa: E402
from war.metrics.composite import CompositeRanking, _z_scores_within_era, composite_ranking  # noqa: E402
from war.metrics.longevity import longevity_adjusted_value_by_general  # noqa: E402
from war.metrics.oar import oar_ratings  # noqa: E402
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
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H3-ablation.md"
CORRELATIONS_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H3-variant-correlations.csv"
TOP20_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H3-variant-top20.csv"

TOP_N = 20
MIN_BATTLES_FLOORS = (1, 3, 5, 10, 20)
SHRINKAGE_PSEUDO_COUNT = 5  # reuses ranking_tables.MIN_BATTLES_FOR_HEADLINE_RANKING


@dataclass(frozen=True)
class Variant:
    """One ablation variant: a label and the general_id->rank/score it produces."""

    key: str
    label: str
    rank_by_id: dict[str, int]
    score_by_id: dict[str, float]


def _rank_by_id(ranking: list[CompositeRanking]) -> dict[str, int]:
    return {entry.general_id: entry.rank for entry in ranking}


def _score_by_id(ranking: list[CompositeRanking]) -> dict[str, float]:
    return {entry.general_id: entry.composite_score for entry in ranking}


def _weight_variant(key: str, label: str, weights: CompositeWeights, battles, generals) -> Variant:
    ranking = composite_ranking(battles, generals, weights)
    return Variant(key, label, _rank_by_id(ranking), _score_by_id(ranking))


def _min_battles_variant(
    key: str, label: str, floor: int, baseline_ranking: list[CompositeRanking], battle_counts: Counter
) -> Variant:
    """Filter the baseline ranking to generals with `battle_count >= floor`, keeping each
    survivor's original full-population rank/score -- the same "filter what's shown, never
    re-rank" convention `war/viz/ranking_tables.py`'s own `min_battles` display floor uses, so
    this measures the same kind of floor the shipped headline table already applies, just swept
    across more values.
    """
    eligible = [entry for entry in baseline_ranking if battle_counts[entry.general_id] >= floor]
    return Variant(key, label, _rank_by_id(eligible), _score_by_id(eligible))


def _shrunk_decisive_win_rate(
    battles: list[Battle], ranked_ids: set[str], pseudo_count: int
) -> dict[str, float]:
    """Per general_id, `(converted + pseudo_count * 0.5) / (rated_wins + pseudo_count)` --
    `rate.py`'s `decisive_win_rate` numerator/denominator (wins with a `decisiveness` label,
    the Strategic/Rout subset of those), pulled toward the 0.5 prior by `pseudo_count` fake
    observations. Unlike `decisive_win_rate`, this is defined for *every* ranked general, even
    one with zero rated wins (who gets exactly the 0.5 prior) -- the point of the comparison is
    whether giving everyone a real, non-zero-weight value (instead of the current "no data ->
    z defaults to 0.0" convention) changes the ranking.
    """
    rated_wins: Counter[str] = Counter()
    converted: Counter[str] = Counter()
    for battle in battles:
        if battle.general_id not in ranked_ids or battle.outcome != "Win":
            continue
        if battle.decisiveness is None:
            continue
        rated_wins[battle.general_id] += 1
        if battle.decisiveness in ("Strategic", "Rout"):
            converted[battle.general_id] += 1

    return {
        gid: (converted[gid] + pseudo_count * 0.5) / (rated_wins[gid] + pseudo_count)
        for gid in ranked_ids
    }


def _shrinkage_variant(
    key: str,
    label: str,
    battles: list[Battle],
    generals: list[General],
    weights: CompositeWeights,
    pseudo_count: int,
) -> Variant:
    era_by_general = {g.general_id: g.era for g in generals}
    oar = oar_ratings(battles)
    war_residual = war_residual_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)
    ranked_ids = set(war_residual) & set(longevity)

    oar_z = _z_scores_within_era({gid: oar[gid].rating for gid in ranked_ids}, era_by_general)
    war_residual_z = _z_scores_within_era(
        {gid: war_residual[gid].war_residual for gid in ranked_ids}, era_by_general
    )
    longevity_z = _z_scores_within_era(
        {gid: longevity[gid].longevity_adjusted_value for gid in ranked_ids}, era_by_general
    )
    shrunk_rate = _shrunk_decisive_win_rate(battles, ranked_ids, pseudo_count)
    decisiveness_z = _z_scores_within_era(shrunk_rate, era_by_general)

    scored = []
    for gid in ranked_ids:
        score = (
            weights.oar * oar_z[gid]
            + weights.war_residual * war_residual_z[gid]
            + weights.decisiveness * decisiveness_z[gid]
            + weights.longevity * longevity_z[gid]
        )
        scored.append((gid, score))
    scored.sort(key=lambda t: t[1], reverse=True)

    rank_by_id = {gid: rank for rank, (gid, _score) in enumerate(scored, start=1)}
    score_by_id = {gid: score for gid, score in scored}
    return Variant(key, label, rank_by_id, score_by_id)


def _largest_tie_group_size(score_by_id: dict[str, float]) -> int:
    """Size of the biggest group of generals sharing the exact same composite score.

    `composite_ranking`'s own rank assignment (`war/metrics/composite.py`) breaks ties by
    whatever order `set(war_residual) & set(longevity)` iterates in -- Python string-hash order,
    randomized per process (`PYTHONHASHSEED`) unless pinned. A variant with a large tied group
    therefore has an arbitrary, run-to-run-unstable exact rank *within that group* (confirmed by
    re-running `composite_ranking` under several hash seeds while writing this script) -- this
    number flags which variants that applies to, rather than silently reporting a precise-looking
    rank that would not reproduce on a second run. Not a bug this diagnosis-only task fixes (out
    of scope -- `war/metrics/composite.py` is untouched); a candidate for H9's findings report.
    """
    counts = Counter(score_by_id.values())
    return max(counts.values(), default=0)


def _vs_baseline_spearman(variant: Variant, baseline: Variant) -> float | None:
    common = sorted(set(variant.rank_by_id) & set(baseline.rank_by_id))
    pairs = [(float(variant.rank_by_id[gid]), float(baseline.rank_by_id[gid])) for gid in common]
    return spearman_correlation(pairs)


def _top_n_display_names(variant: Variant, display_names: dict[str, str], n: int) -> list[str]:
    ordered = sorted(variant.rank_by_id, key=lambda gid: variant.rank_by_id[gid])
    return [display_names[gid] for gid in ordered[:n]]


def build_variants(
    battles: list[Battle], generals: list[General]
) -> list[Variant]:
    weights = DEFAULT_COMPOSITE_WEIGHTS
    battle_counts = Counter(b.general_id for b in battles)

    baseline = _weight_variant("baseline", "Baseline (default weights)", weights, battles, generals)
    baseline_ranking = composite_ranking(battles, generals, weights)

    variants = [baseline]

    for field in ("oar", "war_residual", "decisiveness", "longevity"):
        alone_weights = CompositeWeights(**{f: (1.0 if f == field else 0.0) for f in weights.as_dict()})
        variants.append(
            _weight_variant(f"{field}_alone", f"{field} alone", alone_weights, battles, generals)
        )

    for field in ("oar", "war_residual", "decisiveness", "longevity"):
        drop_weights = replace(weights, **{field: 0.0})
        variants.append(
            _weight_variant(f"drop_{field}", f"drop {field}", drop_weights, battles, generals)
        )

    equal_weights = CompositeWeights(0.25, 0.25, 0.25, 0.25)
    variants.append(_weight_variant("equal_weights", "equal weights", equal_weights, battles, generals))

    for floor in MIN_BATTLES_FLOORS:
        variants.append(
            _min_battles_variant(
                f"min_battles_{floor}", f"min battles >= {floor}", floor, baseline_ranking, battle_counts
            )
        )

    variants.append(
        _shrinkage_variant(
            "shrinkage_decisiveness",
            f"decisiveness shrunk toward 0.5 (pseudo_count={SHRINKAGE_PSEUDO_COUNT})",
            battles,
            generals,
            weights,
            SHRINKAGE_PSEUDO_COUNT,
        )
    )

    return variants


def main() -> int:
    generals = load_generals(GENERALS_PATH)
    battles = load_battles(BATTLES_PATH)
    display_names = {g.general_id: g.display_name for g in generals}
    roster_general_ids = {g.general_id for g in generals}

    variants = build_variants(battles, generals)
    baseline = variants[0]

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
    sources = sorted(list_size_by_source)

    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    emit("# H3: ablation harness")
    emit()
    emit(f"Ranked population (baseline): {len(baseline.rank_by_id)} generals. "
         f"{len(variants)} variants, compared against the baseline and against "
         f"{len(sources)} reference-list sources ({', '.join(sources)}) from "
         f"`data/reference/top_n_lists.csv`.")
    emit()

    variant_stats: dict[str, dict] = {}
    for variant in variants:
        battle_count_by_gid = Counter(b.general_id for b in battles)
        comparison_rows = build_comparison_rows(
            entries, name_to_general_id, roster_general_ids, variant.rank_by_id, battle_count_by_gid
        )
        source_corr = rank_correlation_by_source(comparison_rows)
        corrs = [c for c in source_corr.values() if c is not None]
        mean_corr = sum(corrs) / len(corrs) if corrs else None
        vs_baseline = _vs_baseline_spearman(variant, baseline) if variant.key != "baseline" else 1.0
        variant_stats[variant.key] = {
            "label": variant.label,
            "population": len(variant.rank_by_id),
            "vs_baseline": vs_baseline,
            "source_corr": source_corr,
            "mean_corr": mean_corr,
            "largest_tie_group": _largest_tie_group_size(variant.score_by_id),
        }

    baseline_mean_corr = variant_stats["baseline"]["mean_corr"]

    emit("## Spearman correlation per variant")
    emit()
    header = (
        "| Variant | Population | vs. baseline rank | "
        + " | ".join(f"vs. {s}" for s in sources)
        + " | mean vs. sources | delta vs. baseline mean | largest tied-score group |"
    )
    emit(header)
    emit("|" + "---|" * (5 + len(sources)))
    for variant in variants:
        stats = variant_stats[variant.key]
        vs_baseline_str = f"{stats['vs_baseline']:+.3f}" if stats["vs_baseline"] is not None else "n/a"
        source_cells = []
        for source in sources:
            corr = stats["source_corr"].get(source)
            source_cells.append(f"{corr:+.3f}" if corr is not None else "n/a")
        mean_str = f"{stats['mean_corr']:+.3f}" if stats["mean_corr"] is not None else "n/a"
        delta = (
            stats["mean_corr"] - baseline_mean_corr
            if stats["mean_corr"] is not None and baseline_mean_corr is not None
            else None
        )
        delta_str = f"{delta:+.3f}" if delta is not None else "n/a"
        emit(
            f"| {stats['label']} | {stats['population']} | {vs_baseline_str} | "
            + " | ".join(source_cells)
            + f" | {mean_str} | {delta_str} | {stats['largest_tie_group']} |"
        )
    emit()
    emit("Every `min battles >= N` variant's \"vs. baseline rank\" is +1.000 by construction: it "
         "filters the baseline ranking down to generals meeting the floor and keeps each "
         "survivor's original full-population rank rather than re-ranking the smaller pool (same "
         "\"filter what's shown, never re-rank\" convention `war/viz/ranking_tables.py`'s own "
         "`min_battles` display floor uses) -- a rank-preserving subset always correlates "
         "perfectly with itself. Its reference-source correlations get noisy at small "
         "populations: `min battles >= 20` is only 7 generals, one source has too few overlapping "
         "entries to compute at all (n/a), and the other three swing between +1.000 and -1.000.")
    emit()
    emit("`decisiveness alone`'s largest tied-score group "
         f"({variant_stats['decisiveness_alone']['largest_tie_group']} of "
         f"{variant_stats['decisiveness_alone']['population']} generals, all stuck at the "
         "\"no rated wins\" default `z=0.0`) means `composite_ranking`'s exact rank order *within* "
         "that group is not reproducible between runs -- it comes from Python's hash-randomized "
         "set iteration order (`war/metrics/composite.py`'s `ranked_ids = set(...) & set(...)`), "
         "confirmed by recomputing this variant under several `PYTHONHASHSEED` values while "
         "writing this script (different runs printed different names in positions past the "
         "handful with real decisiveness data). The `decisiveness alone` and `drop decisiveness` "
         "rows above therefore carry run-to-run noise on top of the sampling noise already "
         "flagged; every other variant's largest tied group is small enough (see the table's last "
         "column) that this does not meaningfully affect its numbers. Not a bug this task fixes "
         "(`war/metrics/composite.py` is untouched) -- flagged for H9.")
    emit()

    non_baseline = [v for v in variants if v.key != "baseline"]
    with_delta = [
        (variant_stats[v.key]["mean_corr"] - baseline_mean_corr, v)
        for v in non_baseline
        if variant_stats[v.key]["mean_corr"] is not None and baseline_mean_corr is not None
    ]
    biggest_improve = max(with_delta, key=lambda t: t[0]) if with_delta else None
    biggest_worsen = min(with_delta, key=lambda t: t[0]) if with_delta else None

    emit("## Which variant moves reference agreement most")
    emit()
    if biggest_improve:
        delta, variant = biggest_improve
        emit(f"- Biggest **improvement** in mean reference-source Spearman: **{variant.label}** "
             f"({delta:+.3f} vs. baseline's {baseline_mean_corr:+.3f}).")
    if biggest_worsen:
        delta, variant = biggest_worsen
        emit(f"- Biggest **worsening**: **{variant.label}** ({delta:+.3f}).")
    emit()

    emit("## Top 20 per variant")
    emit()
    for variant in variants:
        names_top = _top_n_display_names(variant, display_names, TOP_N)
        emit(f"**{variant.label}**: {', '.join(names_top)}")
        emit()

    def _delta_for(key: str) -> float | None:
        mean_corr = variant_stats[key]["mean_corr"]
        return mean_corr - baseline_mean_corr if mean_corr is not None and baseline_mean_corr is not None else None

    alone_deltas = {f: _delta_for(f"{f}_alone") for f in ("oar", "war_residual", "decisiveness", "longevity")}
    drop_deltas = {f: _delta_for(f"drop_{f}") for f in ("oar", "war_residual", "decisiveness", "longevity")}
    equal_delta = _delta_for("equal_weights")
    shrink_delta = _delta_for("shrinkage_decisiveness")

    emit("## Answer: which component is overrated and which is underrated?")
    emit()
    emit(
        f"Dropping each component from the default weights moves mean reference-source Spearman "
        f"by: OAR {drop_deltas['oar']:+.3f}, WAR-residual {drop_deltas['war_residual']:+.3f}, "
        f"decisiveness {drop_deltas['decisiveness']:+.3f}, longevity {drop_deltas['longevity']:+.3f} "
        f"(baseline mean {baseline_mean_corr:+.3f}). A positive delta means the ranking agrees "
        f"with the published lists *more* once that component is removed -- i.e. that component is "
        f"currently overrated relative to its weight; a negative delta means removing it hurts "
        f"agreement, i.e. it is underrated or at least correctly weighted. Each component alone "
        f"(no other input) moves mean correlation by: OAR {alone_deltas['oar']:+.3f}, WAR-residual "
        f"{alone_deltas['war_residual']:+.3f}, decisiveness {alone_deltas['decisiveness']:+.3f}, "
        f"longevity {alone_deltas['longevity']:+.3f}, showing how much reference agreement each "
        f"input can explain in isolation. Equal weights (0.25 each, versus the default "
        f"0.35/0.35/0.15/0.15) moves mean correlation by {equal_delta:+.3f} -- "
        f"{'raising decisiveness/longevity and lowering OAR/WAR-residual helps' if equal_delta and equal_delta > 0 else 'this reweighting does not help'} "
        f"agreement with the published lists. Shrinking decisiveness toward the 0.5 prior "
        f"(pseudo_count={SHRINKAGE_PSEUDO_COUNT}) moves mean correlation by {shrink_delta:+.3f} "
        f"relative to the default-weighted baseline."
    )
    emit()

    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    with open(CORRELATIONS_CSV_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["variant", "label", "population", "vs_baseline"]
            + [f"vs_{s}" for s in sources]
            + ["mean_vs_sources", "delta_vs_baseline_mean", "largest_tied_score_group"]
        )
        for variant in variants:
            stats = variant_stats[variant.key]
            delta = (
                stats["mean_corr"] - baseline_mean_corr
                if stats["mean_corr"] is not None and baseline_mean_corr is not None
                else None
            )
            writer.writerow(
                [variant.key, stats["label"], stats["population"], stats["vs_baseline"]]
                + [stats["source_corr"].get(s) for s in sources]
                + [stats["mean_corr"], delta, stats["largest_tie_group"]]
            )

    with open(TOP20_CSV_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variant", "rank", "general_id", "display_name"])
        for variant in variants:
            ordered = sorted(variant.rank_by_id, key=lambda gid: variant.rank_by_id[gid])[:TOP_N]
            for gid in ordered:
                writer.writerow([variant.key, variant.rank_by_id[gid], gid, display_names[gid]])

    print(report)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {CORRELATIONS_CSV_PATH}")
    print(f"Wrote {TOP20_CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
