"""Tests for war/rules.py's three ingestion rules (PROGRESS.md task B2)."""

from war.rules import (
    CincTable,
    decisiveness_from_result,
    era_for_year,
    load_cinc_table,
    outcome_from_result,
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


def test_era_for_year_boundaries():
    assert era_for_year(-334) == "Ancient"
    assert era_for_year(499) == "Ancient"
    assert era_for_year(500) == "Medieval"
    assert era_for_year(1499) == "Medieval"
    assert era_for_year(1500) == "Early Modern"
    assert era_for_year(1791) == "Early Modern"
    assert era_for_year(1792) == "Napoleonic"
    assert era_for_year(1815) == "Napoleonic"
    assert era_for_year(1816) == "Industrial"
    assert era_for_year(1913) == "Industrial"
    assert era_for_year(1914) == "WWII"
    assert era_for_year(1944) == "WWII"


def test_era_for_year_post_1945_is_modern_not_wwii():
    # H1: the original table had no upper bound on "WWII" at all, so 2001-2017 battles (Iraq,
    # Libya, Syria, Macedonia) were landing in it too.
    assert era_for_year(1945) == "Modern"
    assert era_for_year(2001) == "Modern"
    assert era_for_year(2011) == "Modern"
    assert era_for_year(2017) == "Modern"


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


def test_outcome_from_result_no_text_is_unresolved():
    assert outcome_from_result(None, "France", "Britain") == (None, None)


def test_outcome_from_result_draw_keywords():
    assert outcome_from_result("Inconclusive", "France", "Britain") == ("Draw", "Draw")
    assert outcome_from_result("Stalemate", "France", "Britain") == ("Draw", "Draw")


def test_outcome_from_result_direct_substring_match():
    assert outcome_from_result("Roman victory", "Roman Republic", "Gauls") == ("Win", "Loss")


def test_outcome_from_result_side2_wins_via_substring():
    assert outcome_from_result("Confederate victory", "United States", "Confederate States") == (
        "Loss",
        "Win",
    )


def test_outcome_from_result_irregular_demonym_table():
    assert outcome_from_result("French victory", "France", "Great Britain") == ("Win", "Loss")
    assert outcome_from_result("British victory", "France", "Britain") == ("Loss", "Win")


def test_outcome_from_result_unmatched_demonym_is_unresolved():
    assert outcome_from_result("Zanzibari victory", "France", "Great Britain") == (None, None)


def test_outcome_from_result_no_victory_word_is_unresolved():
    assert outcome_from_result("Ceasefire agreed", "France", "Great Britain") == (None, None)


def test_outcome_from_result_united_kingdom_official_name():
    # F2: "British" has no word in common with "United Kingdom" at all -- not even a stopword
    # overlap -- since neither "united" nor "kingdom" stems to "britain". Regression for the
    # single biggest ambiguous_side_match loss cause F1 found.
    assert outcome_from_result("British victory", "United Kingdom", "France") == ("Win", "Loss")
    assert outcome_from_result("British victory", "France", "United Kingdom") == ("Loss", "Win")


def test_outcome_from_result_united_states_official_name():
    assert outcome_from_result("American victory", "United States", "Mexico") == ("Win", "Loss")


def test_outcome_from_result_trailing_victory_for_name():
    # "Victory for X" / "Victory of X" put the winning side's name *after* "victory" -- the
    # leading-adjective capture sees nothing before it. Matched as a literal name, not a
    # demonym, since this form is usually a person or faction name, not a country.
    assert outcome_from_result(
        "Victory for Philip II", "Supporters of António Prior of Crato", "Supporters of Philip II"
    ) == ("Loss", "Win")
    assert outcome_from_result(
        "Victory of Antiochus Hierax", "Seleucid Empire", "Antiochus Hierax; Kingdom of Pontus"
    ) == ("Loss", "Win")


def test_outcome_from_result_trailing_victory_name_stops_at_bullet_separator():
    # "Victory for Drenthe * Death of Otto II of Lippe" -- the trailing clause after "*" isn't
    # part of the winning side's name and must not leak into the match.
    assert outcome_from_result(
        "Victory for Drenthe * Death of Otto II of Lippe", "Bishopric of Utrecht", "Drenthe"
    ) == ("Loss", "Win")


def test_outcome_from_result_trailing_victory_name_no_match_is_unresolved():
    assert outcome_from_result("Victory for Kassa Hailu", None, None) == (None, None)


def test_outcome_from_result_generic_victory_word_stays_unresolved():
    # "Government" is a stopword with no side-identifying content and no "for"/"of" clause to
    # fall back on -- must stay unresolved rather than guessing.
    assert outcome_from_result("Government victory", "Rebels", "National Army") == (None, None)
