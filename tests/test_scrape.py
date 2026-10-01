"""Tests for war/scrape.py. Parser tests use fixtures only; batch-fetch tests mock urlopen —
no real network calls."""

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

from war.scrape import fetch_wikitext_batch, parse_military_infobox

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


def _query_response(pages):
    body = json.dumps({"query": {"pages": pages}}).encode()
    return BytesIO(body)


def test_fetch_wikitext_batch_parses_multi_page_response():
    pages = [
        {"title": "Battle of Cannae", "revisions": [{"slots": {"main": {"content": "AAA"}}}]},
        {"title": "Battle of Zama", "revisions": [{"slots": {"main": {"content": "BBB"}}}]},
        {"title": "Nonexistent Battle", "missing": True},
    ]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _query_response(pages)
        result = fetch_wikitext_batch(["Battle of Cannae", "Battle of Zama", "Nonexistent Battle"])

    assert result == {"Battle of Cannae": "AAA", "Battle of Zama": "BBB"}
    assert mock_urlopen.call_count == 1


def test_fetch_wikitext_batch_chunks_by_batch_size():
    pages = [{"title": "A", "revisions": [{"slots": {"main": {"content": "x"}}}]}]
    with patch("urllib.request.urlopen") as mock_urlopen, patch("time.sleep") as mock_sleep:
        mock_urlopen.return_value.__enter__.side_effect = [
            _query_response(pages),
            _query_response(pages),
        ]
        fetch_wikitext_batch(["A", "B", "C"], batch_size=2, delay_seconds=1.0)

    assert mock_urlopen.call_count == 2  # chunks of 2 -> ["A", "B"], ["C"]
    mock_sleep.assert_called_once_with(1.0)


def test_fetch_wikitext_batch_retries_on_429_then_succeeds():
    pages = [{"title": "A", "revisions": [{"slots": {"main": {"content": "x"}}}]}]
    error = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("urllib.request.urlopen") as mock_urlopen, patch("time.sleep") as mock_sleep:
        mock_urlopen.return_value.__enter__.side_effect = [error, _query_response(pages)]
        result = fetch_wikitext_batch(["A"], max_retries=3)

    assert result == {"A": "x"}
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once()  # backoff before the retry, not the politeness delay
