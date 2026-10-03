import csv

from war.reference_rankings import (
    ComparisonRow,
    ReferenceListEntry,
    biggest_disagreements,
    build_comparison_rows,
    load_reference_list,
    rank_correlation_by_source,
    spearman_correlation,
)


def test_load_reference_list(tmp_path):
    path = tmp_path / "top_n_lists.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source", "source_kind", "url", "rank", "name"])
        writer.writerow(["acme", "popular_list", "https://example.com", "1", "Alexander the Great"])
        writer.writerow(["acme", "popular_list", "https://example.com", "2", "Genghis Khan"])

    entries = load_reference_list(path)

    assert entries == [
        ReferenceListEntry("acme", "popular_list", "https://example.com", 1, "Alexander the Great"),
        ReferenceListEntry("acme", "popular_list", "https://example.com", 2, "Genghis Khan"),
    ]


def test_build_comparison_rows_classifies_every_status():
    entries = [
        ReferenceListEntry("acme", "popular_list", "https://example.com", 1, "Ranked Guy"),
        ReferenceListEntry("acme", "popular_list", "https://example.com", 2, "Unranked Roster Guy"),
        ReferenceListEntry("acme", "popular_list", "https://example.com", 3, "Not In Roster Guy"),
        ReferenceListEntry("acme", "popular_list", "https://example.com", 4, "Nobody Knows This Guy"),
    ]
    name_to_general_id = {
        "Ranked Guy": "ranked-guy",
        "Unranked Roster Guy": "unranked-roster-guy",
        "Not In Roster Guy": "not-in-roster-guy",
        "Nobody Knows This Guy": None,
    }
    roster_general_ids = {"ranked-guy", "unranked-roster-guy"}
    rank_by_general_id = {"ranked-guy": 5}
    battle_count_by_general_id = {"ranked-guy": 10, "unranked-roster-guy": 0}

    rows = build_comparison_rows(
        entries, name_to_general_id, roster_general_ids, rank_by_general_id, battle_count_by_general_id
    )

    assert rows == [
        ComparisonRow("acme", 1, "Ranked Guy", "ranked-guy", "ranked", 5, 10),
        ComparisonRow("acme", 2, "Unranked Roster Guy", "unranked-roster-guy", "in_roster_unranked", None, 0),
        ComparisonRow("acme", 3, "Not In Roster Guy", "not-in-roster-guy", "missing", None, None),
        ComparisonRow("acme", 4, "Nobody Knows This Guy", None, "unresolved", None, None),
    ]


def test_spearman_correlation_perfect_agreement():
    assert spearman_correlation([(1, 10), (2, 20), (3, 30)]) == 1.0


def test_spearman_correlation_perfect_disagreement():
    assert spearman_correlation([(1, 30), (2, 20), (3, 10)]) == -1.0


def test_spearman_correlation_needs_at_least_two_pairs():
    assert spearman_correlation([]) is None
    assert spearman_correlation([(1, 1)]) is None


def test_spearman_correlation_constant_input_is_undefined():
    # every x the same -> zero variance -> correlation undefined, not 0.
    assert spearman_correlation([(1, 1), (1, 2), (1, 3)]) is None


def test_rank_correlation_by_source_only_uses_ranked_rows():
    rows = [
        ComparisonRow("acme", 1, "A", "a", "ranked", 1, 5),
        ComparisonRow("acme", 2, "B", "b", "ranked", 2, 5),
        ComparisonRow("acme", 3, "C", "c", "missing", None, None),
        ComparisonRow("other", 1, "D", "d", "unresolved", None, None),
    ]

    correlations = rank_correlation_by_source(rows)

    assert correlations["acme"] == 1.0
    # "other" has zero ranked rows (only an unresolved one), so it never gets an entry at all --
    # that's different from a source with 1 ranked row, which does get an entry (value None).
    assert "other" not in correlations


def test_biggest_disagreements_ranks_by_percentile_gap():
    rows = [
        # published #1 of 10 (top 10%), but we rank them 100th of 100 (bottom) -> huge gap.
        ComparisonRow("acme", 1, "Snubbed", "snubbed", "ranked", 100, 5),
        # published #1 of 10, we also rank them #1 of 100 -> perfect agreement, no gap.
        ComparisonRow("acme", 1, "Agreed", "agreed", "ranked", 1, 5),
    ]

    result = biggest_disagreements(
        rows, list_size_by_source={"acme": 10}, roster_ranked_count=100, top_k=10
    )

    assert [entry["name"] for entry in result] == ["Snubbed", "Agreed"]
    assert result[0]["disagreement"] > result[1]["disagreement"]
    assert result[1]["disagreement"] == 0.0


def test_biggest_disagreements_respects_top_k():
    rows = [
        ComparisonRow("acme", i, f"Gen {i}", f"gen-{i}", "ranked", i * 2, 5) for i in range(1, 6)
    ]

    result = biggest_disagreements(
        rows, list_size_by_source={"acme": 5}, roster_ranked_count=10, top_k=2
    )

    assert len(result) == 2
