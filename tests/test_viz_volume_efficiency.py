"""Phase 6 Volume vs. Efficiency scatter: hand-computed data + figure-shape checks.

No display is available in the overnight sandbox (SCOPE.md Phase 6), so this
verifies the render without looking at a screenshot: `render_volume_efficiency_figure`
returns a plain `matplotlib.figure.Figure` we can inspect directly (point count,
coordinates, labels), and `plot_volume_vs_efficiency` is checked by asserting the
saved PNG/CSV files exist, are non-empty, and the CSV's numbers match the inputs.
"""

from war.records import Battle, General
from war.viz.volume_efficiency import (
    plot_volume_vs_efficiency,
    render_volume_efficiency_figure,
    volume_efficiency_points,
)


def make_battle(general_id, outcome, battle_id=None):
    """A Battle with only the fields battles_commanded/win_rate read meaningfully."""
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
        decisiveness="Tactical" if outcome == "Win" else None,
        objective_secured=outcome == "Win",
        opponent_general_id=None,
        resource_backing_tier=3,
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


def test_points_hand_computed():
    battles = [
        make_battle("alice", "Win", battle_id="a1"),
        make_battle("alice", "Win", battle_id="a2"),
        make_battle("alice", "Loss", battle_id="a3"),
        make_battle("alice", "Loss", battle_id="a4"),
        make_battle("bob", "Win", battle_id="b1"),
    ]
    generals = [make_general("alice", "Alice"), make_general("bob", "Bob")]

    points = volume_efficiency_points(battles, generals)

    by_id = {p.general_id: p for p in points}
    assert by_id["alice"].battles_commanded == 4
    assert by_id["alice"].win_rate == 0.5
    assert by_id["alice"].display_name == "Alice"
    assert by_id["bob"].battles_commanded == 1
    assert by_id["bob"].win_rate == 1.0


def test_points_sorted_by_general_id():
    battles = [make_battle("zeta", "Win"), make_battle("alice", "Win")]
    generals = [make_general("zeta", "Zeta"), make_general("alice", "Alice")]

    points = volume_efficiency_points(battles, generals)

    assert [p.general_id for p in points] == ["alice", "zeta"]


def test_empty_input_produces_no_points():
    assert volume_efficiency_points([], []) == []


def test_figure_has_one_scatter_point_per_general():
    battles = [
        make_battle("alice", "Win", battle_id="a1"),
        make_battle("alice", "Loss", battle_id="a2"),
        make_battle("bob", "Win", battle_id="b1"),
    ]
    generals = [make_general("alice", "Alice"), make_general("bob", "Bob")]
    points = volume_efficiency_points(battles, generals)

    fig = render_volume_efficiency_figure(points)
    ax = fig.axes[0]
    offsets = ax.collections[0].get_offsets()

    assert len(offsets) == 2
    plotted = {tuple(offset) for offset in offsets}
    assert (2, 0.5) in plotted  # alice: 2 battles, 1 win
    assert (1, 1.0) in plotted  # bob: 1 battle, 1 win


def test_figure_labels_every_point_by_display_name():
    battles = [make_battle("alice", "Win")]
    generals = [make_general("alice", "Alice the Great")]
    points = volume_efficiency_points(battles, generals)

    fig = render_volume_efficiency_figure(points)
    ax = fig.axes[0]

    assert [t.get_text() for t in ax.texts] == ["Alice the Great"]


def test_empty_points_renders_without_error():
    fig = render_volume_efficiency_figure([])
    assert len(fig.axes[0].collections[0].get_offsets()) == 0


def test_plot_writes_nonempty_png_and_matching_csv(tmp_path):
    battles = [
        make_battle("alice", "Win", battle_id="a1"),
        make_battle("alice", "Loss", battle_id="a2"),
    ]
    generals = [make_general("alice", "Alice")]
    output_path = tmp_path / "volume_vs_efficiency.png"

    result_path = plot_volume_vs_efficiency(battles, generals, output_path)

    assert result_path == output_path
    assert output_path.exists() and output_path.stat().st_size > 0
    assert output_path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    csv_path = output_path.with_suffix(".csv")
    assert csv_path.exists() and csv_path.stat().st_size > 0
    rows = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0] == "general_id,display_name,battles_commanded,win_rate"
    assert rows[1] == "alice,Alice,2,0.5"
