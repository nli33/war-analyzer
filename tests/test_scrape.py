"""Tests for war/scrape.py. Parser tests use fixtures only; batch-fetch tests mock urlopen —
no real network calls."""

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

from war.scrape import (
    extract_battle_titles,
    fetch_category_members,
    fetch_wikitext_batch,
    find_infobox_body,
    parse_military_infobox,
    redirect_stub_target,
    split_infobox_params,
)

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


def test_split_infobox_params_does_not_truncate_on_nested_template_close():
    # Regression test (C2): a value containing a nested multi-line {{efn|...}} citation has its
    # own "}}" before the field's real end. The old single-regex param splitter
    # (`(?=\n}}|\Z)` lookahead) stopped there, silently truncating the value. Depth-aware
    # splitting must read all the way to the *next field*, not the first "}}" it sees.
    wikitext = (
        "{{Infobox military conflict\n"
        "| strength1 = 72,000{{efn|\n* alt estimate one\n* alt estimate two\n}}\n"
        "| strength2 = 86,400\n"
        "}}"
    )
    body = find_infobox_body(wikitext)
    pairs = dict(split_infobox_params(body))
    assert pairs["strength1"] == "72,000{{efn|\n* alt estimate one\n* alt estimate two\n}}"
    assert pairs["strength2"] == "86,400"


def test_split_infobox_params_ignores_pipe_equals_inside_nested_template():
    # A {{ubl|...}} breakdown's own lines can start with "|" and even contain "=" — these must
    # not be mistaken for the infobox's own next "|name=" field boundary.
    wikitext = (
        "{{Infobox military conflict\n"
        "| casualties1 = {{ubl\n|label = 500\n|other item\n}}\n"
        "| casualties2 = Unknown\n"
        "}}"
    )
    body = find_infobox_body(wikitext)
    pairs = dict(split_infobox_params(body))
    assert pairs["casualties1"] == "{{ubl\n|label = 500\n|other item\n}}"
    assert pairs["casualties2"] == "Unknown"


def test_find_infobox_body_stops_at_matching_close_not_rest_of_article():
    wikitext = (
        "{{Infobox military conflict\n| conflict = Battle of X\n}}\n"
        "'''Battle of X''' was fought.\n|unrelated=should not be reachable\n}}"
    )
    body = find_infobox_body(wikitext)
    assert "unrelated" not in body


def test_redirect_stub_target_bare_redirect():
    assert redirect_stub_target("#REDIRECT [[Battle of Ras Kamboni (2007)]]") == (
        "Battle of Ras Kamboni (2007)"
    )


def test_redirect_stub_target_tolerates_trailing_redirect_category_templates():
    wikitext = "#REDIRECT [[Battle of Bronkhorstspruit]]\n\n{{R from move}}"
    assert redirect_stub_target(wikitext) == "Battle of Bronkhorstspruit"


def test_redirect_stub_target_none_for_anchor_redirect():
    # Points at a section of a different page, not its own infobox -- re-fetching would risk
    # handing every title anchored to that page the same (wrong) first infobox. See docstring.
    wikitext = "#REDIRECT [[Battles of Saratoga#First Saratoga]]"
    assert redirect_stub_target(wikitext) is None


def test_redirect_stub_target_none_for_non_redirect_page():
    assert redirect_stub_target(CANNAE_WIKITEXT) is None


def _query_response(pages, redirects=None):
    query = {"pages": pages}
    if redirects is not None:
        query["redirects"] = redirects
    body = json.dumps({"query": query}).encode()
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


def test_fetch_wikitext_batch_follows_redirects_keyed_by_requested_title():
    # Regression test (C7): a requested title that is itself a #REDIRECT page (e.g.
    # "Siege of Alesia" -> "Battle of Alesia") used to come back with the redirect stub's own
    # one-line wikitext (no infobox at all), since fetch_wikitext_batch keyed results purely by
    # the API response's `page["title"]`. With `redirects=1`, the API resolves the redirect
    # server-side and reports the mapping separately in `query.redirects`.
    pages = [{"title": "Battle of Alesia", "revisions": [{"slots": {"main": {"content": "AAA"}}}]}]
    redirects = [{"from": "Siege of Alesia", "to": "Battle of Alesia"}]
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _query_response(pages, redirects)
        result = fetch_wikitext_batch(["Siege of Alesia"])

    assert result == {"Siege of Alesia": "AAA", "Battle of Alesia": "AAA"}


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


def test_extract_battle_titles_keeps_keyword_matches_only():
    text = "[[Battle of Cannae]], [[Rome]], and [[Siege of Ostend]]."
    assert extract_battle_titles(text) == ["Battle of Cannae", "Siege of Ostend"]


def test_extract_battle_titles_excludes_list_of_links():
    # A "see also" link containing the keyword "siege" shouldn't be mistaken for a battle page.
    text = "[[Battle of Kokenhausen]] ... see also [[List of sieges]]"
    assert extract_battle_titles(text) == ["Battle of Kokenhausen"]


def test_extract_battle_titles_excludes_namespaced_and_interwiki_links():
    text = "[[:es:Masacre de la cueva de Els Trocs|Battle Massacre]] [[Category:Battles]]"
    assert extract_battle_titles(text) == []


def test_extract_battle_titles_strips_section_fragments():
    # The keyword only appears in the fragment, not the page title itself — not a battle page.
    text = "[[Scorpion I#Battle depiction|Unification Battle of Egypt]]"
    assert extract_battle_titles(text) == []


def test_extract_battle_titles_dedupes_preserving_first_order():
    text = "[[Battle of Zama]] ... [[Battle of Cannae]] ... [[Battle of Zama|Zama]]"
    assert extract_battle_titles(text) == ["Battle of Zama", "Battle of Cannae"]


def test_extract_battle_titles_works_on_wikitable_markup():
    # Real markup shape: table row cells separated by `||`, link piped to a display alias.
    text = (
        "{|class=\"wikitable\"\n"
        "|-\n"
        "| [[Eighty Years' War]] || [[Siege of Rheinberg (1601)|Siege of Rheinberg]] "
        "|| {{flagicon|Germany}} || 12 June\n"
        "|-\n"
        "| [[Jebel Sahaba]] || {{flagicon|Sudan}} || Neolithic conflict site\n"
        "|}"
    )
    # "Eighty Years' War" has no keyword (correctly excluded as a war, not a battle); "Jebel
    # Sahaba" is the documented miss (no battle-like keyword in its title).
    assert extract_battle_titles(text) == ["Siege of Rheinberg (1601)"]


def test_extract_battle_titles_works_on_bullet_markup():
    text = "* [[Battle of Hastings]]\n* [[Fall of Constantinople]]\n* [[Byzantine Empire]]"
    assert extract_battle_titles(text) == ["Battle of Hastings", "Fall of Constantinople"]


def test_fetch_wikitext_batch_retries_on_429_then_succeeds():
    pages = [{"title": "A", "revisions": [{"slots": {"main": {"content": "x"}}}]}]
    error = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("urllib.request.urlopen") as mock_urlopen, patch("time.sleep") as mock_sleep:
        mock_urlopen.return_value.__enter__.side_effect = [error, _query_response(pages)]
        result = fetch_wikitext_batch(["A"], max_retries=3)

    assert result == {"A": "x"}
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once()  # backoff before the retry, not the politeness delay


def _categorymembers_response(titles, cmcontinue=None):
    payload = {"query": {"categorymembers": [{"title": t} for t in titles]}}
    if cmcontinue:
        payload["continue"] = {"cmcontinue": cmcontinue}
    return BytesIO(json.dumps(payload).encode())


def test_fetch_category_members_single_page():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _categorymembers_response(
            ["Julius Caesar", "Pompey"]
        )
        result = fetch_category_members("Category:Ancient Roman generals")

    assert result == ["Julius Caesar", "Pompey"]
    assert mock_urlopen.call_count == 1


def test_fetch_category_members_follows_cmcontinue():
    with patch("urllib.request.urlopen") as mock_urlopen, patch("time.sleep") as mock_sleep:
        mock_urlopen.return_value.__enter__.side_effect = [
            _categorymembers_response(["A"], cmcontinue="page2|0"),
            _categorymembers_response(["B"]),
        ]
        result = fetch_category_members("Category:X", delay_seconds=2.0)

    assert result == ["A", "B"]
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once_with(2.0)


def test_fetch_category_members_retries_on_429_then_succeeds():
    error = urllib.error.HTTPError("url", 429, "Too Many Requests", {}, None)
    with patch("urllib.request.urlopen") as mock_urlopen, patch("time.sleep") as mock_sleep:
        mock_urlopen.return_value.__enter__.side_effect = [
            error,
            _categorymembers_response(["A"]),
        ]
        result = fetch_category_members("Category:X", max_retries=3)

    assert result == ["A"]
    assert mock_urlopen.call_count == 2
    mock_sleep.assert_called_once()


def test_fetch_category_members_empty_category():
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = _categorymembers_response([])
        result = fetch_category_members("Category:Does not exist")

    assert result == []
