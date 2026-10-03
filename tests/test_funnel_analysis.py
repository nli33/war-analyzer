"""Tests for scripts/funnel_analysis.py (F1): classifying a candidate title's drop-out stage."""

from scripts.funnel_analysis import (
    STAGE_NO_COMMANDER,
    STAGE_NO_INFOBOX,
    STAGE_NO_OUTCOME,
    STAGE_NO_YEAR,
    STAGE_NOT_FETCHED,
    STAGE_PRODUCED,
    classify_title,
    run_funnel,
)

_FULL_WIKITEXT = """
{{Infobox military conflict
|date = 2 September 31 BC
|result = Decisive Roman victory
|combatant1 = Roman Republic
|combatant2 = Gauls
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = 10,000
|strength2 = 6,000
}}
"""


def test_classify_title_not_fetched():
    result = classify_title(None)
    assert result.stage == STAGE_NOT_FETCHED


def test_classify_title_no_infobox():
    result = classify_title("just some prose, no infobox here")
    assert result.stage == STAGE_NO_INFOBOX


def test_classify_title_no_year_missing_date_field():
    wikitext = """
{{Infobox military conflict
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_YEAR
    assert result.reason == "no_date_field"


def test_classify_title_no_year_unparseable_date_field():
    wikitext = """
{{Infobox military conflict
|date = 4th century BC
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_YEAR
    assert result.reason == "date_field_unparseable"


def test_classify_title_no_commander_fields_at_all():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = French victory
|combatant1 = France
|combatant2 = Britain
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_COMMANDER
    assert result.reason == "no_commander_fields"


def test_classify_title_commander_not_wikilinked():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = French victory
|combatant1 = France
|combatant2 = Britain
|commander1 = General One (unlinked)
|commander2 = General Two (unlinked)
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_COMMANDER
    assert result.reason == "first_commander_not_wikilinked"


def test_classify_title_no_result_field():
    wikitext = """
{{Infobox military conflict
|date = 1800
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_OUTCOME
    assert result.reason == "no_result_field"


def test_classify_title_result_text_ambiguous():
    wikitext = """
{{Infobox military conflict
|date = 1800
|result = Allied victory
|combatant1 = France
|combatant2 = Britain
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""
    result = classify_title(wikitext)
    assert result.stage == STAGE_NO_OUTCOME
    assert result.reason == "ambiguous_side_match"


def test_classify_title_produced_row_with_usable_strength():
    result = classify_title(_FULL_WIKITEXT)
    assert result.stage == STAGE_PRODUCED
    assert result.has_usable_strength is True


def test_classify_title_produced_row_without_usable_strength():
    wikitext = _FULL_WIKITEXT.replace("|strength1 = 10,000\n", "")
    result = classify_title(wikitext)
    assert result.stage == STAGE_PRODUCED
    assert result.has_usable_strength is False


def test_run_funnel_counts_and_examples():
    titles = ["Fetched", "Missing", "No Infobox"]
    cache = {"Fetched": _FULL_WIKITEXT, "No Infobox": "just prose"}
    report = run_funnel(titles, cache)
    assert report["total_candidate_titles"] == 3
    assert report["produced_row_usable_strength"] == 1
    stage_dropped = {row["stage"]: row["dropped_here"] for row in report["funnel"]}
    assert stage_dropped[STAGE_NOT_FETCHED] == 1
    assert stage_dropped[STAGE_NO_INFOBOX] == 1
    reasons = {(entry["stage"], entry["reason"]): entry["count"] for entry in report["loss_reasons"]}
    assert reasons[(STAGE_NOT_FETCHED, "page_not_in_cache")] == 1
    assert reasons[(STAGE_NO_INFOBOX, "no_military_conflict_infobox")] == 1
