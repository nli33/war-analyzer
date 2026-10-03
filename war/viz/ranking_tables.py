"""Ranking tables: PLAN.md Section 6 deliverables 1 ("Composite Power Ranking")
and 2 ("Category Rankings"), rendered as a static HTML page — the last piece
of Phase 6's "3 scatter plots + ranking tables" deliverable.

Per the dataviz skill's own form guidance (`choosing-a-form.md`: "more than
~7 classes that all carry meaning -> a table"), a ranked list of generals with
several numeric columns each is a table by construction, not a chart — so
this module has no categorical palette to validate and no marks/hover layer
to build, unlike `volume_efficiency.py`/`tactical_strategic.py`/
`oar_resource_backing.py`. It reuses only the skill's text-token/surface
roles (`palette.md`) for a plain, readable table, and — matching every other
Phase 6 module's light-only treatment (no dark-mode variant exists for the
three scatter PNGs either, since matplotlib doesn't drive `prefers-color-
scheme`) — ships light mode only, for consistency rather than asymmetric
scope.

Design choices not fully specified by PLAN.md/SCOPE.md:

* **Confidence intervals**: SCOPE.md's deliverable 3 asks for the composite/
  category rankings to carry confidence intervals, and PLAN.md Section 5's
  own example phrases this in terms of OAR ("Caesar: OAR 82 +/- 15"). But
  `uncertainty.py`'s Monte Carlo resampling deliberately does *not* re-run
  OAR, decisive_win_rate, or Longevity-Adjusted Value — they are pure
  functions of `outcome`/`decisiveness`/career years, untouched by the
  troop/casualty resampling, so a "distribution" for them would just be the
  same point estimate N times (see `uncertainty.py`'s own docstring). Rather
  than fabricate a band for those metrics, this module attaches a genuine
  Monte Carlo 90% interval only where one actually exists: WAR-residual (one
  of the Composite Power Ranking's four inputs) and Clutch Rating (one of
  the six category rankings). Every other column is a plain point estimate,
  with no invented uncertainty — an honest gap, not an oversight, and worth
  flagging in Phase 7's sanity pass if it reads as incomplete.
* **`mc` is an injected, optional pre-computed dict** (`monte_carlo_
  uncertainty`'s own return type), not computed inside this module. A real
  1000-run resample is expensive to call from every test; every other Phase
  6 viz module's tests use small hand-computed fixtures, and injecting `mc`
  keeps that possible here too — a test can hand-build a two-entry
  `MetricDistribution` dict instead of running Monte Carlo just to check the
  table wires the CI columns to the right cells. `mc=None` (the default)
  renders every CI-eligible column as plain point estimates.
* **Composite Power Ranking columns**: `composite.py`'s own `CompositeRanking`
  only stores z-scores, which are not intuitive to a general reader by
  themselves (PLAN.md's own worked example uses raw OAR, not a z-score) — so
  this module re-joins the four raw per-general values (`oar.py`'s rating,
  `war_residual.py`'s point estimate, `rate.py`'s `decisive_win_rate`,
  `longevity.py`'s `longevity_adjusted_value`) alongside the composite score
  and rank, using the same public functions `composite.py` itself calls
  internally (no reach into its private helpers).
* **Category value formatting** is category-specific (percentage for Win
  Rate/Squander Index, a ":1" ratio suffix for Casualty Efficiency, plain
  numbers otherwise) since each category's underlying metric has a different
  natural unit; this is presentation only; the CSV output keeps raw
  unformatted floats so the numbers stay machine-checkable.
* **`top_n` (PROGRESS.md's D2, default 25)**: at the original 8-general
  roster every table just showed everyone, but the auto-ingested roster runs
  to the hundreds, and a scrollable wall of rows defeats the point of an
  HTML summary table. Each table (composite and every category) renders only
  its best `top_n` rows, with a caption noting the full count when truncated
  (e.g. "top 25 of 342"); the two CSV files are never truncated, since they
  are the "full data alongside" half of D2's ask and the place to look up
  anyone past the cutoff. 25 was picked as enough rows to sanity-check the
  top of a ranking (D3) without the page turning back into a full roster
  dump; `top_n=None` disables truncation for callers that want everything
  (e.g. a small gold-set run where truncation would never trigger anyway).
* **`min_battles` (PROGRESS.md's G1, default 5)**: a general with only one
  or two recorded battles can still get a composite score (every input has a
  no-data convention, per `composite.py`'s docstring), but that score is
  nearly meaningless next to someone with a dozen battles, and the
  auto-ingested roster has plenty of 1-2-battle generals (see the dev log's
  F-phase funnel numbers). Rather than drop them from the dataset (that's a
  roster-membership decision, already made in `war.roster`), this is a
  *display* floor on the headline tables only, the same `top_n`-style
  "filter what's shown, never what's stored" split: a row's `battle_count`
  (added to both dataclasses, always populated, never filtered out of the
  CSVs) is compared against `min_battles` only inside
  `render_ranking_tables_html`, after which `top_n` slices the *eligible*
  rows. 5 was picked because it's the gold set's own floor — every one of
  the 19 hand-curated generals has at least 5 recorded battles (SCOPE.md's
  Phase 2 target was "8-15 battles per general", and nobody landed below 5
  even at the thin end) — so this reuses a bar the project has already
  validated as "enough to compute metrics honestly" (SCOPE.md's stop-and-
  flag wording) rather than inventing a new one. Applies to every category
  table too, not just the composite ranking, per PROGRESS.md's explicit
  ask — one shared constant, not six per-category tunables.
"""

import csv
import html
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from war.config import CompositeWeights, DEFAULT_COMPOSITE_WEIGHTS
from war.metrics.category import CategoryRankEntry, category_rankings
from war.metrics.composite import composite_ranking
from war.metrics.longevity import longevity_adjusted_value_by_general
from war.metrics.oar import oar_ratings
from war.metrics.rate import rate_stats_by_general
from war.metrics.uncertainty import MetricDistribution
from war.metrics.war_residual import war_residual_by_general
from war.records import Battle, General

_SURFACE_COLOR = "#fcfcfb"  # dataviz skill palette.md light chart surface
_TEXT_PRIMARY = "#0b0b0b"  # dataviz skill palette.md light text-primary
_TEXT_SECONDARY = "#52514e"  # dataviz skill palette.md light text-secondary
_ACCENT_COLOR = "#2a78d6"  # dataviz skill palette.md categorical slot 1 (light)
_BORDER_COLOR = "#e3e2dc"  # a muted step off the light surface, for row rules

CATEGORY_LABELS: dict[str, str] = {
    "win_rate": "Win Rate",
    "casualty_efficiency": "Casualty Efficiency",
    "opponent_adjusted_rating": "Opponent-Adjusted Rating",
    "clutch_rating": "Clutch Rating",
    "squander_index": "Squander Index",
    "longevity_adjusted_value": "Longevity-Adjusted Value",
}

# Category key -> (value column header, formatter). Kept centralized so the
# HTML/CSV renderers agree on units without duplicating the mapping.
_CATEGORY_VALUE_FORMAT: dict[str, tuple[str, "callable"]] = {
    "win_rate": ("Win Rate", lambda v: f"{v:.1%}"),
    "casualty_efficiency": ("Enemy:Own Casualties", lambda v: f"{v:.2f}:1"),
    "opponent_adjusted_rating": ("OAR", lambda v: f"{v:.0f}"),
    "clutch_rating": ("Clutch Rating", lambda v: f"{v:.3f}"),
    "squander_index": ("Squander Index", lambda v: f"{v:.1%}"),
    "longevity_adjusted_value": ("Longevity-Adj. Value", lambda v: f"{v:.3f}"),
}

# Category eligible for a Monte Carlo confidence interval (see module
# docstring) -> the `uncertainty.py` metric name it reuses.
_CATEGORY_MC_METRIC = {"clutch_rating": "clutch_rating"}

# Minimum recorded battles for a general to appear in the headline (HTML)
# tables -- see module docstring's "min_battles" entry. Never filters the
# CSVs; every roster general with a computable value stays in those.
MIN_BATTLES_FOR_HEADLINE_RANKING = 5


@dataclass(frozen=True)
class CompositeRankingRow:
    """One rendered row of the Composite Power Ranking table."""

    general_id: str
    display_name: str
    era: str
    rank: int
    battle_count: int
    composite_score: float
    oar_rating: float
    decisive_win_rate: float | None
    longevity_adjusted_value: float
    war_residual: float
    war_residual_ci_low: float | None
    war_residual_ci_high: float | None


@dataclass(frozen=True)
class CategoryTableRow:
    """One rendered row within a single category's ranking table."""

    general_id: str
    display_name: str
    rank: int
    battle_count: int
    value: float
    ci_low: float | None
    ci_high: float | None


def _mc_interval(
    mc: dict[str, dict[str, MetricDistribution]] | None, general_id: str, metric: str
) -> tuple[float | None, float | None]:
    if mc is None:
        return None, None
    distribution = mc.get(general_id, {}).get(metric)
    if distribution is None or distribution.runs_used == 0:
        return None, None
    return distribution.ci_low, distribution.ci_high


def composite_ranking_rows(
    battles: list[Battle],
    generals: list[General],
    weights: CompositeWeights = DEFAULT_COMPOSITE_WEIGHTS,
    mc: dict[str, dict[str, MetricDistribution]] | None = None,
) -> list[CompositeRankingRow]:
    """Join `composite_ranking`'s output with the raw per-general values it
    scored, sorted by rank (already best-first from `composite_ranking`).

    `mc` (see module docstring) optionally attaches a Monte Carlo 90% CI to
    the WAR-residual column; omitted or missing entries leave it `None`.
    Empty `battles` returns an empty list.
    """
    ranking = composite_ranking(battles, generals, weights)
    if not ranking:
        return []

    era_by_general = {general.general_id: general.era for general in generals}
    display_names = {general.general_id: general.display_name for general in generals}
    battle_counts = Counter(battle.general_id for battle in battles)
    oar = oar_ratings(battles)
    rate_stats = rate_stats_by_general(battles)
    longevity = longevity_adjusted_value_by_general(battles, generals)
    war_residual = war_residual_by_general(battles)

    rows = []
    for entry in ranking:
        gid = entry.general_id
        ci_low, ci_high = _mc_interval(mc, gid, "war_residual")
        rows.append(
            CompositeRankingRow(
                general_id=gid,
                display_name=display_names[gid],
                era=era_by_general[gid],
                rank=entry.rank,
                battle_count=battle_counts[gid],
                composite_score=entry.composite_score,
                oar_rating=oar[gid].rating,
                decisive_win_rate=rate_stats[gid].decisive_win_rate,
                longevity_adjusted_value=longevity[gid].longevity_adjusted_value,
                war_residual=war_residual[gid].war_residual,
                war_residual_ci_low=ci_low,
                war_residual_ci_high=ci_high,
            )
        )
    return rows


def category_ranking_rows(
    battles: list[Battle],
    generals: list[General],
    mc: dict[str, dict[str, MetricDistribution]] | None = None,
) -> dict[str, list[CategoryTableRow]]:
    """Join `category_rankings`'s output with display names (and, for Clutch
    Rating only, a Monte Carlo 90% CI — see module docstring).

    Empty `battles` returns every category mapped to an empty list, matching
    `category_rankings`'s own convention.
    """
    display_names = {general.general_id: general.display_name for general in generals}
    battle_counts = Counter(battle.general_id for battle in battles)
    rankings = category_rankings(battles, generals)

    def to_row(category: str, entry: CategoryRankEntry) -> CategoryTableRow:
        mc_metric = _CATEGORY_MC_METRIC.get(category)
        ci_low, ci_high = (
            _mc_interval(mc, entry.general_id, mc_metric) if mc_metric else (None, None)
        )
        return CategoryTableRow(
            general_id=entry.general_id,
            display_name=display_names[entry.general_id],
            rank=entry.rank,
            battle_count=battle_counts[entry.general_id],
            value=entry.value,
            ci_low=ci_low,
            ci_high=ci_high,
        )

    return {
        category: [to_row(category, entry) for entry in entries]
        for category, entries in rankings.items()
    }


def _table_caption(label: str, shown: int, total: int) -> str:
    if shown < total:
        return f"{label} (top {shown} of {total})"
    return label


def _composite_table_html(rows: list[CompositeRankingRow], total: int) -> str:
    header = (
        '<tr><th>Rank</th><th>General</th><th class="era-cell">Era</th><th>Battles</th><th>Composite Score</th>'
        "<th>OAR</th><th>WAR-Residual (90% CI)</th><th>Decisive Win Rate</th>"
        "<th>Longevity-Adj. Value</th></tr>"
    )
    body_rows = []
    for row in rows:
        if row.war_residual_ci_low is not None:
            war_residual_cell = (
                f"{row.war_residual:+.3f} "
                f"({row.war_residual_ci_low:+.3f} to {row.war_residual_ci_high:+.3f})"
            )
        else:
            war_residual_cell = f"{row.war_residual:+.3f}"
        decisive_cell = (
            f"{row.decisive_win_rate:.1%}" if row.decisive_win_rate is not None else "—"
        )
        body_rows.append(
            "<tr>"
            f"<td>{row.rank}</td>"
            f"<td>{html.escape(row.display_name)}</td>"
            f'<td class="era-cell">{html.escape(row.era)}</td>'
            f"<td>{row.battle_count}</td>"
            f"<td>{row.composite_score:+.3f}</td>"
            f"<td>{row.oar_rating:.0f}</td>"
            f"<td>{war_residual_cell}</td>"
            f"<td>{decisive_cell}</td>"
            f"<td>{row.longevity_adjusted_value:.3f}</td>"
            "</tr>"
        )
    caption = html.escape(_table_caption("Composite Power Ranking", len(rows), total))
    return (
        f'<table class="ranking-table"><caption>{caption}</caption>'
        f"<thead>{header}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


def _category_table_html(category: str, rows: list[CategoryTableRow], total: int) -> str:
    value_label, formatter = _CATEGORY_VALUE_FORMAT[category]
    header = (
        f"<tr><th>Rank</th><th>General</th><th>Battles</th><th>{html.escape(value_label)}</th></tr>"
    )
    body_rows = []
    for row in rows:
        if row.ci_low is not None:
            value_cell = f"{formatter(row.value)} ({formatter(row.ci_low)} to {formatter(row.ci_high)})"
        else:
            value_cell = formatter(row.value)
        body_rows.append(
            "<tr>"
            f"<td>{row.rank}</td>"
            f"<td>{html.escape(row.display_name)}</td>"
            f"<td>{row.battle_count}</td>"
            f"<td>{value_cell}</td>"
            "</tr>"
        )
    caption = html.escape(_table_caption(CATEGORY_LABELS[category], len(rows), total))
    return (
        f'<table class="ranking-table"><caption>{caption}</caption>'
        f"<thead>{header}</thead><tbody>{''.join(body_rows)}</tbody></table>"
    )


_STYLE = f"""
body {{ background: {_SURFACE_COLOR}; color: {_TEXT_PRIMARY};
  font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 2rem; }}
h1, h2 {{ color: {_TEXT_PRIMARY}; }}
.category-grid {{ display: flex; flex-wrap: wrap; gap: 2rem; }}
table.ranking-table {{ border-collapse: collapse; margin-bottom: 1rem; }}
table.ranking-table caption {{ text-align: left; font-weight: 600; color: {_TEXT_PRIMARY};
  margin-bottom: 0.5rem; }}
table.ranking-table th, table.ranking-table td {{ padding: 0.35rem 0.75rem;
  border-bottom: 1px solid {_BORDER_COLOR}; text-align: right; white-space: nowrap; }}
table.ranking-table th:nth-child(2), table.ranking-table td:nth-child(2) {{ text-align: left; }}
table.ranking-table td.era-cell {{ text-align: left; }}
table.ranking-table thead th {{ border-bottom: 2px solid {_ACCENT_COLOR}; color: {_TEXT_SECONDARY};
  font-weight: 600; }}
"""


def render_ranking_tables_html(
    composite_rows: list[CompositeRankingRow],
    category_rows: dict[str, list[CategoryTableRow]],
    top_n: int | None = 25,
    min_battles: int = MIN_BATTLES_FOR_HEADLINE_RANKING,
) -> str:
    """Render the Composite Power Ranking and the six category rankings as one
    static HTML page (no JS, no server) — plain string in, plain string out,
    so tests can assert on its contents directly rather than parsing a file.

    `min_battles` (see module docstring) drops rows below the battle-count
    floor from every table *before* `top_n` slices the survivors, so a
    thin-data general never occupies a "top n" slot nor displaces a
    better-populated general further down the ranking; the caption's
    "of N" count also reflects the post-`min_battles` pool, not the full
    roster. `top_n` caps each table (post-floor) at its best `top_n` rows;
    `None` renders every eligible row.
    """
    full_categories = {
        category: category_rows.get(category, []) for category in CATEGORY_LABELS
    }
    category_table_htmls = []
    for category, rows in full_categories.items():
        eligible = [row for row in rows if row.battle_count >= min_battles]
        display = eligible[:top_n] if top_n is not None else eligible
        category_table_htmls.append(_category_table_html(category, display, total=len(eligible)))
    category_tables = "".join(category_table_htmls)

    eligible_composite = [row for row in composite_rows if row.battle_count >= min_battles]
    composite_display = eligible_composite[:top_n] if top_n is not None else eligible_composite
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>War Analyzer — Ranking Tables</title>"
        f"<style>{_STYLE}</style></head><body>"
        "<h1>War Analyzer — Ranking Tables</h1>"
        f"{_composite_table_html(composite_display, total=len(eligible_composite))}"
        "<h2>Category Rankings</h2>"
        f'<div class="category-grid">{category_tables}</div>'
        "</body></html>"
    )


def _write_composite_csv(rows: list[CompositeRankingRow], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "rank",
                "general_id",
                "display_name",
                "era",
                "battle_count",
                "composite_score",
                "oar_rating",
                "decisive_win_rate",
                "longevity_adjusted_value",
                "war_residual",
                "war_residual_ci_low",
                "war_residual_ci_high",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.rank,
                    row.general_id,
                    row.display_name,
                    row.era,
                    row.battle_count,
                    row.composite_score,
                    row.oar_rating,
                    row.decisive_win_rate,
                    row.longevity_adjusted_value,
                    row.war_residual,
                    row.war_residual_ci_low,
                    row.war_residual_ci_high,
                ]
            )


def _write_category_csv(category_rows: dict[str, list[CategoryTableRow]], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["category", "rank", "general_id", "display_name", "battle_count", "value", "ci_low", "ci_high"]
        )
        for category, rows in category_rows.items():
            for row in rows:
                writer.writerow(
                    [
                        category,
                        row.rank,
                        row.general_id,
                        row.display_name,
                        row.battle_count,
                        row.value,
                        row.ci_low,
                        row.ci_high,
                    ]
                )


def save_ranking_tables(
    battles: list[Battle],
    generals: list[General],
    output_path: Path | str,
    weights: CompositeWeights = DEFAULT_COMPOSITE_WEIGHTS,
    mc: dict[str, dict[str, MetricDistribution]] | None = None,
    top_n: int | None = 25,
    min_battles: int = MIN_BATTLES_FOR_HEADLINE_RANKING,
) -> Path:
    """Compute both rankings, render the HTML page, and save it plus two CSVs
    (`<stem>_composite.csv`, `<stem>_categories.csv`) next to it — the CSV
    pair keeps every number independently machine-checkable and, per `top_n`
    and `min_battles` (module docstring), is never truncated/floored even
    when the HTML page is.

    Returns the resolved HTML output path.
    """
    composite_rows = composite_ranking_rows(battles, generals, weights, mc)
    category_rows = category_ranking_rows(battles, generals, mc)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_ranking_tables_html(
            composite_rows, category_rows, top_n=top_n, min_battles=min_battles
        ),
        encoding="utf-8",
    )

    _write_composite_csv(composite_rows, output_path.with_name(output_path.stem + "_composite.csv"))
    _write_category_csv(category_rows, output_path.with_name(output_path.stem + "_categories.csv"))

    return output_path
