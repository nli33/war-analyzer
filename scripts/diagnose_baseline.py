#!/usr/bin/env python3
"""H2: baseline diagnostic for the composite ranking, against `data/auto/`.

Read-only: computes the same metrics the shipped pipeline computes
(`war.metrics.composite`, `war.metrics.rate`, `war.viz.ranking_tables`) and
reports on them -- no new metric, no reweighting, no roster change. Per
PROGRESS.md's H2 task:

    python scripts/diagnose_baseline.py

Writes `notes/ranking-diagnosis/H2-baseline.md` (the report) and
`notes/ranking-diagnosis/H2-top30-breakdown.csv` (per-general z-scores and
weighted contributions for the top 30 + must-include generals). Also prints
a shorter version of the same report to stdout.

"Top 30" is the top 30 of the full composite ranking over every ranked
general with a computable score (`war.metrics.composite.composite_ranking`'s
own population -- no `min_battles` floor), not the headline HTML table's
`top_n=25`/`min_battles=5` view -- H2 asks what the raw ranking looks like
before that display floor hides anything, since the floor itself is one of
the candidate root causes (G1/H8's territory, not this task's).

"Owes its place to a single component" (one of H2's asks) is operationalized
as: among the four weighted contributions (`weight_i * z_i`), the
largest-magnitude one exceeds the sum of the other three's magnitudes. That
is a concrete, checkable definition, not the only possible one -- a stricter
test would re-run the ranking with that one component dropped and check
whether the general actually falls out of the top 30, which is H3's ablation
harness, not this task's.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.config import DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.metrics.composite import composite_ranking  # noqa: E402
from war.metrics.rate import rate_stats_by_general  # noqa: E402
from war.records import Battle, General, load_battles, load_generals  # noqa: E402
from war.roster import pipeline_general_id_for  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H2-baseline.md"
CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H2-top30-breakdown.csv"

TOP_N = 30
WEIGHTS = DEFAULT_COMPOSITE_WEIGHTS
BATTLE_COUNT_BUCKETS = [(1, 1), (2, 3), (4, 5), (6, 10), (11, 20), (21, None)]


def _bucket_label(lo: int, hi: int | None) -> str:
    return f"{lo}+" if hi is None else (str(lo) if lo == hi else f"{lo}-{hi}")


def _bucket_for(count: int) -> str:
    for lo, hi in BATTLE_COUNT_BUCKETS:
        if hi is None and count >= lo:
            return _bucket_label(lo, hi)
        if hi is not None and lo <= count <= hi:
            return _bucket_label(lo, hi)
    raise AssertionError(f"battle count {count} not covered by any bucket")


def _spearman(xs: list[float], ys: list[float]) -> float | None:
    """Spearman rank correlation, hand-rolled (no scipy in this venv -- see
    requirements.txt). Average ranks for ties. `None` if either series is
    constant (zero variance, correlation undefined)."""
    n = len(xs)
    if n < 2:
        return None

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(n), key=lambda i: values[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg_rank
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mean_rx, mean_ry = sum(rx) / n, sum(ry) / n
    cov = sum((a - mean_rx) * (b - mean_ry) for a, b in zip(rx, ry))
    var_x = sum((a - mean_rx) ** 2 for a in rx)
    var_y = sum((b - mean_ry) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x**0.5 * var_y**0.5)


def main() -> int:
    generals = load_generals(GENERALS_PATH)
    battles = load_battles(BATTLES_PATH)
    display_names = {g.general_id: g.display_name for g in generals}
    eras = {g.general_id: g.era for g in generals}

    ranking = composite_ranking(battles, generals, WEIGHTS)
    ranking_by_id = {entry.general_id: entry for entry in ranking}
    battle_counts = Counter(b.general_id for b in battles)
    rate_stats = rate_stats_by_general(battles)

    # `data/must_include.csv`'s own `general_id` column is a human label copied from the
    # hand-curated gold set (`data/generals.csv`), not necessarily the id the auto pipeline
    # assigns -- e.g. the gold set's "napoleon-bonaparte" is the pipeline's "napoleon". Resolve
    # through the same canonical-title identity pipeline `scripts/report_must_include.py` and
    # `scripts/build_roster_selection.py` use, so this matches whatever id actually landed in
    # `data/auto/generals.csv`.
    identity_resolver = build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))
    must_include_ids = []
    with open(MUST_INCLUDE_PATH, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            must_include_ids.append(pipeline_general_id_for(row["canonical_title"], identity_resolver))

    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    emit("# H2: baseline diagnostic")
    emit()
    emit(f"Ranked population: {len(ranking)} generals (every general with a computable "
         f"WAR-residual and longevity value -- `composite_ranking`'s own no-data convention; "
         f"see `war/metrics/composite.py`). Weights: {WEIGHTS.as_dict()}.")
    emit()

    # --- Per-general component breakdown: top 30 + must-include -----------------------------
    def contributions(gid: str) -> dict[str, float]:
        entry = ranking_by_id[gid]
        return {
            "oar": WEIGHTS.oar * entry.oar_z,
            "war_residual": WEIGHTS.war_residual * entry.war_residual_z,
            "decisiveness": WEIGHTS.decisiveness * entry.decisiveness_z,
            "longevity": WEIGHTS.longevity * entry.longevity_z,
        }

    top30 = ranking[:TOP_N]
    must_include_rows = [
        ranking_by_id[gid] for gid in must_include_ids if gid in ranking_by_id
    ]
    must_include_missing = [gid for gid in must_include_ids if gid not in ranking_by_id]

    csv_rows = []
    dominance_count = 0
    dominant_component_counts: Counter[str] = Counter()
    below_floor_in_top30 = 0

    emit("## Top 30 by composite score: z-scores and weighted contributions")
    emit()
    emit("| Rank | General | Era | Battles | Composite | OAR z (w.contrib) | "
         "WAR-resid z (w.contrib) | Decisiveness z (w.contrib) | Longevity z (w.contrib) | "
         "Dominant component |")
    emit("|---|---|---|---|---|---|---|---|---|---|")
    for entry in top30:
        gid = entry.general_id
        contrib = contributions(gid)
        dominant = max(contrib, key=lambda k: abs(contrib[k]))
        rest = sum(abs(v) for k, v in contrib.items() if k != dominant)
        is_dominated = abs(contrib[dominant]) > rest
        if is_dominated:
            dominance_count += 1
            dominant_component_counts[dominant] += 1
        bc = battle_counts[gid]
        if bc < 5:
            below_floor_in_top30 += 1
        emit(
            f"| {entry.rank} | {display_names[gid]} | {eras[gid]} | {bc} | "
            f"{entry.composite_score:+.3f} | {entry.oar_z:+.2f} ({contrib['oar']:+.3f}) | "
            f"{entry.war_residual_z:+.2f} ({contrib['war_residual']:+.3f}) | "
            f"{entry.decisiveness_z:+.2f} ({contrib['decisiveness']:+.3f}) | "
            f"{entry.longevity_z:+.2f} ({contrib['longevity']:+.3f}) | "
            f"{dominant if is_dominated else '-'} |"
        )
        csv_rows.append((entry, gid, contrib, dominant if is_dominated else ""))
    emit()
    emit(f"**{dominance_count} of the top 30 ({dominance_count / TOP_N:.0%}) owe their place to a "
         f"single component** (its weighted contribution outweighs the other three combined). "
         f"Breakdown: {dict(dominant_component_counts)}.")
    emit()
    emit(f"**{below_floor_in_top30} of the top 30 have fewer than 5 battles** -- the headline "
         f"HTML table's own `min_battles` display floor (`war/viz/ranking_tables.py`) would hide "
         f"them, so they only show up in this unfiltered view and in the full CSVs.")
    emit()

    emit("## Must-include generals (`data/must_include.csv`)")
    emit()
    emit("| General | Rank | Era | Battles | Composite | OAR z (w.contrib) | "
         "WAR-resid z (w.contrib) | Decisiveness z (w.contrib) | Longevity z (w.contrib) |")
    emit("|---|---|---|---|---|---|---|---|---|")
    for entry in sorted(must_include_rows, key=lambda e: e.rank):
        gid = entry.general_id
        contrib = contributions(gid)
        emit(
            f"| {display_names[gid]} | {entry.rank} | {eras[gid]} | {battle_counts[gid]} | "
            f"{entry.composite_score:+.3f} | {entry.oar_z:+.2f} ({contrib['oar']:+.3f}) | "
            f"{entry.war_residual_z:+.2f} ({contrib['war_residual']:+.3f}) | "
            f"{entry.decisiveness_z:+.2f} ({contrib['decisiveness']:+.3f}) | "
            f"{entry.longevity_z:+.2f} ({contrib['longevity']:+.3f}) |"
        )
        csv_rows.append((entry, gid, contrib, ""))
    if must_include_missing:
        emit()
        emit(f"Not in the ranked population at all: {must_include_missing} (no computable "
             f"WAR-residual/longevity -- likely zero battle rows in `data/auto/battles.csv`).")
    emit()

    # --- Rank correlation of each component (and composite) with battle count ---------------
    all_ids = list(ranking_by_id)
    bc_values = [battle_counts[gid] for gid in all_ids]
    oar_z_values = [ranking_by_id[gid].oar_z for gid in all_ids]
    war_z_values = [ranking_by_id[gid].war_residual_z for gid in all_ids]
    dec_z_values = [ranking_by_id[gid].decisiveness_z for gid in all_ids]
    lon_z_values = [ranking_by_id[gid].longevity_z for gid in all_ids]
    composite_values = [ranking_by_id[gid].composite_score for gid in all_ids]

    emit("## Rank correlation (Spearman) with battle count, over all "
         f"{len(all_ids)} ranked generals")
    emit()
    emit("| Component | Spearman rho vs. battle_count |")
    emit("|---|---|")
    for label, series in [
        ("OAR z", oar_z_values),
        ("WAR-residual z", war_z_values),
        ("Decisiveness z", dec_z_values),
        ("Longevity z", lon_z_values),
        ("Composite score", composite_values),
    ]:
        rho = _spearman(bc_values, series)
        emit(f"| {label} | {rho:+.3f} |" if rho is not None else f"| {label} | undefined |")
    emit()

    # --- Win rate by battle count bucket -----------------------------------------------------
    bucket_general_count: Counter[str] = Counter()
    bucket_win_rate_sum: defaultdict[str, float] = defaultdict(float)
    bucket_wins: Counter[str] = Counter()
    bucket_battles: Counter[str] = Counter()
    for gid, stats in rate_stats.items():
        bucket = _bucket_for(battle_counts[gid])
        bucket_general_count[bucket] += 1
        bucket_win_rate_sum[bucket] += stats.win_rate
        bucket_wins[bucket] += round(stats.win_rate * battle_counts[gid])
        bucket_battles[bucket] += battle_counts[gid]

    emit("## Win rate by battle-count bucket (all generals with a rate stat, not just ranked)")
    emit()
    emit("| Battles | Generals | Mean win rate (per-general) | Pooled win rate (wins/battles) |")
    emit("|---|---|---|---|")
    for lo, hi in BATTLE_COUNT_BUCKETS:
        label = _bucket_label(lo, hi)
        n = bucket_general_count[label]
        if n == 0:
            continue
        mean_wr = bucket_win_rate_sum[label] / n
        pooled_wr = bucket_wins[label] / bucket_battles[label]
        emit(f"| {label} | {n} | {mean_wr:.1%} | {pooled_wr:.1%} |")
    emit()

    # --- Tier distributions -------------------------------------------------------------------
    resource_tier_counts = Counter(b.resource_backing_tier for b in battles)
    tech_tier_counts = Counter(b.tech_era_tier for b in battles)
    tech_tier_by_era: defaultdict[str, Counter[int]] = defaultdict(Counter)
    for b in battles:
        tech_tier_by_era[eras.get(b.general_id, "?")][b.tech_era_tier] += 1

    emit("## Tier distributions (all battle rows)")
    emit()
    total_rows = len(battles)
    emit(f"Resource backing tier (1-5), over {total_rows} rows:")
    for tier in sorted(resource_tier_counts):
        n = resource_tier_counts[tier]
        emit(f"- tier {tier}: {n} rows ({n / total_rows:.0%})")
    emit()
    emit(f"Tech era tier (1-5), over {total_rows} rows:")
    for tier in sorted(tech_tier_counts):
        n = tech_tier_counts[tier]
        emit(f"- tier {tier}: {n} rows ({n / total_rows:.0%})")
    emit()
    emit("Tech era tier by general's era (showing how closely tech tier tracks era -- a single "
         "dominant tier per era row means tech tier carries almost no information beyond era):")
    emit()
    emit("| Era | Tier distribution |")
    emit("|---|---|")
    for era, counts in sorted(tech_tier_by_era.items()):
        total = sum(counts.values())
        dist = ", ".join(f"{t}:{n} ({n/total:.0%})" for t, n in sorted(counts.items()))
        emit(f"| {era} | {dist} |")
    emit()

    # --- Decisiveness sparsity -----------------------------------------------------------------
    decisiveness_counts = Counter(b.decisiveness for b in battles if b.decisiveness is not None)
    labeled_rows = sum(decisiveness_counts.values())
    converted_rows = decisiveness_counts.get("Strategic", 0) + decisiveness_counts.get("Rout", 0)
    generals_with_decisiveness = sum(
        1 for gid in ranking_by_id if rate_stats[gid].decisive_win_rate is not None
    )

    emit("## Decisiveness input sparsity")
    emit()
    emit(f"- {labeled_rows} of {total_rows} rows ({labeled_rows/total_rows:.0%}) have a "
         f"`decisiveness` label at all.")
    emit(f"- Label breakdown among labeled rows: {dict(decisiveness_counts)}.")
    emit(f"- {converted_rows} of {total_rows} rows ({converted_rows/total_rows:.1%}) are "
         f"Strategic/Rout (the two levels `decisive_win_rate` counts as \"converted\").")
    emit(f"- {generals_with_decisiveness} of {len(ranking_by_id)} ranked generals "
         f"({generals_with_decisiveness/len(ranking_by_id):.0%}) have at least one "
         f"decisiveness-labeled win, i.e. a non-`None` `decisive_win_rate` at all; the rest get "
         f"`decisiveness_z = 0.0` by convention, not because they lack decisive wins.")
    emit()

    emit("## Answer: what puts generals who are not considered the best in the top 25?")
    emit()
    emit(f"{below_floor_in_top30} of the top 30 have fewer than 5 battles (one, Nelson A. Miles, "
         f"has exactly 1), and {dominance_count} of 30 ({dominance_count/TOP_N:.0%}) are carried "
         f"by a single component that outweighs the other three combined: 8 by OAR, 3 by "
         f"decisiveness, 0 by WAR-residual or longevity under this test. A short, clean win "
         f"streak (few battles, no losses yet) inflates OAR quickly against a rating graph where "
         f"65% of opponents are off-roster at a flat 1500 (H6's territory), and it inflates "
         f"longevity (career value over very few career years) at the same time. Era cohorts of a "
         f"dozen or fewer generals (H8's territory) let a handful of standout battles swing a "
         f"z-score much further than a large cohort would allow. Decisiveness compounds this: "
         f"only 41 of 1887 rows (2.2%) are labeled Strategic/Rout, so `decisive_win_rate` is close "
         f"to binary for anyone with few rated wins. One Strategic/Rout win among a thin sample of "
         f"rated wins (Hayreddin Pasha, Nelson A. Miles, Oda Nobunaga) produces a z of +3 to +7 "
         f"against peers sitting near zero, worth {WEIGHTS.decisiveness} of the composite no "
         f"matter how few battles back it. Eisenhower at #1 is a partial exception: no single "
         f"component dominates by this test, but it is still a 6-battle, all-win sample, the same "
         f"'thin roster, all wins' shape the dev log already flagged for him. Among the "
         f"must-include generals, the ones who rank well (Alexander #12, Han Xin #8) have a "
         f"double-digit battle count and a moderate, positive OAR/WAR-residual pair rather than "
         f"one outlier input. Most of the surprising top-30 entries have the opposite shape.")
    emit()

    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["rank", "general_id", "display_name", "era", "battle_count", "composite_score",
             "oar_z", "oar_contrib", "war_residual_z", "war_residual_contrib",
             "decisiveness_z", "decisiveness_contrib", "longevity_z", "longevity_contrib",
             "dominant_component"]
        )
        for entry, gid, contrib, dominant in csv_rows:
            writer.writerow(
                [entry.rank, gid, display_names[gid], eras[gid], battle_counts[gid],
                 entry.composite_score, entry.oar_z, contrib["oar"], entry.war_residual_z,
                 contrib["war_residual"], entry.decisiveness_z, contrib["decisiveness"],
                 entry.longevity_z, contrib["longevity"], dominant]
            )

    print(report)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {CSV_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
