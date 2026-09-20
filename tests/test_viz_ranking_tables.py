"""Phase 6 ranking tables: hand-computed row-joining checks plus HTML/CSV
render checks, per SCOPE.md Phase 6's no-display verification method (same
"inspect the data structure, then inspect the saved file's bytes/text"
approach the three scatter-plot viz test files already use).
"""

from war.metrics.composite import composite_ranking
from war.metrics.longevity import longevity_adjusted_value_by_general
from war.metrics.oar import oar_ratings
from war.metrics.rate import rate_stats_by_general
from war.metrics.uncertainty import MetricDistribution
from war.metrics.war_residual import war_residual_by_general
from war.records import Battle, General
from war.viz.ranking_tables import (
    CATEGORY_LABELS,
    category_ranking_rows,
    composite_ranking_rows,
    render_ranking_tables_html,
    save_ranking_tables,
)


def make_battle(
    general_id,
    outcome,
    opponent_general_id=None,
    era="Industrial",
    battle_id=None,
    resource_backing_tier=3,
    decisiveness=None,
    objective_secured=False,
    own_troop_strength=10_000,
    enemy_troop_strength=10_000,
    own_casualties=1_000,
    enemy_casualties=1_000,
):
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{opponent_general_id}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era=era,
        own_troop_strength=own_troop_strength,
        enemy_troop_strength=enemy_troop_strength,
        own_casualties=own_casualties,
        enemy_casualties=enemy_casualties,
        outcome=outcome,
        decisiveness=decisiveness,
        objective_secured=objective_secured,
        opponent_general_id=opponent_general_id,
        resource_backing_tier=resource_backing_tier,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def make_general(general_id, display_name=None, era="Industrial"):
    return General(
        general_id=general_id,
        display_name=display_name or general_id.title(),
        era=era,
        career_start_year=1900,
        career_end_year=1901,
        notes=None,
    )


def _two_general_fixture():
    battles = [
        make_battle(
            "alice",
            "Win",
            opponent_general_id="bob",
            decisiveness="Strategic",
            objective_secured=True,
            battle_id="a1",
        ),
        make_battle("bob", "Loss", opponent_general_id="alice", battle_id="b1"),
    ]
    generals = [make_general("alice"), make_general("bob")]
    return battles, generals


def test_composite_rows_empty_input():
    assert composite_ranking_rows([], []) == []


def test_composite_rows_join_raw_values_and_rank():
    battles, generals = _two_general_fixture()

    rows = composite_ranking_rows(battles, generals)

    expected_ranking = {r.general_id: r for r in composite_ranking(battles, generals)}
    expected_oar = oar_ratings(battles)
    expected_rate = rate_stats_by_general(battles)
    expected_longevity = longevity_adjusted_value_by_general(battles, generals)
    expected_war_residual = war_residual_by_general(battles)

    by_id = {row.general_id: row for row in rows}
    assert set(by_id) == {"alice", "bob"}
    for gid in by_id:
        row = by_id[gid]
        assert row.display_name == gid.title()
        assert row.era == "Industrial"
        assert row.rank == expected_ranking[gid].rank
        assert row.composite_score == expected_ranking[gid].composite_score
        assert row.oar_rating == expected_oar[gid].rating
        assert row.decisive_win_rate == expected_rate[gid].decisive_win_rate
        assert row.longevity_adjusted_value == expected_longevity[gid].longevity_adjusted_value
        assert row.war_residual == expected_war_residual[gid].war_residual
        # no `mc` passed in -> no fabricated interval
        assert row.war_residual_ci_low is None
        assert row.war_residual_ci_high is None

    # alice won -> ranked above bob
    assert by_id["alice"].rank == 1
    assert by_id["bob"].rank == 2


def test_composite_rows_attach_war_residual_ci_when_mc_given():
    battles, generals = _two_general_fixture()
    mc = {
        "alice": {
            "war_residual": MetricDistribution(
                general_id="alice", metric="war_residual", mean=0.5, ci_low=0.1, ci_high=0.9, runs_used=100
            )
        },
        "bob": {
            "war_residual": MetricDistribution(
                general_id="bob", metric="war_residual", mean=None, ci_low=None, ci_high=None, runs_used=0
            )
        },
    }

    rows = composite_ranking_rows(battles, generals, mc=mc)

    by_id = {row.general_id: row for row in rows}
    assert by_id["alice"].war_residual_ci_low == 0.1
    assert by_id["alice"].war_residual_ci_high == 0.9
    # runs_used == 0 -> stays None, same no-data convention as everywhere else
    assert by_id["bob"].war_residual_ci_low is None
    assert by_id["bob"].war_residual_ci_high is None


def test_category_rows_empty_input():
    rows = category_ranking_rows([], [])
    assert set(rows) == set(CATEGORY_LABELS)
    assert all(entries == [] for entries in rows.values())


def test_category_rows_join_display_names_and_values():
    battles, generals = _two_general_fixture()

    rows = category_ranking_rows(battles, generals)

    win_rate_rows = {row.general_id: row for row in rows["win_rate"]}
    assert win_rate_rows["alice"].display_name == "Alice"
    assert win_rate_rows["alice"].value == 1.0
    assert win_rate_rows["alice"].rank == 1
    assert win_rate_rows["bob"].value == 0.0
    assert win_rate_rows["bob"].rank == 2
    # win_rate has no Monte Carlo distribution -> never gets a fabricated CI
    assert win_rate_rows["alice"].ci_low is None


def test_category_rows_attach_clutch_rating_ci_only():
    battles, generals = _two_general_fixture()
    mc = {
        "alice": {
            "clutch_rating": MetricDistribution(
                general_id="alice", metric="clutch_rating", mean=1.0, ci_low=0.8, ci_high=1.0, runs_used=100
            )
        },
        "bob": {},
    }

    rows = category_ranking_rows(battles, generals, mc=mc)

    clutch_by_id = {row.general_id: row for row in rows["clutch_rating"]}
    if "alice" in clutch_by_id:
        assert clutch_by_id["alice"].ci_low == 0.8
        assert clutch_by_id["alice"].ci_high == 1.0

    # a category with no MC metric mapping stays uninfluenced by `mc`
    win_rate_by_id = {row.general_id: row for row in rows["win_rate"]}
    assert all(row.ci_low is None for row in win_rate_by_id.values())


def test_render_html_contains_composite_and_all_six_category_tables():
    battles, generals = _two_general_fixture()
    composite_rows = composite_ranking_rows(battles, generals)
    category_rows = category_ranking_rows(battles, generals)

    output = render_ranking_tables_html(composite_rows, category_rows)

    assert output.startswith("<!DOCTYPE html>")
    assert "Composite Power Ranking" in output
    for label in CATEGORY_LABELS.values():
        assert label in output
    assert "Alice" in output
    assert "Bob" in output


def test_render_html_handles_empty_input_without_error():
    output = render_ranking_tables_html([], {category: [] for category in CATEGORY_LABELS})
    assert output.startswith("<!DOCTYPE html>")
    assert "Composite Power Ranking" in output


def test_save_writes_html_and_two_matching_csvs(tmp_path):
    battles, generals = _two_general_fixture()
    output_path = tmp_path / "ranking_tables.html"

    result_path = save_ranking_tables(battles, generals, output_path)

    assert result_path == output_path
    assert output_path.exists() and output_path.stat().st_size > 0
    assert output_path.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    composite_csv = tmp_path / "ranking_tables_composite.csv"
    category_csv = tmp_path / "ranking_tables_categories.csv"
    assert composite_csv.exists() and composite_csv.stat().st_size > 0
    assert category_csv.exists() and category_csv.stat().st_size > 0

    composite_lines = composite_csv.read_text(encoding="utf-8").strip().splitlines()
    assert composite_lines[0].split(",")[:3] == ["rank", "general_id", "display_name"]
    assert len(composite_lines) == 1 + 2  # header + alice + bob

    category_lines = category_csv.read_text(encoding="utf-8").strip().splitlines()
    assert category_lines[0] == "category,rank,general_id,display_name,value,ci_low,ci_high"
