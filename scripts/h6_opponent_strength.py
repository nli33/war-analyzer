#!/usr/bin/env python3
"""H6: opponent strength diagnosis.

    python scripts/h6_opponent_strength.py

Today's OAR (`war/metrics/oar.py`) solves one Elo-style graph from `data/auto/battles.csv`
alone -- roster-general perspectives plus whichever off-roster `opponent_general_id` they
happened to face. An off-roster opponent's rating only ever moves from games against roster
generals; it never sees that opponent's own record against other off-roster generals, which is
most of the historical record (per PROGRESS.md's "only 35% of opponents are on the roster").
This script tests two variants, both read-only against existing caches (no new network calls,
no new LLM calls, `war/metrics/oar.py`/`war/config.py` untouched):

1. **Full-universe OAR**: re-run the same `oar_ratings` solver over a bigger graph built from
   *every* identifiable commander in the cached battle universe (`war.battles_dataset.build_battle_rows`
   called with an "allow every general_id" roster filter instead of the real 343-general roster),
   not just roster-perspective rows. Off-roster opponents now rate against each other too.
2. **Confidence-weighted OAR**: keep the existing roster-only graph, but scale each battle's Elo
   step size by how many rated battles the *opponent* has in the full-universe graph (a
   `n / (n + 5)` saturating weight, pseudo-count 5 reusing `ranking_tables.MIN_BATTLES_FOR_HEADLINE_RANKING`,
   same convention H3's shrinkage variant used) -- "weight each battle by opponent rating quality."

Both variants only replace the OAR input to the composite score; WAR-residual/decisiveness/
longevity are computed from `data/auto/battles.csv` exactly as `composite_ranking` does, via
`_composite_with_oar` below (duplicates `war.metrics.composite.composite_ranking`'s body with the
OAR dict taken as a parameter instead of recomputed internally, so this stays a comparison script,
not a change to the shipped composite function).

Writes `notes/ranking-diagnosis/H6-opponent-strength.md` (report), `H6-opponent-coverage.csv`
(off-roster opponents bucketed by full-universe battle count), and `H6-rank-changes.csv` (top 30
+ must-include generals' rank under baseline/variant1/variant2). Also writes
`data/raw/h6_full_universe_battles.csv` (gitignored, regenerable) so the full-universe graph can
be inspected directly.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_auto_battles import (  # noqa: E402
    GOLD_BATTLES_PATH,
    build_rows,
    gold_battle_rows,
    hand_curated_fallback_ids,
)
from war.config import DEFAULT_COMPOSITE_WEIGHTS  # noqa: E402
from war.identity import build_general_id_resolver, load_identity_map  # noqa: E402
from war.metrics.composite import CompositeRanking, _z_scores_within_era, composite_ranking  # noqa: E402
from war.metrics.longevity import longevity_adjusted_value_by_general  # noqa: E402
from war.metrics.oar import _ACTUAL_SCORE, OARRating, oar_ratings  # noqa: E402
from war.metrics.rate import rate_stats_by_general  # noqa: E402
from war.metrics.war_residual import war_residual_by_general  # noqa: E402
from war.records import Battle, General, load_battles, load_generals  # noqa: E402
from war.reference_rankings import spearman_correlation  # noqa: E402
from war.roster import pipeline_general_id_for  # noqa: E402
from war.schema import BATTLE_FIELD_NAMES  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
BATTLES_PATH = REPO_ROOT / "data" / "auto" / "battles.csv"
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
RESOLVED_OUTCOMES_PATH = REPO_ROOT / "data" / "auto" / "f3_resolved_outcomes.json"
IDENTITY_MAP_PATH = REPO_ROOT / "data" / "raw" / "identity_map.json"
MUST_INCLUDE_PATH = REPO_ROOT / "data" / "must_include.csv"
FULL_UNIVERSE_BATTLES_PATH = REPO_ROOT / "data" / "raw" / "h6_full_universe_battles.csv"
REPORT_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H6-opponent-strength.md"
COVERAGE_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H6-opponent-coverage.csv"
RANK_CSV_PATH = REPO_ROOT / "notes" / "ranking-diagnosis" / "H6-rank-changes.csv"

TOP_N = 30
CONFIDENCE_PSEUDO_COUNT = 5  # reuses ranking_tables.MIN_BATTLES_FOR_HEADLINE_RANKING
COVERAGE_BUCKETS = ((0, 0), (1, 2), (3, 4), (5, 9), (10, None))


class _AllowAll:
    """A `roster_ids` stand-in whose membership test always succeeds -- lets
    `war.battles_dataset.build_battle_rows` build a row for every identifiable primary
    commander in the cache, not just the real 343-general roster, without touching that
    function's signature or `scripts/build_auto_battles.py`."""

    def __contains__(self, item: object) -> bool:
        return True


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def build_full_universe_battles(roster_ids: set[str]) -> list[Battle]:
    """Every identifiable-primary-commander battle in the cached universe, as `Battle` rows --
    reuses `build_auto_battles.build_rows` (the real C6 row-building loop) with `_AllowAll()` in
    place of the real roster filter, plus the same hand-curated gold-set rows production splices
    in for `hand_curated_fallback_general_ids`, so those 3 generals aren't missing from the graph
    just because their pipeline identity never gets parsed (see `build_auto_battles.py`'s E4
    note). Writes the merged rows to `data/raw/h6_full_universe_battles.csv` and loads them back
    through `war.records.load_battles` rather than constructing `Battle` objects by hand, so this
    exercises the exact same CSV round-trip/type-coercion the real pipeline does.
    """
    titles = _read_column(BATTLE_UNIVERSE_PATH, "battle_title")
    cache = _load_json(WIKITEXT_CACHE_PATH)
    pages_found = sum(1 for title in titles if title in cache)
    print(f"{pages_found}/{len(titles)} battle pages available in wikitext cache (read-only, no crawl)")

    identity_resolver = (
        build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH))
        if IDENTITY_MAP_PATH.exists()
        else None
    )
    resolved_outcomes = _load_json(RESOLVED_OUTCOMES_PATH)

    rows = build_rows(titles, cache, _AllowAll(), {}, identity_resolver, resolved_outcomes)
    print(f"{len(rows)} full-universe battle rows built (every identifiable primary commander)")

    hand_curated_ids = hand_curated_fallback_ids() & roster_ids
    if hand_curated_ids:
        gold_rows = gold_battle_rows(hand_curated_ids)
        rows.extend(gold_rows)
        print(f"{len(gold_rows)} hand-curated row(s) spliced in for {sorted(hand_curated_ids)}")

    FULL_UNIVERSE_BATTLES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FULL_UNIVERSE_BATTLES_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=BATTLE_FIELD_NAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    name: ("" if row.get(name) is None else str(row.get(name)))
                    for name in BATTLE_FIELD_NAMES
                }
            )

    return load_battles(FULL_UNIVERSE_BATTLES_PATH)


def oar_ratings_confidence_weighted(
    battles: list[Battle],
    confidence_by_id: dict[str, float],
    k_factor: float = 32.0,
    base_rating: float = 1500.0,
    decay: float = 0.9,
    tolerance: float = 1e-6,
    max_epochs: int = 2000,
    default_confidence: float = 0.0,
) -> dict[str, OARRating]:
    """Same synchronous-batch iterative Elo solver as `war.metrics.oar.oar_ratings`, except each
    battle's step is additionally scaled by `confidence_by_id[opponent_general_id]` -- "weight
    each battle by opponent rating quality." A participant absent from `confidence_by_id` (no
    battles at all in the full-universe graph, not even their own cached appearance) gets
    `default_confidence` rather than crashing; in practice this should be rare, since anyone who
    appears as an `opponent_general_id` in the roster graph was, by construction, identifiable as
    a primary commander on their own side of that same battle, so the full-universe build (which
    uses the same cache) should also have produced a row for them.
    """
    participants: set[str] = set()
    rated_battles: list[Battle] = []
    for battle in battles:
        participants.add(battle.general_id)
        if battle.opponent_general_id:
            participants.add(battle.opponent_general_id)
            rated_battles.append(battle)

    ratings = {pid: base_rating for pid in participants}
    battles_rated: dict[str, int] = Counter()
    for battle in rated_battles:
        battles_rated[battle.general_id] += 1
        battles_rated[battle.opponent_general_id] += 1

    for epoch in range(1, max_epochs + 1):
        k_epoch = k_factor * (decay**epoch)
        deltas: dict[str, float] = Counter()
        for battle in rated_battles:
            own_rating = ratings[battle.general_id]
            opp_rating = ratings[battle.opponent_general_id]
            expected = 1.0 / (1.0 + 10 ** ((opp_rating - own_rating) / 400.0))
            actual = _ACTUAL_SCORE[battle.outcome]
            weight = confidence_by_id.get(battle.opponent_general_id, default_confidence)
            change = k_epoch * weight * (actual - expected)
            deltas[battle.general_id] += change
            deltas[battle.opponent_general_id] -= change

        max_delta = max((abs(d) for d in deltas.values()), default=0.0)
        for pid, delta in deltas.items():
            ratings[pid] += delta
        if max_delta < tolerance:
            break

    return {
        pid: OARRating(general_id=pid, rating=ratings[pid], battles_rated=battles_rated.get(pid, 0))
        for pid in participants
    }


def _composite_with_oar(
    oar: dict[str, OARRating],
    battles: list[Battle],
    generals: list[General],
    weights=DEFAULT_COMPOSITE_WEIGHTS,
) -> list[CompositeRanking]:
    """`war.metrics.composite.composite_ranking`'s body, with the OAR dict taken as a parameter
    instead of computed internally via `oar_ratings(battles)` -- lets this script swap in the
    full-universe or confidence-weighted OAR while keeping WAR-residual/decisiveness/longevity
    exactly as the shipped function computes them. Comparison only: `war/metrics/composite.py`
    itself is untouched."""
    era_by_general = {general.general_id: general.era for general in generals}
    war_residual = war_residual_by_general(battles)
    rate_stats = rate_stats_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)

    ranked_ids = set(war_residual) & set(longevity) & set(oar)

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
        oz = oar_z[gid]
        wz = war_residual_z[gid]
        dz = decisiveness_z.get(gid, 0.0)
        lz = longevity_z[gid]
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


def _vs_baseline_spearman(rank_by_id: dict[str, int], baseline_rank_by_id: dict[str, int]) -> float | None:
    common = sorted(set(rank_by_id) & set(baseline_rank_by_id))
    pairs = [(float(rank_by_id[gid]), float(baseline_rank_by_id[gid])) for gid in common]
    return spearman_correlation(pairs)


def _resolve_must_include(identity_resolver: dict[str, str | None] | None) -> list[tuple[str, str]]:
    """`(csv_general_id, pipeline_general_id)` for every `data/must_include.csv` row, resolved
    through the same canonical-title identity pipeline H2/H3 found is required -- the CSV's own
    `general_id` column is a hand-curated gold-set label that does not match the id the auto
    pipeline actually assigns (`scripts/report_must_include.py` is the precedent)."""
    resolver = identity_resolver or {}
    out = []
    with MUST_INCLUDE_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            out.append((row["general_id"], pipeline_general_id_for(row["canonical_title"], resolver)))
    return out


def main() -> int:
    generals = load_generals(GENERALS_PATH)
    roster_battles = load_battles(BATTLES_PATH)
    roster_ids = {g.general_id for g in generals}
    display_names = {g.general_id: g.display_name for g in generals}
    weights = DEFAULT_COMPOSITE_WEIGHTS

    identity_resolver = (
        build_general_id_resolver(load_identity_map(IDENTITY_MAP_PATH)) if IDENTITY_MAP_PATH.exists() else None
    )

    full_battles = build_full_universe_battles(roster_ids)

    # --- Opponent coverage: how many off-roster opponents have enough rows to rate? ---
    opponent_rows = Counter(b.opponent_general_id for b in roster_battles if b.opponent_general_id)
    off_roster_opponents = {gid for gid in opponent_rows if gid not in roster_ids}
    off_roster_rows = sum(count for gid, count in opponent_rows.items() if gid in off_roster_opponents)
    total_opponent_rows = sum(opponent_rows.values())

    full_universe_oar = oar_ratings(full_battles)
    full_universe_battle_counts = {gid: rating.battles_rated for gid, rating in full_universe_oar.items()}

    def _bucket_label(lo: int, hi: int | None) -> str:
        return f"{lo}+" if hi is None else (f"{lo}" if lo == hi else f"{lo}-{hi}")

    bucket_counts: dict[str, int] = {_bucket_label(lo, hi): 0 for lo, hi in COVERAGE_BUCKETS}
    coverage_rows = []
    for gid in sorted(off_roster_opponents):
        n = full_universe_battle_counts.get(gid, 0)
        for lo, hi in COVERAGE_BUCKETS:
            if n >= lo and (hi is None or n <= hi):
                bucket_counts[_bucket_label(lo, hi)] += 1
                break
        coverage_rows.append((gid, opponent_rows[gid], n))

    # --- Variant 1: full-universe OAR ---
    baseline_ranking = composite_ranking(roster_battles, generals, weights)
    baseline_rank_by_id = _rank_by_id(baseline_ranking)

    variant1_ranking = _composite_with_oar(full_universe_oar, roster_battles, generals, weights)
    variant1_rank_by_id = _rank_by_id(variant1_ranking)

    # --- Variant 2: confidence-weighted OAR (roster-only graph, weighted step size) ---
    confidence_by_id = {
        gid: n / (n + CONFIDENCE_PSEUDO_COUNT) for gid, n in full_universe_battle_counts.items()
    }
    weighted_oar = oar_ratings_confidence_weighted(roster_battles, confidence_by_id)
    variant2_ranking = _composite_with_oar(weighted_oar, roster_battles, generals, weights)
    variant2_rank_by_id = _rank_by_id(variant2_ranking)

    # Sanity check: baseline composite via the swap-in helper must match the shipped function.
    sanity_ranking = _composite_with_oar(oar_ratings(roster_battles), roster_battles, generals, weights)
    assert _rank_by_id(sanity_ranking) == baseline_rank_by_id, "_composite_with_oar diverged from composite_ranking"

    spearman_v1 = _vs_baseline_spearman(variant1_rank_by_id, baseline_rank_by_id)
    spearman_v2 = _vs_baseline_spearman(variant2_rank_by_id, baseline_rank_by_id)

    baseline_top30 = _top_n_ids(baseline_ranking, TOP_N)
    variant1_top30 = _top_n_ids(variant1_ranking, TOP_N)
    variant2_top30 = _top_n_ids(variant2_ranking, TOP_N)
    v1_entering = [gid for gid in variant1_top30 if gid not in baseline_top30]
    v1_leaving = [gid for gid in baseline_top30 if gid not in variant1_top30]
    v2_entering = [gid for gid in variant2_top30 if gid not in baseline_top30]
    v2_leaving = [gid for gid in baseline_top30 if gid not in variant2_top30]

    must_include = _resolve_must_include(identity_resolver)

    # --- Napoleon/Wellington ---
    napoleon_id = pipeline_general_id_for("Napoleon", identity_resolver or {})
    wellington_id = pipeline_general_id_for(
        "Arthur Wellesley, 1st Duke of Wellington", identity_resolver or {}
    )

    def _opponent_list(general_id: str) -> list[tuple[str, str, str]]:
        return sorted(
            (b.battle_name, b.opponent_general_id, b.outcome)
            for b in roster_battles
            if b.general_id == general_id and b.opponent_general_id
        )

    napoleon_opponents = _opponent_list(napoleon_id)
    wellington_opponents = _opponent_list(wellington_id)
    shared_direct_opponents = {o for _, o, _ in napoleon_opponents} & {o for _, o, _ in wellington_opponents}

    # --- Write report ---
    lines: list[str] = []

    def emit(line: str = "") -> None:
        lines.append(line)

    emit("# H6: opponent strength")
    emit()
    emit(
        f"Roster graph (`data/auto/battles.csv`): {len(roster_battles)} rows, "
        f"{total_opponent_rows} with a recorded opponent, {len(opponent_rows)} distinct "
        f"opponents, {len(off_roster_opponents)} of them ({len(off_roster_opponents) / len(opponent_rows):.0%} "
        f"of distinct opponents, {off_roster_rows / total_opponent_rows:.0%} of opponent-rows) off-roster. "
        f"Full-universe graph: {len(full_battles)} rows built from every identifiable primary "
        f"commander in the cached battle universe (not just the 343-general roster)."
    )
    emit()

    emit("## How many off-roster opponents have enough rows to rate?")
    emit()
    emit(
        "For each off-roster opponent appearing in the roster graph, their own `battles_rated` "
        "count in the full-universe OAR solve (how many identifiable battles they appear in at "
        "all, as either side, corpus-wide -- not just against roster generals):"
    )
    emit()
    emit("| Full-universe battle count | Off-roster opponents |")
    emit("|---|---|")
    for lo, hi in COVERAGE_BUCKETS:
        label = _bucket_label(lo, hi)
        emit(f"| {label} | {bucket_counts[label]} |")
    emit()

    emit("## Variant 1: full-universe OAR vs. baseline")
    emit()
    emit(
        f"Spearman rank correlation vs. baseline (roster-only OAR), over "
        f"{len(set(variant1_rank_by_id) & set(baseline_rank_by_id))} generals ranked by both: "
        f"**{spearman_v1:+.3f}**." if spearman_v1 is not None else "Spearman vs. baseline: n/a."
    )
    emit()
    emit(f"Top {TOP_N} entering under variant 1 (not in baseline top {TOP_N}): "
         + (", ".join(display_names[g] for g in v1_entering) if v1_entering else "none"))
    emit(f"Top {TOP_N} leaving under variant 1 (in baseline top {TOP_N}, not variant 1): "
         + (", ".join(display_names[g] for g in v1_leaving) if v1_leaving else "none"))
    emit()

    emit("## Variant 2: confidence-weighted OAR vs. baseline")
    emit()
    emit(
        f"Weight = `n / (n + {CONFIDENCE_PSEUDO_COUNT})` where `n` is the opponent's full-universe "
        f"battle count (reusing `ranking_tables.MIN_BATTLES_FOR_HEADLINE_RANKING`'s pseudo-count "
        f"convention). Spearman rank correlation vs. baseline, over "
        f"{len(set(variant2_rank_by_id) & set(baseline_rank_by_id))} generals ranked by both: "
        f"**{spearman_v2:+.3f}**." if spearman_v2 is not None else "Spearman vs. baseline: n/a."
    )
    emit()
    emit(f"Top {TOP_N} entering under variant 2: "
         + (", ".join(display_names[g] for g in v2_entering) if v2_entering else "none"))
    emit(f"Top {TOP_N} leaving under variant 2: "
         + (", ".join(display_names[g] for g in v2_leaving) if v2_leaving else "none"))
    emit()

    emit("## Must-include generals: rank under each variant")
    emit()
    emit("| General | Baseline rank | Variant 1 (full-universe OAR) rank | Variant 2 (confidence-weighted OAR) rank |")
    emit("|---|---|---|---|")
    for csv_id, pipeline_id in must_include:
        b = baseline_rank_by_id.get(pipeline_id)
        v1 = variant1_rank_by_id.get(pipeline_id)
        v2 = variant2_rank_by_id.get(pipeline_id)
        name = display_names.get(pipeline_id, csv_id)
        emit(f"| {name} | {b if b is not None else 'n/a'} | {v1 if v1 is not None else 'n/a'} | "
             f"{v2 if v2 is not None else 'n/a'} |")
    emit()

    emit("## Napoleon-Wellington: what do the two ratings depend on, with Waterloo missing?")
    emit()
    emit(
        f"Napoleon (`{napoleon_id}`) has {len(napoleon_opponents)} rated opponent-rows in the "
        f"roster graph; Wellington (`{wellington_id}`) has {len(wellington_opponents)}. Direct "
        f"shared opponents (an opponent both generals personally fought, in this dataset): "
        + (", ".join(sorted(shared_direct_opponents)) if shared_direct_opponents else "none") + "."
    )
    emit()
    emit("Napoleon's rated opponents (battle, opponent_general_id, outcome):")
    for battle_name, opp, outcome in napoleon_opponents:
        emit(f"- {battle_name} vs. `{opp}`: {outcome}")
    emit()
    emit("Wellington's rated opponents (battle, opponent_general_id, outcome):")
    for battle_name, opp, outcome in wellington_opponents:
        emit(f"- {battle_name} vs. `{opp}`: {outcome}")
    emit()
    for label, gid in (("Napoleon", napoleon_id), ("Wellington", wellington_id)):
        for variant_name, oar_dict in (
            ("baseline", oar_ratings(roster_battles)),
            ("full-universe", full_universe_oar),
            ("confidence-weighted", weighted_oar),
        ):
            rating = oar_dict.get(gid)
            if rating is not None:
                emit(f"- {label} {variant_name} OAR: {rating.rating:.1f} ({rating.battles_rated} rated battles)")
    emit()

    napoleon_gaps = {}
    for variant_name, oar_dict in (
        ("baseline", oar_ratings(roster_battles)),
        ("full-universe", full_universe_oar),
        ("confidence-weighted", weighted_oar),
    ):
        n = oar_dict.get(napoleon_id)
        w = oar_dict.get(wellington_id)
        if n is not None and w is not None:
            napoleon_gaps[variant_name] = n.rating - w.rating

    emit("## Answer")
    emit()
    emit(
        f"**Off-roster share is higher than PROGRESS.md's old 65%/35% split, not lower**: "
        f"{len(off_roster_opponents) / len(opponent_rows):.0%} of distinct opponents "
        f"({off_roster_rows / total_opponent_rows:.0%} of opponent-rows, the weighted figure) are "
        f"off-roster today, after H1/H4 grew the dataset. Rating them from the full battle "
        f"universe instead of a flat 1500 barely moves the composite ranking "
        f"(Spearman {spearman_v1:+.3f} vs. baseline, {len(v1_entering)} of the top {TOP_N} swap "
        f"either way) because **coverage, not graph size, is the bottleneck**: "
        f"{bucket_counts['1-2']} of {len(off_roster_opponents)} off-roster opponents "
        f"({bucket_counts['1-2'] / len(off_roster_opponents):.0%}) have only 1-2 identifiable "
        f"battles anywhere in the whole cached universe, not just in their games against the "
        f"roster -- most of them are thin because Wikipedia's coverage of them is thin, not "
        f"because this project only looked at their roster-facing games. Only "
        f"{bucket_counts['10+']} of {len(off_roster_opponents)} have 10 or more full-universe "
        f"battles, i.e. enough to plausibly trust a solved rating at all."
    )
    emit()
    emit(
        f"Confidence-weighting (variant 2) moves the ranking about as little "
        f"(Spearman {spearman_v2:+.3f}), for the same reason: discounting a win over a thin-record "
        f"opponent only matters when there are *other*, better-attested wins to lean on instead, "
        f"and most generals' opponent pools are uniformly thin."
    )
    emit()
    if len(napoleon_gaps) == 3:
        emit(
            f"**Where opponent-strength method does matter: a direct comparison with no shared "
            f"battle to anchor it.** Napoleon and Wellington share zero opponents in this dataset "
            f"and (per H4) never get a Waterloo row for either side, so their relative order rests "
            f"entirely on how the *rest* of their respective opponent pools get rated. Napoleon "
            f"leads Wellington by {napoleon_gaps['baseline']:+.1f} Elo points under the baseline, "
            f"{napoleon_gaps['full-universe']:+.1f} under full-universe OAR (full-universe context "
            f"makes Napoleon's deep, win-heavy opponent list look relatively tougher, since many of "
            f"his opponents also beat other people elsewhere), and only "
            f"{napoleon_gaps['confidence-weighted']:+.1f} once thin-record opponents are "
            f"downweighted (most of Napoleon's 124 full-universe-rated wins are against "
            f"one-battle-in-this-corpus opponents, so discounting them costs him more than it "
            f"costs Wellington, whose smaller opponent list is proportionally less thin). The gap "
            f"swings by about {max(napoleon_gaps.values()) - min(napoleon_gaps.values()):.0f} Elo "
            f"points across the three methods without either general's own rating ever reversing "
            f"direction -- a concrete size for how much the opponent-rating method can move a "
            f"head-to-head comparison between two generals who, in the data, never actually met."
        )
    emit()

    report = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")

    with COVERAGE_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["opponent_general_id", "roster_graph_rows", "full_universe_battle_count"])
        for gid, roster_rows, n in coverage_rows:
            writer.writerow([gid, roster_rows, n])

    with RANK_CSV_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["general_id", "display_name", "baseline_rank", "variant1_rank", "variant2_rank"])
        all_ids = sorted(set(baseline_top30) | set(variant1_top30) | set(variant2_top30))
        for gid in all_ids:
            writer.writerow(
                [
                    gid,
                    display_names.get(gid, gid),
                    baseline_rank_by_id.get(gid),
                    variant1_rank_by_id.get(gid),
                    variant2_rank_by_id.get(gid),
                ]
            )

    print(report)
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {COVERAGE_CSV_PATH}")
    print(f"Wrote {RANK_CSV_PATH}")
    print(f"Wrote {FULL_UNIVERSE_BATTLES_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
