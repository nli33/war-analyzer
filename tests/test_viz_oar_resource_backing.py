"""Phase 6 OAR vs. Resource Backing scatter: hand-computed data + figure-shape checks.

No display is available in the overnight sandbox (SCOPE.md Phase 6), so this
verifies the render without looking at a screenshot: `render_oar_resource_backing_figure`
returns a plain `matplotlib.figure.Figure` we can inspect directly (point count,
coordinates, labels), and `plot_oar_vs_resource_backing` is checked by asserting the
saved PNG/CSV files exist, are non-empty, and the CSV's numbers match the inputs.

The Resource Backing axis (a plain mean of a per-battle field) is hand-computed
directly. The OAR axis is an iterative Elo solve (`oar.py`), not hand-computable
as a one-line fraction the way the other viz modules' axes are (`oar.py`'s own
tests take the same approach) — instead this cross-checks that the plotted value
is exactly what `oar_ratings` independently produces for the same battles.
"""

from war.metrics.oar import oar_ratings
from war.records import Battle, General
from war.viz.oar_resource_backing import (
    oar_resource_backing_points,
    plot_oar_vs_resource_backing,
    render_oar_resource_backing_figure,
)


def make_battle(
    general_id,
    outcome,
    resource_backing_tier,
    opponent_general_id=None,
    battle_id=None,
):
    """A Battle with only the fields OAR/resource-backing read meaningfully."""
    return Battle(
        battle_id=battle_id or f"{general_id}-{outcome}-{id(object())}",
        general_id=general_id,
        battle_name="Test Battle",
        date="1900",
        era="Industrial",
        own_troop_strength=10_000,
        enemy_troop_strength=10_000,
        own_casualties=1,
        enemy_casualties=1,
        outcome=outcome,
        decisiveness=None,
        objective_secured=False,
        opponent_general_id=opponent_general_id,
        resource_backing_tier=resource_backing_tier,
        tech_era_tier=3,
        political_constraint_flag=False,
        source_confidence="High",
        source_citation="test fixture",
        notes=None,
    )


def make_general(general_id, display_name):
    return General(
        general_id=general_id,
        display_name=display_name,
        era="Industrial",
        career_start_year=1900,
        career_end_year=1901,
        notes=None,
    )


def test_resource_backing_is_mean_of_per_battle_tiers():
    battles = [
        make_battle("alice", "Win", 5, opponent_general_id="bob", battle_id="a1"),
        make_battle("alice", "Loss", 1, opponent_general_id="bob", battle_id="a2"),
        make_battle("bob", "Loss", 3, opponent_general_id="alice", battle_id="b1"),
        make_battle("bob", "Win", 3, opponent_general_id="alice", battle_id="b2"),
    ]
    generals = [make_general("alice", "Alice"), make_general("bob", "Bob")]

    points = oar_resource_backing_points(battles, generals)

    by_id = {p.general_id: p for p in points}
    assert by_id["alice"].avg_resource_backing_tier == 3.0  # (5 + 1) / 2
    assert by_id["bob"].avg_resource_backing_tier == 3.0  # (3 + 3) / 2
    assert by_id["alice"].display_name == "Alice"


def test_oar_rating_matches_independent_solve():
    battles = [
        make_battle("alice", "Win", 3, opponent_general_id="bob", battle_id="a1"),
        make_battle("bob", "Loss", 3, opponent_general_id="alice", battle_id="b1"),
    ]
    generals = [make_general("alice", "Alice"), make_general("bob", "Bob")]

    points = oar_resource_backing_points(battles, generals)
    expected = oar_ratings(battles)

    by_id = {p.general_id: p for p in points}
    assert by_id["alice"].oar_rating == expected["alice"].rating
    assert by_id["bob"].oar_rating == expected["bob"].rating
    assert expected["alice"].rating > expected["bob"].rating  # alice won


def test_points_sorted_by_general_id():
    battles = [make_battle("zeta", "Win", 3), make_battle("alice", "Win", 3)]
    generals = [make_general("zeta", "Zeta"), make_general("alice", "Alice")]

    points = oar_resource_backing_points(battles, generals)

    assert [p.general_id for p in points] == ["alice", "zeta"]


def test_empty_input_produces_no_points():
    assert oar_resource_backing_points([], []) == []


def test_figure_has_one_scatter_point_per_general():
    battles = [
        make_battle("alice", "Win", 5, battle_id="a1"),
        make_battle("alice", "Win", 1, battle_id="a2"),
        make_battle("bob", "Win", 3, battle_id="b1"),
    ]
    generals = [make_general("alice", "Alice"), make_general("bob", "Bob")]
    points = oar_resource_backing_points(battles, generals)

    fig = render_oar_resource_backing_figure(points)
    ax = fig.axes[0]
    offsets = ax.collections[0].get_offsets()

    assert len(offsets) == 2
    plotted = {tuple(offset) for offset in offsets}
    by_id = {p.general_id: p for p in points}
    assert (by_id["alice"].oar_rating, 3.0) in plotted
    assert (by_id["bob"].oar_rating, 3.0) in plotted


def test_figure_labels_every_point_by_display_name():
    battles = [make_battle("alice", "Win", 3)]
    generals = [make_general("alice", "Alice the Great")]
    points = oar_resource_backing_points(battles, generals)

    fig = render_oar_resource_backing_figure(points)
    ax = fig.axes[0]

    assert [t.get_text() for t in ax.texts] == ["Alice the Great"]


def test_empty_points_renders_without_error():
    fig = render_oar_resource_backing_figure([])
    assert len(fig.axes[0].collections[0].get_offsets()) == 0


def test_plot_writes_nonempty_png_and_matching_csv(tmp_path):
    battles = [
        make_battle("alice", "Win", 5, battle_id="a1"),
        make_battle("alice", "Loss", 1, battle_id="a2"),
    ]
    generals = [make_general("alice", "Alice")]
    output_path = tmp_path / "oar_vs_resource_backing.png"

    result_path = plot_oar_vs_resource_backing(battles, generals, output_path)

    assert result_path == output_path
    assert output_path.exists() and output_path.stat().st_size > 0
    assert output_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    csv_path = output_path.with_suffix(".csv")
    assert csv_path.exists() and csv_path.stat().st_size > 0
    rows = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0] == "general_id,display_name,oar_rating,avg_resource_backing_tier"
    expected_rating = oar_ratings(battles)["alice"].rating
    assert rows[1] == f"alice,Alice,{expected_rating},3.0"
