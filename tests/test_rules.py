"""Tests for war/rules.py's three ingestion rules (PROGRESS.md task B2)."""

from war.rules import (
    CincTable,
    decisiveness_from_result,
    load_cinc_table,
    resource_backing_tier,
    tech_era_tier_for_year,
)


def test_tech_era_tier_boundaries():
    assert tech_era_tier_for_year(-334) == 1  # Alexander, well pre-gunpowder
    assert tech_era_tier_for_year(1399) == 1
    assert tech_era_tier_for_year(1400) == 2  # gunpowder era begins
    assert tech_era_tier_for_year(1699) == 2
    assert tech_era_tier_for_year(1700) == 3  # standardized musket/artillery warfare
    assert tech_era_tier_for_year(1859) == 3
    assert tech_era_tier_for_year(1860) == 4  # rail/telegraph logistics
    assert tech_era_tier_for_year(1913) == 4
    assert tech_era_tier_for_year(1914) == 5  # mechanised warfare
    assert tech_era_tier_for_year(1945) == 5


def test_resource_backing_tier_uses_era_default_before_cinc_start():
    # 1815 predates COW CINC (starts 1816) even with a country/table supplied.
    table = CincTable(by_country_year={("FRN", 1815): 0.2}, by_year={1815: [0.2, 0.05]})
    assert resource_backing_tier(1815, "Napoleonic", "FRN", table) == 4


def test_resource_backing_tier_era_default_without_country_or_table():
    assert resource_backing_tier(1900, "Industrial") == 3
    assert resource_backing_tier(1200, "Medieval") == 2


def test_resource_backing_tier_cinc_quintile_rank():
    # Five states spanning the full spread; USA's 0.5 is the top value -> tier 5.
    year_values = [0.01, 0.05, 0.1, 0.2, 0.5]
    table = CincTable(
        by_country_year={("USA", 1900): 0.5, ("MNC", 1900): 0.01},
        by_year={1900: year_values},
    )
    assert resource_backing_tier(1900, "Industrial", "USA", table) == 5
    assert resource_backing_tier(1900, "Industrial", "MNC", table) == 1


def test_resource_backing_tier_falls_back_when_country_not_in_table():
    table = CincTable(by_country_year={("USA", 1900): 0.5}, by_year={1900: [0.5]})
    assert resource_backing_tier(1900, "Industrial", "FRN", table) == 3


def test_load_cinc_table(tmp_path):
    csv_path = tmp_path / "cinc.csv"
    csv_path.write_text(
        "stateabb,ccode,year,milex,milper,irst,pec,tpop,upop,cinc,version\n"
        "USA,2,1900,100,10,10,10,100,10,.3,2025\n"
        "FRN,220,1900,50,5,5,5,50,5,.1,2025\n"
    )
    table = load_cinc_table(csv_path)
    assert table.by_country_year[("USA", 1900)] == 0.3
    assert table.by_country_year[("FRN", 1900)] == 0.1
    assert sorted(table.by_year[1900]) == [0.1, 0.3]


def test_decisiveness_draw_is_always_none():
    assert decisiveness_from_result("Decisive victory", "Draw") is None
    assert decisiveness_from_result(None, "Win") is None


def test_decisiveness_decisive_keyword_is_rout_for_win_or_loss():
    assert decisiveness_from_result("Decisive Carthaginian victory", "Win") == "Rout"
    assert decisiveness_from_result("Decisive Carthaginian victory", "Loss") == "Rout"


def test_decisiveness_does_not_confuse_indecisive_with_decisive():
    assert decisiveness_from_result("Indecisive, stalemate", "Win") == "Tactical"


def test_decisiveness_rout_keyword_variants():
    assert decisiveness_from_result("French army routed", "Win") == "Rout"
    assert decisiveness_from_result("Annihilation of the defenders", "Win") == "Rout"
    assert decisiveness_from_result("Garrison destroyed", "Loss") == "Rout"


def test_decisiveness_pyrrhic_and_strategic_only_apply_to_win():
    assert decisiveness_from_result("Pyrrhic victory for the Allies", "Win") == "Pyrrhic"
    assert decisiveness_from_result("Pyrrhic victory for the Allies", "Loss") is None
    assert decisiveness_from_result("Strategic Soviet victory", "Win") == "Strategic"
    assert decisiveness_from_result("Strategic Soviet victory", "Loss") is None


def test_decisiveness_plain_victory_defaults_to_tactical():
    assert decisiveness_from_result("American victory", "Win") == "Tactical"
