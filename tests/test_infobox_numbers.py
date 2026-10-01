"""Tests for war/infobox_numbers.py (C2). One test per named failure mode from PROGRESS.md's
C2 task plus A3's dev-log findings, then integration tests against real cached infobox text
pulled from Wikipedia (Waterloo/Borodino/Pharsalus — see data/raw/eval_ingest_cache.json) so the
pipeline is checked against genuinely messy wikitext, not just hand-written fixtures."""

import json
from pathlib import Path

import pytest

from war.infobox_numbers import ExtractedNumber, extract_numeric_field, extract_strength_and_casualties

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_CACHE = REPO_ROOT / "data" / "raw" / "eval_ingest_cache.json"


# --- ranges ------------------------------------------------------------------------------------


def test_range_hyphen_gives_point_low_high():
    assert extract_numeric_field("5,700-8,000") == ExtractedNumber(point=6850, low=5700, high=8000)


def test_range_en_dash():
    assert extract_numeric_field("5,700–8,000") == ExtractedNumber(point=6850, low=5700, high=8000)


def test_range_word_to():
    assert extract_numeric_field("5,700 to 8,000") == ExtractedNumber(point=6850, low=5700, high=8000)


def test_range_low_above_high_in_source_is_reordered():
    # Defensive: a malformed "8,000-5,700" source order shouldn't invert low/high.
    assert extract_numeric_field("8,000-5,700") == ExtractedNumber(point=6850, low=5700, high=8000)


# --- "c."/"~" approximate markers ---------------------------------------------------------------


def test_c_dot_prefix():
    assert extract_numeric_field("c. 50,000").point == 50000


def test_tilde_prefix():
    assert extract_numeric_field("~50,000").point == 50000


def test_approximately_template():
    assert extract_numeric_field("{{approximately|68,000}}").point == 68000


def test_circa_template_with_arg():
    assert extract_numeric_field("{{circa|30,000}}").point == 30000


# --- k/m suffixes --------------------------------------------------------------------------------


def test_k_suffix():
    assert extract_numeric_field("50k").point == 50_000


def test_m_suffix():
    assert extract_numeric_field("2.5m").point == 2_500_000


def test_million_word():
    assert extract_numeric_field("2.5 million").point == 2_500_000


def test_thousand_word():
    assert extract_numeric_field("40 thousand").point == 40_000


# --- multi-segment fields (headline + trailing equipment/extra clause) --------------------------


def test_multi_segment_headline_wins_over_trailing_equipment():
    assert extract_numeric_field("40,000\n40+ cannon") == ExtractedNumber(point=40000)


def test_multi_segment_headline_wins_over_citation_bracket():
    assert extract_numeric_field("35,000[1]\n40+ cannon") == ExtractedNumber(point=35000)


def test_equipment_only_field_returns_null():
    # Nothing but an equipment count — not a troop/casualty number at all.
    assert extract_numeric_field("20 ships").point is None


# --- plainlist/ubl templates ----------------------------------------------------------------------


def test_plainlist_template_with_no_stated_total_sums_items():
    raw = "{{plainlist|\n* 7,000 infantry\n* 3,000 cavalry\n}}"
    assert extract_numeric_field(raw) == ExtractedNumber(point=10000)


def test_ubl_template_pipe_separated():
    raw = "{{ubl|212 killed|1,252 wounded|250 missing}}"
    assert extract_numeric_field(raw) == ExtractedNumber(point=1714)


def test_ubl_breakdown_after_a_stated_total_is_not_double_counted():
    # The common real shape: a headline total, then a {{ubl|...}} breakdown of that same total.
    raw = "26,000-27,000{{Ubl|{{*}}25,000 killed or wounded|{{*}}8,000 captured}}"
    assert extract_numeric_field(raw) == ExtractedNumber(point=26500, low=26000, high=27000)


def test_plainlist_does_not_crash_on_nested_sfn_citations():
    # Regression guard for the truncation bug this task fixed: a {{plainlist|...}} containing
    # its own nested {{sfn|...}} used to confuse the old "}}"-lookahead param splitter. These are
    # alternative historian estimates for the same figure, not parts of a whole — the first
    # (headline-shaped, bare) one wins, matching the real {{efn|...}} case this is based on.
    raw = "{{plainlist|\n* 71,947{{sfn|Clodfelter|2017|p=170}}\n* 72,000{{sfn|Bodart|1908|p=487}}\n}}"
    assert extract_numeric_field(raw).point == 71947


# --- killed/wounded/captured sums -----------------------------------------------------------------


def test_killed_wounded_captured_no_total_stated_sums():
    raw = "500 killed\n1,200 wounded\n300 captured"
    assert extract_numeric_field(raw) == ExtractedNumber(point=2000)


def test_combined_category_phrase_is_treated_as_the_total_not_a_part():
    # "killed, wounded or missing" names several categories together -> it IS the total.
    raw = "30,000-42,000 killed, wounded or missing\n50 generals"
    assert extract_numeric_field(raw) == ExtractedNumber(point=36000, low=30000, high=42000)


# --- per-nation breakdowns -------------------------------------------------------------------------


def test_per_nation_breakdown_no_total_stated_sums():
    raw = "Britain: 20,000\nFrance: 15,000"
    assert extract_numeric_field(raw) == ExtractedNumber(point=35000)


def test_per_nation_breakdown_after_a_stated_total_is_not_double_counted():
    raw = "Total: 118,000-120,000\n91,000 infantry\n21,500 cavalry\n7,500 gunners"
    assert extract_numeric_field(raw) == ExtractedNumber(point=119000, low=118000, high=120000)


# --- qualitative words become null --------------------------------------------------------------


@pytest.mark.parametrize("text", ["Heavy", "Unknown", "Light", "Minimal", ""])
def test_qualitative_text_returns_null(text):
    assert extract_numeric_field(text) == ExtractedNumber(None)


def test_qualitative_segment_alongside_a_real_number_keeps_the_number():
    raw = "Heavy losses[2]\n3000 sick and wounded[1]"
    assert extract_numeric_field(raw) == ExtractedNumber(point=3000)


# --- footnote/citation templates don't pollute the parse ------------------------------------------


def test_sfn_citation_template_is_dropped_not_summed():
    raw = "50,000{{sfn|Goldsworthy|2001|p=203}}"
    assert extract_numeric_field(raw) == ExtractedNumber(point=50000)


def test_efn_with_nested_alternative_estimates_is_dropped_whole():
    # The alternative historian estimates inside {{efn|...}} must not get summed in.
    raw = "72,000-73,000{{efn|\n* 71,947{{sfn|a}}\n* 72,000{{sfn|b}}\n* 73,000{{sfn|c}}\n}}"
    assert extract_numeric_field(raw) == ExtractedNumber(point=72500, low=72000, high=73000)


def test_ref_tag_with_nested_cite_template_is_dropped():
    raw = '30,000-39,000<ref>{{Cite web |title=x |url=https://example.com}}</ref>'
    assert extract_numeric_field(raw) == ExtractedNumber(point=34500, low=30000, high=39000)


# --- extract_strength_and_casualties / infobox integration ---------------------------------------


def test_extract_strength_and_casualties_no_infobox_returns_empty():
    assert extract_strength_and_casualties("no infobox on this page at all") == {}


def test_extract_strength_and_casualties_reads_all_four_fields():
    wikitext = (
        "{{Infobox military conflict\n"
        "| strength1 = 50,000{{sfn|a}}\n"
        "| strength2 = 86,400\n"
        "| casualties1 = 5,700-8,000\n"
        "| casualties2 = 55,000 killed or captured\n"
        "}}"
    )
    result = extract_strength_and_casualties(wikitext)
    assert result["strength1"] == ExtractedNumber(point=50000)
    assert result["strength2"] == ExtractedNumber(point=86400)
    assert result["casualties1"] == ExtractedNumber(point=6850, low=5700, high=8000)
    assert result["casualties2"].point == 55000


@pytest.mark.skipif(not EVAL_CACHE.exists(), reason="requires data/raw/eval_ingest_cache.json")
@pytest.mark.parametrize(
    "title,field,expected",
    [
        ("Battle of Waterloo", "strength1", ExtractedNumber(point=72500, low=72000, high=73000)),
        ("Battle of Waterloo", "strength2", ExtractedNumber(point=119000, low=118000, high=120000)),
        ("Battle of Waterloo", "casualties1", ExtractedNumber(point=26500, low=26000, high=27000)),
        ("Battle of Waterloo", "casualties2", ExtractedNumber(point=24000)),
        ("Battle of Borodino", "casualties1", ExtractedNumber(point=36000, low=30000, high=42000)),
        ("Battle of Pharsalus", "strength1", ExtractedNumber(point=23000)),
        ("Battle of Pharsalus", "casualties1", ExtractedNumber(point=700, low=200, high=1200)),
    ],
)
def test_real_wikipedia_pages(title, field, expected):
    cache = json.loads(EVAL_CACHE.read_text(encoding="utf-8"))
    assert extract_strength_and_casualties(cache[title])[field] == expected
