"""Tests for war/identity.py (E1): canonical identity resolution from a MediaWiki
`action=query&prop=pageprops&redirects=1` response.

Fixtures below are trimmed real responses (captured 2026-10-02 against the live API for exactly
the titles PROGRESS.md's E1 line names as the verification case: Napoleon, Wellington, Hannibal
variants), not synthesized JSON — `parse_identity_response` is pure (no network), so these drive
it directly.
"""

import json
from pathlib import Path

import pytest

from war.identity import (
    IdentityInfo,
    build_general_id_resolver,
    load_identity_map,
    parse_identity_response,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REAL_IDENTITY_MAP = REPO_ROOT / "data" / "raw" / "identity_map.json"

NAPOLEON_RESPONSE = {
    "batchcomplete": True,
    "query": {
        "redirects": [
            {"from": "Napoleon Bonaparte", "to": "Napoleon"},
            {"from": "Napoleon I", "to": "Napoleon"},
        ],
        "pages": [
            {
                "pageid": 69880,
                "ns": 0,
                "title": "Napoleon",
                "pageprops": {"wikibase_item": "Q517"},
            }
        ],
    },
}

WELLINGTON_RESPONSE = {
    "batchcomplete": True,
    "query": {
        "redirects": [
            {
                "from": "Duke of Wellington",
                "to": "Arthur Wellesley, 1st Duke of Wellington",
            }
        ],
        "pages": [
            {
                "pageid": 8474,
                "ns": 0,
                "title": "Arthur Wellesley, 1st Duke of Wellington",
                "pageprops": {"wikibase_item": "Q131691"},
            },
            {
                "pageid": 33804,
                "ns": 0,
                "title": "Wellington",
                "pageprops": {"wikibase_item": "Q23661"},
            },
        ],
    },
}

HANNIBAL_RESPONSE = {
    "batchcomplete": True,
    "query": {
        "redirects": [{"from": "Hannibal Barca", "to": "Hannibal"}],
        "pages": [
            {
                "pageid": 13959,
                "ns": 0,
                "title": "Hannibal",
                "pageprops": {"wikibase_item": "Q36456"},
            }
        ],
    },
}

# A lowercase/underscored title ("napoleon_bonaparte") goes through `query.normalized` before
# the redirect chain, a second independent hop on top of HANNIBAL_RESPONSE's single-hop case.
NORMALIZED_THEN_REDIRECT_RESPONSE = {
    "batchcomplete": True,
    "query": {
        "normalized": [{"fromencoded": False, "from": "napoleon_bonaparte", "to": "Napoleon bonaparte"}],
        "redirects": [
            {"from": "Hannibal Barca", "to": "Hannibal"},
            {"from": "Napoleon bonaparte", "to": "Napoleon"},
        ],
        "pages": [
            {"pageid": 13959, "ns": 0, "title": "Hannibal", "pageprops": {"wikibase_item": "Q36456"}},
            {"pageid": 69880, "ns": 0, "title": "Napoleon", "pageprops": {"wikibase_item": "Q517"}},
        ],
    },
}

DISAMBIGUATION_AND_MISSING_RESPONSE = {
    "batchcomplete": True,
    "query": {
        "pages": [
            {"ns": 0, "title": "ThisPageDoesNotExistXyzAbc123", "missing": True},
            {
                "pageid": 20605753,
                "ns": 0,
                "title": "John Smith",
                "pageprops": {"disambiguation": "", "wikibase_item": "Q245903"},
            },
        ]
    },
}


def test_napoleon_variants_resolve_to_one_canonical_title():
    result = parse_identity_response(
        NAPOLEON_RESPONSE, ["Napoleon", "Napoleon I", "Napoleon Bonaparte"]
    )
    assert {info.canonical_title for info in result.values()} == {"Napoleon"}
    assert {info.wikidata_id for info in result.values()} == {"Q517"}
    assert result["Napoleon Bonaparte"] == IdentityInfo(
        "Napoleon Bonaparte", "Napoleon", "Q517", False
    )


def test_hannibal_variants_resolve_to_one_canonical_title():
    result = parse_identity_response(HANNIBAL_RESPONSE, ["Hannibal", "Hannibal Barca"])
    assert {info.canonical_title for info in result.values()} == {"Hannibal"}
    assert {info.wikidata_id for info in result.values()} == {"Q36456"}


def test_wellington_title_and_city_of_wellington_are_different_identities():
    """"Wellington" bare is the New Zealand city's article, not a redirect to the duke's -- a
    real case this project's dev log flagged (ingestion.md's D3 entry): two titles must not be
    merged just because they look like name variants. Only the real redirect ("Duke of
    Wellington") collapses."""
    result = parse_identity_response(
        WELLINGTON_RESPONSE,
        ["Arthur Wellesley, 1st Duke of Wellington", "Duke of Wellington", "Wellington"],
    )
    assert result["Arthur Wellesley, 1st Duke of Wellington"].wikidata_id == "Q131691"
    assert result["Duke of Wellington"].wikidata_id == "Q131691"
    assert result["Duke of Wellington"].canonical_title == "Arthur Wellesley, 1st Duke of Wellington"
    assert result["Wellington"].wikidata_id == "Q23661"


def test_normalized_title_chains_through_to_the_redirect_target():
    result = parse_identity_response(
        NORMALIZED_THEN_REDIRECT_RESPONSE, ["napoleon_bonaparte", "Hannibal Barca"]
    )
    assert result["napoleon_bonaparte"].canonical_title == "Napoleon"
    assert result["napoleon_bonaparte"].wikidata_id == "Q517"
    assert result["Hannibal Barca"].canonical_title == "Hannibal"


def test_disambiguation_page_flagged():
    result = parse_identity_response(DISAMBIGUATION_AND_MISSING_RESPONSE, ["John Smith"])
    assert result["John Smith"].is_disambiguation is True
    assert result["John Smith"].canonical_title == "John Smith"


def test_missing_page_has_no_canonical_title():
    result = parse_identity_response(
        DISAMBIGUATION_AND_MISSING_RESPONSE, ["ThisPageDoesNotExistXyzAbc123"]
    )
    info = result["ThisPageDoesNotExistXyzAbc123"]
    assert info.canonical_title is None
    assert info.wikidata_id is None
    assert info.is_disambiguation is False


def test_page_with_no_pageprops_at_all():
    payload = {
        "query": {
            "pages": [{"pageid": 1, "ns": 0, "title": "Some Minor Figure"}],
        }
    }
    info = parse_identity_response(payload, ["Some Minor Figure"])["Some Minor Figure"]
    assert info.canonical_title == "Some Minor Figure"
    assert info.wikidata_id is None
    assert info.is_disambiguation is False


# --- build_general_id_resolver (E2) ---------------------------------------------------------


def test_resolver_merges_titles_sharing_a_wikidata_id():
    identities = {
        "Napoleon": IdentityInfo("Napoleon", "Napoleon", "Q517", False),
        "Napoleon I": IdentityInfo("Napoleon I", "Napoleon", "Q517", False),
        "Napoleon Bonaparte": IdentityInfo("Napoleon Bonaparte", "Napoleon Bonaparte", "Q517", False),
    }
    resolver = build_general_id_resolver(identities)
    # "Napoleon" sorts before "Napoleon Bonaparte" -- the representative title for this group.
    assert resolver == {
        "Napoleon": "napoleon",
        "Napoleon I": "napoleon",
        "Napoleon Bonaparte": "napoleon",
    }


def test_resolver_disambiguation_page_is_unidentified():
    identities = {"John Smith": IdentityInfo("John Smith", "John Smith", "Q245903", True)}
    assert build_general_id_resolver(identities) == {"John Smith": None}


def test_resolver_unresolved_title_is_unidentified():
    identities = {"Some Deleted Page": IdentityInfo("Some Deleted Page", None, None, False)}
    assert build_general_id_resolver(identities) == {"Some Deleted Page": None}


def test_resolver_title_with_no_wikidata_id_uses_its_own_canonical_title():
    identities = {"Some Minor Figure": IdentityInfo("Some Minor Figure", "Some Minor Figure", None, False)}
    assert build_general_id_resolver(identities) == {"Some Minor Figure": "some-minor-figure"}


def test_resolver_does_not_merge_titles_with_different_wikidata_ids():
    # Real case from this project's dev log: "Wellington" bare is the New Zealand city's
    # article, not the duke's -- same wikidata_id as itself only, never merged with the duke.
    identities = {
        "Duke of Wellington": IdentityInfo(
            "Duke of Wellington", "Arthur Wellesley, 1st Duke of Wellington", "Q131691", False
        ),
        "Wellington": IdentityInfo("Wellington", "Wellington", "Q23661", False),
    }
    resolver = build_general_id_resolver(identities)
    assert resolver["Duke of Wellington"] != resolver["Wellington"]


def test_load_identity_map_round_trips(tmp_path):
    path = tmp_path / "identity_map.json"
    path.write_text(
        json.dumps(
            {
                "Napoleon": {
                    "requested_title": "Napoleon",
                    "canonical_title": "Napoleon",
                    "wikidata_id": "Q517",
                    "is_disambiguation": False,
                }
            }
        ),
        encoding="utf-8",
    )
    identities = load_identity_map(path)
    assert identities == {"Napoleon": IdentityInfo("Napoleon", "Napoleon", "Q517", False)}


@pytest.mark.skipif(not REAL_IDENTITY_MAP.exists(), reason="requires data/raw/identity_map.json")
def test_real_identity_map_no_two_general_ids_share_a_wikidata_id():
    """E2's own verification line: build the real resolver against E1's full-cache run and
    confirm the invariant the merge is supposed to guarantee holds for every title, not just the
    Napoleon/Wellington/Hannibal spot-check cases."""
    identities = load_identity_map(REAL_IDENTITY_MAP)
    resolver = build_general_id_resolver(identities)

    general_id_by_wikidata_id: dict[str, str] = {}
    for title, general_id in resolver.items():
        wikidata_id = identities[title].wikidata_id
        if general_id is None or not wikidata_id:
            continue
        if wikidata_id in general_id_by_wikidata_id:
            assert general_id_by_wikidata_id[wikidata_id] == general_id, (
                f"wikidata id {wikidata_id!r} maps to two different general_ids "
                f"({general_id_by_wikidata_id[wikidata_id]!r} and {general_id!r})"
            )
        else:
            general_id_by_wikidata_id[wikidata_id] = general_id
