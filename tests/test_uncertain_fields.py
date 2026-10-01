"""Tests for war/uncertain_fields.py (C5): the uncertain-row queue and the bounded LLM pass's
pure logic (queue building, response parsing, sanity bounds). The actual `claude -p` call lives
in scripts/resolve_uncertain_fields.py and isn't exercised here, same as war/scrape.py's network
calls are mocked rather than hit for real.
"""

from war.uncertain_fields import (
    QueueItem,
    build_prompt,
    build_queue,
    extract_results,
    sanity_clean,
)

_WIKITEXT_WITH_ROSTER_GENERAL = """
{{Infobox military conflict
|date = 1800
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = 10,000
|strength2 = Kamensky's division
|casualties1 = Unknown
|casualties2 = 2,000, 3 guns
}}
"""

_WIKITEXT_NO_ROSTER_GENERAL = """
{{Infobox military conflict
|date = 1800
|commander1 = [[General Three]]
|commander2 = [[General Four]]
|strength1 = Unknown
|strength2 = 6,000
}}
"""

_WIKITEXT_ALL_PARSEABLE = """
{{Infobox military conflict
|date = 1800
|commander1 = [[General One]]
|commander2 = [[General Two]]
|strength1 = 10,000
|strength2 = 6,000
}}
"""


# --- build_queue -------------------------------------------------------------------------------


def test_build_queue_only_includes_battles_touching_a_roster_general():
    cache = {
        "Battle A": _WIKITEXT_WITH_ROSTER_GENERAL,
        "Battle B": _WIKITEXT_NO_ROSTER_GENERAL,
    }
    queue = build_queue(["Battle A", "Battle B"], cache, roster_ids={"general-one"})
    battles = {item.battle_title for item in queue}
    assert battles == {"Battle A"}


def test_build_queue_skips_fields_that_already_parse():
    cache = {"Battle A": _WIKITEXT_ALL_PARSEABLE}
    queue = build_queue(["Battle A"], cache, roster_ids={"general-one"})
    assert queue == []


def test_build_queue_finds_unparseable_fields_with_and_without_digits():
    cache = {"Battle A": _WIKITEXT_WITH_ROSTER_GENERAL}
    queue = build_queue(["Battle A"], cache, roster_ids={"general-one"})
    by_field = {item.field: item for item in queue}
    assert set(by_field) == {"strength2", "casualties1"}
    assert by_field["strength2"].has_digit is False  # "Kamensky's division"
    assert by_field["casualties1"].has_digit is False  # "Unknown"


def test_build_queue_skips_pages_missing_from_the_wikitext_cache():
    queue = build_queue(["Not Cached"], {}, roster_ids={"general-one"})
    assert queue == []


def test_build_queue_order_is_deterministic_and_respects_max_rows():
    cache = {
        "Battle Z": _WIKITEXT_WITH_ROSTER_GENERAL,
        "Battle A": _WIKITEXT_WITH_ROSTER_GENERAL,
    }
    full = build_queue(["Battle Z", "Battle A"], cache, roster_ids={"general-one"})
    assert [item.battle_title for item in full] == ["Battle A", "Battle A", "Battle Z", "Battle Z"]
    assert [item.id for item in full] == [0, 1, 2, 3]

    truncated = build_queue(["Battle Z", "Battle A"], cache, roster_ids={"general-one"}, max_rows=2)
    assert len(truncated) == 2
    assert [item.battle_title for item in truncated] == ["Battle A", "Battle A"]


# --- QueueItem properties ------------------------------------------------------------------


def test_queue_item_properties():
    item = QueueItem(id=0, battle_title="Battle A", field="casualties2", raw_text="2,000, 3 guns")
    assert item.has_digit is True
    assert item.is_casualties is True
    assert item.side == "2"

    strength_item = QueueItem(id=1, battle_title="Battle A", field="strength1", raw_text="Unknown")
    assert strength_item.has_digit is False
    assert strength_item.is_casualties is False
    assert strength_item.side == "1"


# --- build_prompt / extract_results ---------------------------------------------------------


def test_build_prompt_embeds_every_item_as_json():
    items = [QueueItem(id=5, battle_title="Battle A", field="strength1", raw_text="about 10k men")]
    prompt = build_prompt(items)
    assert '"id": 5' in prompt
    assert "Battle A" in prompt
    assert "about 10k men" in prompt


def test_extract_results_reads_structured_output():
    payload = {"structured_output": {"results": [{"id": 1, "value": 500}, {"id": 2, "value": None}]}}
    assert extract_results(payload) == {1: 500, 2: None}


def test_extract_results_missing_structured_output_is_empty():
    assert extract_results({"is_error": True}) == {}


def test_extract_results_skips_malformed_rows():
    payload = {"structured_output": {"results": [{"id": "not-an-int"}, {"id": 3, "value": 10}]}}
    assert extract_results(payload) == {3: 10}


# --- sanity_clean --------------------------------------------------------------------------


def test_sanity_clean_passes_none_through():
    item = QueueItem(0, "Battle A", "strength1", "text")
    assert sanity_clean(item, None, {}) is None


def test_sanity_clean_rejects_negative():
    item = QueueItem(0, "Battle A", "strength1", "text")
    assert sanity_clean(item, -5, {}) is None


def test_sanity_clean_rejects_implausibly_large():
    item = QueueItem(0, "Battle A", "strength1", "text")
    assert sanity_clean(item, 50_000_000, {}) is None


def test_sanity_clean_keeps_plausible_strength():
    item = QueueItem(0, "Battle A", "strength1", "text")
    assert sanity_clean(item, 10_000, {}) == 10_000


def test_sanity_clean_rejects_casualties_far_above_known_strength():
    item = QueueItem(0, "Battle A", "casualties1", "text")
    strength_lookup = {("Battle A", "strength1"): 1_000}
    assert sanity_clean(item, 10_000, strength_lookup) is None


def test_sanity_clean_keeps_casualties_within_ratio_of_known_strength():
    item = QueueItem(0, "Battle A", "casualties1", "text")
    strength_lookup = {("Battle A", "strength1"): 1_000}
    assert sanity_clean(item, 2_500, strength_lookup) == 2_500


def test_sanity_clean_keeps_casualties_when_strength_unknown():
    item = QueueItem(0, "Battle A", "casualties1", "text")
    assert sanity_clean(item, 1_000_000, {}) == 1_000_000
