"""Tests for the infobox wikitext parser (war/scrape.py). No network calls — fixtures only."""

from war.scrape import parse_military_infobox

# Trimmed from enwiki's actual "Battle of Cannae" infobox as of research time, with
# refs/templates left in deliberately to exercise the cleanup regexes.
CANNAE_WIKITEXT = """
{{Infobox military conflict
| conflict    = Battle of Cannae
| partof      = the [[Second Punic War]]
| date        = 2 August 216 BC
| place       = Cannae, Apulia, southeast Italy
| result      = Decisive Carthaginian victory<ref>Goldsworthy 2001, p. 215</ref>
| combatant1  = [[Carthage]]
| combatant2  = [[Roman Republic]]
| commander1  = [[Hannibal]]
| commander2  = [[Lucius Aemilius Paullus (consul 216 BC)|Paullus]]{{KIA}}
| strength1   = 50,000{{sfn|Goldsworthy|2001|p=203}}
| strength2   = 86,400
| casualties1 = 5,700–8,000
| casualties2 = 55,000 killed or captured<ref name="livy"/>
}}
'''Cannae''' was a battle fought during the [[Second Punic War]].
"""


def test_extracts_known_fields():
    fields = parse_military_infobox(CANNAE_WIKITEXT)
    assert fields["conflict"] == "Battle of Cannae"
    assert fields["date"] == "2 August 216 BC"
    assert fields["combatant1"] == "Carthage"
    assert fields["combatant2"] == "Roman Republic"
    assert fields["commander1"] == "Hannibal"
    assert fields["strength1"] == "50,000"
    assert fields["strength2"] == "86,400"
    assert fields["casualties1"] == "5,700–8,000"


def test_strips_refs_and_templates():
    fields = parse_military_infobox(CANNAE_WIKITEXT)
    assert "ref" not in fields["result"].lower()
    assert "{{" not in fields["strength1"]
    assert "sfn" not in fields["strength1"]


def test_resolves_wikilinks_to_display_text():
    fields = parse_military_infobox(CANNAE_WIKITEXT)
    assert fields["commander2"].startswith("Paullus")


def test_no_infobox_returns_empty():
    assert parse_military_infobox("Just some plain article text, no template here.") == {}
