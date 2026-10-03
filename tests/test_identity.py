"""Tests for war/identity.py (E1): canonical identity resolution from a MediaWiki
`action=query&prop=pageprops&redirects=1` response.

Fixtures below are trimmed real responses (captured 2026-10-02 against the live API for exactly
the titles PROGRESS.md's E1 line names as the verification case: Napoleon, Wellington, Hannibal
variants), not synthesized JSON — `parse_identity_response` is pure (no network), so these drive
it directly.
"""

from war.identity import IdentityInfo, parse_identity_response

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
