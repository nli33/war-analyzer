"""Tests for war/uncertain_outcomes.py (F3): the unresolved-outcome queue and the bounded LLM
pass's pure logic (queue building, response parsing, sanity bounds). The actual `claude -p` call
lives in scripts/resolve_uncertain_outcomes.py and isn't exercised here, same as war/scrape.py's
network calls are mocked rather than hit for real.
"""

from war.uncertain_outcomes import (
    QueueItem,
    build_prompt,
    build_queue,
    extract_results,
    sanity_clean,
)

_WIKITEXT_RESOLVED = """
{{Infobox military conflict
|date = 1800
|result = Roman victory
|combatant1 = Roman Republic
|combatant2 = Gauls
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""

_WIKITEXT_AMBIGUOUS_WITH_SIDE_TEXT = """
{{Infobox military conflict
|date = 1800
|result = Government victory
|combatant1 = Royalists
|combatant2 = Loyalists
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""

_WIKITEXT_AMBIGUOUS_NO_SIDE_TEXT = """
{{Infobox military conflict
|date = 1800
|result = Government victory
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""

_WIKITEXT_NO_RESULT_FIELD = """
{{Infobox military conflict
|date = 1800
|combatant1 = Royalists
|combatant2 = Loyalists
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""

_WIKITEXT_NO_YEAR = """
{{Infobox military conflict
|result = Government victory
|combatant1 = Royalists
|combatant2 = Loyalists
|commander1 = [[General One]]
|commander2 = [[General Two]]
}}
"""

_WIKITEXT_NO_COMMANDER = """
{{Infobox military conflict
|date = 1800
|result = Government victory
|combatant1 = Royalists
|combatant2 = Loyalists
}}
"""


# --- build_queue -------------------------------------------------------------------------------


def test_build_queue_skips_battles_whose_outcome_already_resolves():
    cache = {"Battle A": _WIKITEXT_RESOLVED}
    assert build_queue(["Battle A"], cache) == []


def test_build_queue_includes_ambiguous_outcome_with_side_text():
    cache = {"Battle A": _WIKITEXT_AMBIGUOUS_WITH_SIDE_TEXT}
    queue = build_queue(["Battle A"], cache)
    assert len(queue) == 1
    item = queue[0]
    assert item.battle_title == "Battle A"
    assert item.result_text == "Government victory"
    assert item.combatant1_text == "Royalists"
    assert item.has_side_text is True


def test_build_queue_includes_ambiguous_outcome_with_no_side_text_but_flags_it():
    cache = {"Battle A": _WIKITEXT_AMBIGUOUS_NO_SIDE_TEXT}
    queue = build_queue(["Battle A"], cache)
    assert len(queue) == 1
    assert queue[0].has_side_text is False


def test_build_queue_skips_no_result_field():
    cache = {"Battle A": _WIKITEXT_NO_RESULT_FIELD}
    assert build_queue(["Battle A"], cache) == []


def test_build_queue_skips_no_year():
    cache = {"Battle A": _WIKITEXT_NO_YEAR}
    assert build_queue(["Battle A"], cache) == []


def test_build_queue_skips_no_wikilinked_commander():
    cache = {"Battle A": _WIKITEXT_NO_COMMANDER}
    assert build_queue(["Battle A"], cache) == []


def test_build_queue_skips_pages_missing_from_the_wikitext_cache():
    assert build_queue(["Not Cached"], {}) == []


def test_build_queue_order_is_deterministic_and_respects_max_rows():
    cache = {
        "Battle Z": _WIKITEXT_AMBIGUOUS_WITH_SIDE_TEXT,
        "Battle A": _WIKITEXT_AMBIGUOUS_WITH_SIDE_TEXT,
    }
    full = build_queue(["Battle Z", "Battle A"], cache)
    assert [item.battle_title for item in full] == ["Battle A", "Battle Z"]
    assert [item.id for item in full] == [0, 1]

    truncated = build_queue(["Battle Z", "Battle A"], cache, max_rows=1)
    assert len(truncated) == 1
    assert truncated[0].battle_title == "Battle A"


# --- QueueItem properties ------------------------------------------------------------------


def test_queue_item_has_side_text():
    with_text = QueueItem(0, "Battle A", "Government victory", "Royalists", None)
    assert with_text.has_side_text is True

    without_text = QueueItem(1, "Battle A", "Government victory", None, None)
    assert without_text.has_side_text is False


# --- build_prompt / extract_results ---------------------------------------------------------


def test_build_prompt_embeds_every_item_as_json():
    items = [QueueItem(5, "Battle A", "Government victory", "Royalists", "Loyalists")]
    prompt = build_prompt(items)
    assert '"id": 5' in prompt
    assert "Battle A" not in prompt  # title isn't part of the model's input, only the text fields
    assert "Government victory" in prompt
    assert "Royalists" in prompt


def test_extract_results_reads_structured_output():
    payload = {"structured_output": {"results": [{"id": 1, "winner": "side1"}, {"id": 2, "winner": None}]}}
    assert extract_results(payload) == {1: "side1", 2: None}


def test_extract_results_missing_structured_output_is_empty():
    assert extract_results({"is_error": True}) == {}


def test_extract_results_skips_malformed_rows():
    payload = {"structured_output": {"results": [{"id": "not-an-int"}, {"id": 3, "winner": "draw"}]}}
    assert extract_results(payload) == {3: "draw"}


# --- sanity_clean --------------------------------------------------------------------------


def test_sanity_clean_keeps_allowed_values():
    assert sanity_clean("side1") == "side1"
    assert sanity_clean("side2") == "side2"
    assert sanity_clean("draw") == "draw"


def test_sanity_clean_rejects_unresolvable_and_null():
    assert sanity_clean("unresolvable") is None
    assert sanity_clean(None) is None


def test_sanity_clean_rejects_malformed_value():
    assert sanity_clean("Side 1") is None
    assert sanity_clean("") is None
