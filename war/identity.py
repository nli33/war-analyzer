"""E1: canonical identity resolution for commander wikilink titles.

`war.commanders.general_id_from_title` slugs whatever wikilink target text a battle infobox
happened to use, with no cross-reference against other titles for the same person — so a
historical figure with more than one Wikipedia title (a redirect like "Napoleon I" -> "Napoleon",
*or* a separate non-redirect article like "Napoleon" the short-name bio vs. "Napoleon Bonaparte"
the full-name one) ends up split across multiple `general_id`s. This module answers, for a batch
of requested titles, "what page do they really resolve to, and do any of them share a Wikidata
item" — redirects answer the first question, a shared Wikidata ID (`pageprops.wikibase_item`)
answers the second. `war/roster.py`/`war/commanders.py` (E2) are the callers that act on it.

A resolved title landing on a disambiguation page (`pageprops.disambiguation` present) means the
original wikilink was ambiguous, not a real resolution to one person — E2 treats that the same as
an unidentified commander.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from war.scrape import MAX_TITLES_PER_BATCH, USER_AGENT, WIKIPEDIA_API


@dataclass(frozen=True)
class IdentityInfo:
    """What one requested title resolves to.

    `canonical_title` is `None` when the title matches no Wikipedia page at all (the article was
    deleted/moved since whatever cache originally recorded the wikilink). `wikidata_id` is
    `None` when the canonical page has no Wikidata item linked (rare, but real for some very
    minor figures) — two titles with `wikidata_id is None` are never treated as the same person
    just because both are `None`.
    """

    requested_title: str
    canonical_title: str | None
    wikidata_id: str | None
    is_disambiguation: bool


def parse_identity_response(payload: dict, requested_titles: list[str]) -> dict[str, IdentityInfo]:
    """Turn one `action=query&prop=pageprops&redirects=1` response into `{requested_title:
    IdentityInfo}`. Pure function (no network) so it can run against fixture JSON in tests.

    MediaWiki resolves a requested title to a final page title in up to two independent steps,
    each reported as its own `from`/`to` list: `query.normalized` (capitalization/underscore
    normalization) and `query.redirects` (an actual `#REDIRECT` page). Either, both, or neither
    may apply to a given title, so this walks the combined from->to chain to a fixed point
    rather than assuming a fixed number of hops.
    """
    chain: dict[str, str] = {}
    for entry in payload.get("query", {}).get("normalized", []):
        chain[entry["from"]] = entry["to"]
    for entry in payload.get("query", {}).get("redirects", []):
        chain[entry["from"]] = entry["to"]

    pages_by_title: dict[str, dict] = {}
    for page in payload.get("query", {}).get("pages", []):
        pages_by_title[page["title"]] = page

    results: dict[str, IdentityInfo] = {}
    for requested in requested_titles:
        final_title = requested
        seen = {final_title}
        while final_title in chain and chain[final_title] not in seen:
            final_title = chain[final_title]
            seen.add(final_title)

        page = pages_by_title.get(final_title)
        if page is None or page.get("missing"):
            results[requested] = IdentityInfo(requested, None, None, False)
            continue

        pageprops = page.get("pageprops", {})
        results[requested] = IdentityInfo(
            requested_title=requested,
            canonical_title=page["title"],
            wikidata_id=pageprops.get("wikibase_item"),
            is_disambiguation="disambiguation" in pageprops,
        )
    return results


def _fetch_identity_batch_once(titles: list[str], max_retries: int) -> dict[str, IdentityInfo]:
    params = {
        "action": "query",
        "titles": "|".join(titles),
        "redirects": "1",
        "prop": "pageprops",
        "ppprop": "wikibase_item|disambiguation",
        "format": "json",
        "formatversion": "2",
    }
    query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    request = urllib.request.Request(
        f"{WIKIPEDIA_API}?{query}", headers={"User-Agent": USER_AGENT}
    )

    backoff = 10.0
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                payload = json.loads(response.read())
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < max_retries - 1:
                time.sleep(backoff)
                backoff *= 2
                continue
            raise

    return parse_identity_response(payload, titles)


def resolve_identities(
    titles: list[str],
    batch_size: int = MAX_TITLES_PER_BATCH,
    delay_seconds: float = 1.0,
    max_retries: int = 5,
) -> dict[str, IdentityInfo]:
    """Resolve many requested titles to canonical identities in as few HTTP requests as possible.

    Same batching/backoff shape as `war.scrape.fetch_wikitext_batch`: up to `batch_size` titles
    per request (MediaWiki's anonymous-caller cap), a pause between requests, exponential backoff
    on HTTP 429. Network calls.
    """
    results: dict[str, IdentityInfo] = {}
    deduped = list(dict.fromkeys(titles))
    for start in range(0, len(deduped), batch_size):
        chunk = deduped[start : start + batch_size]
        results.update(_fetch_identity_batch_once(chunk, max_retries))
        if start + batch_size < len(deduped):
            time.sleep(delay_seconds)
    return results
