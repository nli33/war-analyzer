"""Tests for war/commanders.py (C3): commander-field parsing, the first-listed-commander rule,
and the battle -> general-perspective inversion. Parser tests use fixtures; the real-page block
at the bottom reuses data/raw/eval_ingest_cache.json (same cache A3/C2 built, gitignored) and is
skipped if that cache isn't present on disk.
"""

import json
from pathlib import Path

import pytest

from war.commanders import (
    CommanderRef,
    GeneralBattleLink,
    extract_commander_fields,
    general_id_from_title,
    invert_to_general_battles,
    parse_commander_field,
    primary_commander,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_CACHE = REPO_ROOT / "data" / "raw" / "eval_ingest_cache.json"


def test_general_id_from_title_simple():
    assert general_id_from_title("Napoleon") == "napoleon"


def test_general_id_from_title_keeps_disambiguator():
    assert (
        general_id_from_title("Lucius Aemilius Paullus (consul 216 BC)")
        == "lucius-aemilius-paullus-consul-216-bc"
    )


def test_parse_commander_field_single_wikilink():
    refs = parse_commander_field("[[Hannibal]]")
    assert refs == [CommanderRef("Hannibal", "Hannibal", "hannibal")]


def test_parse_commander_field_piped_display_alias():
    refs = parse_commander_field("[[Napoleon Bonaparte|Napoleon]]")
    assert refs == [CommanderRef("Napoleon", "Napoleon Bonaparte", "napoleon-bonaparte")]


def test_parse_commander_field_br_separated_preserves_order():
    refs = parse_commander_field("[[Napoleon]]<br>[[Michel Ney|Ney]]")
    assert [r.display_name for r in refs] == ["Napoleon", "Ney"]
    assert refs[1].general_id == "michel-ney"


def test_parse_commander_field_comma_separated():
    refs = parse_commander_field("[[A]], [[B]]")
    assert [r.general_id for r in refs] == ["a", "b"]


def test_parse_commander_field_and_separated():
    refs = parse_commander_field("[[A]] and [[B]]")
    assert [r.general_id for r in refs] == ["a", "b"]


def test_parse_commander_field_strips_decoration_template():
    # {{KIA}} stuck directly on a name with no separator shouldn't merge into the name or
    # produce a bogus second entry.
    refs = parse_commander_field("[[Paullus]]{{KIA}}")
    assert refs == [CommanderRef("Paullus", "Paullus", "paullus")]


def test_parse_commander_field_strips_footnote_template():
    refs = parse_commander_field("[[Hannibal]]{{sfn|Goldsworthy|2001|p=203}}")
    assert refs == [CommanderRef("Hannibal", "Hannibal", "hannibal")]


def test_parse_commander_field_ubl_template_preserves_order():
    refs = parse_commander_field("{{ubl|[[A]]|[[B]]|[[C]]}}")
    assert [r.general_id for r in refs] == ["a", "b", "c"]


def test_parse_commander_field_plainlist_template_with_bold_first_entry():
    raw = "{{plainlist|\n*'''[[Alexander the Great]]'''\n*[[Parmenion]]\n}}"
    refs = parse_commander_field(raw)
    assert [r.display_name for r in refs] == ["Alexander the Great", "Parmenion"]


def test_parse_commander_field_plain_list_with_space_template_name():
    # "Plain list" (two words) is a real Wikipedia template-name variant for Plainlist, seen on
    # Battle of Gaugamela's commander1 field — regression test for C4b's roster crawl, which
    # found it silently dropping every name because only the no-space "plainlist" name was
    # recognized.
    raw = "{{Plain list| * '''[[Alexander the Great]]''' \n* [[Parmenion]]}}"
    refs = parse_commander_field(raw)
    assert [r.display_name for r in refs] == ["Alexander the Great", "Parmenion"]


def test_parse_commander_field_tree_list_hierarchy_keeps_top_commander_first():
    raw = "{{tree list}}\n*[[Julius Caesar]]\n**[[Mark Antony]]\n{{tree list/end}}"
    refs = parse_commander_field(raw)
    assert [r.display_name for r in refs] == ["Julius Caesar", "Mark Antony"]


def test_parse_commander_field_non_wikilinked_name_has_no_general_id():
    refs = parse_commander_field("[[A]]<br>Vergilius (garrison commander of Thapsus)")
    assert refs[0].general_id == "a"
    assert refs[1] == CommanderRef(
        "Vergilius (garrison commander of Thapsus)", wikipedia_title=None, general_id=None
    )


def test_parse_commander_field_empty_value():
    assert parse_commander_field("") == []


def test_parse_commander_field_skips_leading_flag_icon_file_link():
    # Real bug (C6 dev log): a national flag-icon template directly ahead of the name, with no
    # separator the segment splitter breaks on, used to make the File: link itself the parsed
    # "commander" (and a fake roster entry once the field's first-listed name is the icon).
    refs = parse_commander_field(
        "[[File:Royal flag of France.svg|22px]] [[Louis d'Armagnac|Duke of Nemours]]"
    )
    assert refs == [CommanderRef("Duke of Nemours", "Louis d'Armagnac", "louis-d-armagnac")]


def test_parse_commander_field_flag_icon_ahead_of_plain_name():
    refs = parse_commander_field("[[File:Royal flag of France.svg|22px]] Chandieu")
    assert refs == [CommanderRef("Chandieu", wikipedia_title=None, general_id=None)]


def test_parse_commander_field_pure_flag_icon_segment_is_not_a_commander():
    refs = parse_commander_field("[[File:Royal flag of France.svg|22px]]")
    assert refs == []


def test_extract_commander_fields_no_infobox_returns_empty_dict():
    assert extract_commander_fields("no infobox here") == {}


def test_extract_commander_fields_reads_both_sides():
    wikitext = (
        "{{Infobox military conflict\n"
        "| commander1 = [[Hannibal]]\n"
        "| commander2 = [[Lucius Aemilius Paullus (consul 216 BC)|Paullus]]{{KIA}}\n"
        "}}"
    )
    fields = extract_commander_fields(wikitext)
    assert [r.general_id for r in fields["commander1"]] == ["hannibal"]
    assert [r.general_id for r in fields["commander2"]] == ["lucius-aemilius-paullus-consul-216-bc"]


def test_extract_commander_fields_omits_missing_field():
    wikitext = "{{Infobox military conflict\n| commander1 = [[Hannibal]]\n}}"
    fields = extract_commander_fields(wikitext)
    assert "commander1" in fields
    assert "commander2" not in fields


def test_primary_commander_is_first_in_list():
    side = [CommanderRef("A", "A", "a"), CommanderRef("B", "B", "b")]
    assert primary_commander(side) == side[0]


def test_primary_commander_none_when_side_empty():
    assert primary_commander([]) is None


def test_primary_commander_none_when_first_is_not_wikilinked():
    # Known miss, documented on the function: a real first-listed name with no Wikipedia page
    # can't become a roster entry even though a wikilinked co-commander follows it.
    side = [
        CommanderRef("Some Local Chief", wikipedia_title=None, general_id=None),
        CommanderRef("B", "B", "b"),
    ]
    assert primary_commander(side) is None


def test_invert_to_general_battles_both_sides_identifiable():
    side1 = [CommanderRef("Caesar", "Julius Caesar", "julius-caesar")]
    side2 = [CommanderRef("Pompey", "Pompey", "pompey")]
    links = invert_to_general_battles(side1, side2)
    assert links == [
        GeneralBattleLink("julius-caesar", "Caesar", "Julius Caesar", "pompey", "Pompey"),
        GeneralBattleLink("pompey", "Pompey", "Pompey", "julius-caesar", "Caesar"),
    ]


def test_invert_to_general_battles_one_side_identifiable():
    side1 = [CommanderRef("Caesar", "Julius Caesar", "julius-caesar")]
    side2 = [CommanderRef("Local chief", wikipedia_title=None, general_id=None)]
    links = invert_to_general_battles(side1, side2)
    assert links == [
        GeneralBattleLink("julius-caesar", "Caesar", "Julius Caesar", None, None),
    ]


def test_invert_to_general_battles_neither_side_identifiable():
    side1 = [CommanderRef("Local chief", wikipedia_title=None, general_id=None)]
    side2: list[CommanderRef] = []
    assert invert_to_general_battles(side1, side2) == []


# --- identity_resolver threading (E2) --------------------------------------------------------


def test_parse_commander_field_identity_resolver_merges_title():
    resolver = {"Napoleon Bonaparte": "napoleon"}
    refs = parse_commander_field("[[Napoleon Bonaparte|Napoleon]]", resolver)
    assert refs == [CommanderRef("Napoleon", "Napoleon Bonaparte", "napoleon")]


def test_parse_commander_field_identity_resolver_disambiguation_is_unidentified():
    # A linked name whose resolver entry is None (E1 resolved it to a disambiguation page, or to
    # no page at all) is treated as an unidentified commander even though it *is* wikilinked --
    # general_id is None but wikipedia_title is still recorded, unlike a plain unlinked name.
    resolver = {"John Smith": None}
    refs = parse_commander_field("[[John Smith]]", resolver)
    assert refs == [CommanderRef("John Smith", "John Smith", None)]
    assert primary_commander(refs) is None


def test_parse_commander_field_identity_resolver_falls_back_for_unseen_title():
    # A title absent from the resolver (E1's scan never saw it) falls back to the raw slug,
    # same as passing no resolver at all.
    resolver = {"Some Other Title": "some-other-title"}
    refs = parse_commander_field("[[Hannibal]]", resolver)
    assert refs == [CommanderRef("Hannibal", "Hannibal", "hannibal")]


def test_extract_commander_fields_forwards_identity_resolver():
    resolver = {"Napoleon Bonaparte": "napoleon", "Napoleon I": "napoleon"}
    wikitext = (
        "{{Infobox military conflict\n"
        "| commander1 = [[Napoleon Bonaparte]]\n"
        "| commander2 = [[Napoleon I]]\n"
        "}}"
    )
    fields = extract_commander_fields(wikitext, resolver)
    assert fields["commander1"][0].general_id == "napoleon"
    assert fields["commander2"][0].general_id == "napoleon"


@pytest.mark.skipif(not EVAL_CACHE.exists(), reason="requires data/raw/eval_ingest_cache.json")
@pytest.mark.parametrize(
    "title,expected_general,expected_opponent",
    [
        ("Battle of Pharsalus", "julius-caesar", "pompey"),
        ("Battle of Thapsus", "julius-caesar", "quintus-caecilius-metellus-pius-scipio-nasica"),
        ("Battle of Munda", "julius-caesar", "gnaeus-pompeius-magnus-son-of-pompey"),
        ("Battle of Issus", "alexander-the-great", "darius-iii"),
    ],
)
def test_real_wikipedia_pages_primary_commanders(title, expected_general, expected_opponent):
    cache = json.loads(EVAL_CACHE.read_text(encoding="utf-8"))
    fields = extract_commander_fields(cache[title])
    links = invert_to_general_battles(fields.get("commander1", []), fields.get("commander2", []))
    by_general = {link.general_id: link for link in links}
    assert expected_general in by_general
    assert by_general[expected_general].opponent_general_id == expected_opponent


@pytest.mark.skipif(not EVAL_CACHE.exists(), reason="requires data/raw/eval_ingest_cache.json")
def test_real_wikipedia_page_non_wikilinked_trailing_commander_is_not_primary():
    # Battle of Thapsus's commander2 field ends with a plain-text name ("Vergilius..."); it must
    # not affect the primary-commander pick (still the first, wikilinked, name).
    cache = json.loads(EVAL_CACHE.read_text(encoding="utf-8"))
    fields = extract_commander_fields(cache["Battle of Thapsus"])
    side2 = fields["commander2"]
    assert side2[-1].general_id is None
    assert primary_commander(side2).general_id == "quintus-caecilius-metellus-pius-scipio-nasica"
