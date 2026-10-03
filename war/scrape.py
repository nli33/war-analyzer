"""Wikipedia infobox scraper — draft-data generator only (PLAN.md Section 3 step 3).

Pulls the `{{Infobox military conflict}}` fields (strength/casualties/date/result) for a
battle page and returns them as raw, unverified strings. This exists to save research time,
not replace it: scraper output must be cross-checked against an academic source (Clodfelter,
Osprey, etc.) before it's written into data/battles.csv — infobox numbers frequently disagree
with, or are more credulous than, academic estimates. Every value returned here is tagged
`_source: "wikipedia_infobox_scrape (unverified)"` as a reminder of that at the call site.
"""

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from war.wikitext import balanced_template_end

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "war-analyzer-research-scraper/0.1 (draft-data only, not for direct citation)"

# MediaWiki allows up to 50 titles per query for anonymous callers (500 for bots/users with
# apihighlimits). 50 is the safe default for an unauthenticated throttled crawler.
MAX_TITLES_PER_BATCH = 50

# A `|name = value` boundary only counts at template-brace depth 0 (see split_infobox_params) —
# otherwise a nested template whose own content happens to start a line with "|word=" (a
# {{ubl|...}} breakdown item that includes an "=", say) could be mistaken for the next field.
_PARAM_START_RE = re.compile(r"(?:^|\n)\s*\|\s*(\w+)\s*=")

_INFOBOX_FIELDS = (
    "conflict",
    "date",
    "place",
    "result",
    "combatant1",
    "combatant2",
    "commander1",
    "commander2",
    "strength1",
    "strength2",
    "casualties1",
    "casualties2",
)

# The 7 pages Wikipedia splits its battle index across (same split A1's study of
# ethanarsht/military_rankings uses). "since 2001" currently redirects to "...in the 21st
# century" — using the live redirect target directly avoids relying on redirect resolution.
LIST_OF_BATTLES_PAGES = (
    "List of battles before 301",
    "List of battles 301–1300",
    "List of battles 1301–1600",
    "List of battles 1601–1800",
    "List of battles 1801–1900",
    "List of battles 1901–2000",
    "List of battles in the 21st century",
)

# C4a seed roster: Wikipedia category pages whose members are (mostly) general biography
# pages. Hand-probed from the category hierarchy rather than guessed — see
# ~/notes/war-analyzer/ingestion.md's C4a entry for the probe transcript. Three groups:
#
# - "Category:Generals by century" leaf categories (1st-4th c. BC through 21st century): the
#   literal "by era" source PROGRESS.md's C4a line asks for. Turned out sparse on its own
#   (~200 members total across all 25 — most Wikipedia general bios aren't century-tagged),
#   kept anyway since it catches names the war/nationality categories below miss (a polity
#   with no modern-nation-state category, e.g. a Khwarezmian or early-medieval commander).
# - "Category:Generals by war" and "Category:Military leaders by war" leaf categories: the
#   two hubs overlap in era but not membership (a "Generals of X" tag and a "Military leaders
#   of X" tag on the same war aren't applied to the same pages 1:1), so both are kept rather
#   than picking one. Napoleonic Wars commanders live one hub-level deeper, by nationality.
# - "Category:Generals by nationality" leaf categories: only a curated subset of major
#   historical military powers, not all ~190 countries in the hub — the hub itself is mostly
#   small modern countries with few or no pre-20th-century battles in this project's scope,
#   and crawling all of them would dominate the seed list with names C4b's battle-match filter
#   would just drop anyway.
GENERAL_SEED_CATEGORIES = (
    # By century (ancient/medieval eras with no modern-nationality equivalent)
    "Category:4th-century BC generals",
    "Category:3rd-century BC generals",
    "Category:2nd-century BC generals",
    "Category:1st-century BC generals",
    "Category:1st-century generals",
    "Category:2nd-century generals",
    "Category:3rd-century generals",
    "Category:4th-century generals",
    "Category:5th-century generals",
    "Category:6th-century generals",
    "Category:7th-century generals",
    "Category:8th-century generals",
    "Category:9th-century generals",
    "Category:10th-century generals",
    "Category:11th-century generals",
    "Category:12th-century generals",
    "Category:13th-century generals",
    "Category:14th-century generals",
    "Category:15th-century generals",
    "Category:16th-century generals",
    "Category:17th-century generals",
    "Category:18th-century generals",
    "Category:19th-century generals",
    "Category:20th-century generals",
    "Category:21st-century generals",
    # Flat ancient/medieval categories (denser than their by-century counterparts)
    "Category:Ancient Roman generals",
    "Category:Ancient Greek generals",
    "Category:Byzantine generals",
    # By war ("Category:Generals by war" leaves)
    "Category:Generals of the American Civil War",
    "Category:Generals in the American Revolution",
    "Category:Generals of the Bangladesh Liberation War",
    "Category:Generals in the Mexican War of Independence",
    "Category:Generals of the Colombian War of Independence",
    "Category:Generals of the India–Pakistan war of 1965",
    "Category:Generals of the India–Pakistan war of 1971",
    "Category:Generals of the January Uprising",
    "Category:Generals of the Kościuszko Uprising",
    "Category:Generals of the November Uprising",
    "Category:Generals of World War I",
    "Category:Generals of World War II",
    "Category:Confederate States Army generals",
    # By war ("Category:Military leaders by war" leaves, not duplicating the above)
    "Category:First Punic War commanders",
    "Category:Second Punic War commanders",
    "Category:Military leaders of the French Revolutionary Wars",
    "Category:Military leaders of the Gulf War",
    "Category:Military leaders of the India–Pakistan war of 1965",
    "Category:Military leaders of the India–Pakistan war of 1971",
    "Category:Military leaders of the Iraq War",
    "Category:Military leaders of the Italian Wars",
    "Category:Military leaders of the New Zealand Wars",
    "Category:Military leaders of the War of the Spanish Succession",
    "Category:Military leaders of World War I",
    "Category:Military leaders of World War II",
    # Napoleonic Wars commanders, by nationality (one hub-level below "by war")
    "Category:Austrian Empire commanders of the Napoleonic Wars",
    "Category:British commanders of the Napoleonic Wars",
    "Category:Danish military commanders of the Napoleonic Wars",
    "Category:Dutch military commanders of the Napoleonic Wars",
    "Category:French commanders of the Napoleonic Wars",
    "Category:German commanders of the Napoleonic Wars",
    "Category:Haitian commanders of the Napoleonic Wars",
    "Category:Italian commanders of the Napoleonic Wars",
    "Category:Polish commanders of the Napoleonic Wars",
    "Category:Portuguese military commanders of the Napoleonic Wars",
    "Category:Russian commanders of the Napoleonic Wars",
    "Category:Spanish commanders of the Napoleonic Wars",
    "Category:Swedish military commanders of the Napoleonic Wars",
    # By nationality (curated: major historical military powers only, see docstring above)
    "Category:American generals",
    "Category:British generals",
    "Category:French generals",
    "Category:German generals",
    "Category:Russian generals",
    "Category:Spanish generals",
    "Category:Turkish generals",
    "Category:Polish generals",
    "Category:Swedish generals",
    "Category:Iranian generals",
    "Category:Japanese generals",
    "Category:Israeli generals",
    "Category:Indian generals",
    "Category:North Korean generals",
    "Category:South Korean generals",
    "Category:Egyptian generals",
    "Category:Italian generals",
    "Category:Chinese generals",
    "Category:Austrian generals",
)

# Keyword filter from A1's study of ethanarsht/military_rankings: a wikilink target containing
# one of these words is treated as a candidate battle page. This is recall-oriented, not
# precision — it also catches non-battle links (e.g. a "see also" link to "List of sieges",
# excluded separately below) and it misses battle pages that don't use any of these words (e.g.
# ancient conflict sites named only for their location, like "Jebel Sahaba"). C2's infobox
# extractor is the precision filter on this list, not this function.
_BATTLE_LINK_KEYWORDS = ("fall", "battle", "siege", "capture", "operation", "action", "recapture")

_WIKILINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|[^\]]*)?\]\]")


@dataclass
class InfoboxDraft:
    """Raw, unverified fields pulled from a battle's Wikipedia infobox."""

    title: str
    fields: dict[str, str] = field(default_factory=dict)
    source: str = "wikipedia_infobox_scrape (unverified)"

    def to_dict(self) -> dict:
        return {"title": self.title, "fields": self.fields, "_source": self.source}


def _strip_wikitext_markup(value: str) -> str:
    """Best-effort cleanup: drop refs, wikilinks brackets, templates, collapse whitespace."""
    value = re.sub(r"<ref[^>]*>.*?</ref>", "", value, flags=re.DOTALL)
    value = re.sub(r"<ref[^>]*/>", "", value)
    value = re.sub(r"\{\{[^{}]*\}\}", "", value)  # inline templates like {{convert|...}}
    value = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", value)  # [[a|b]] -> b, [[a]] -> a
    value = re.sub(r"<br\s*/?>", "; ", value)
    value = re.sub(r"'''?", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


_BARE_REDIRECT_RE = re.compile(r"^\s*#REDIRECT\s*\[\[([^\]|]+)", re.IGNORECASE)


def redirect_stub_target(wikitext: str) -> str | None:
    """Return the target title of a bare `#REDIRECT [[Target]]` stub, or `None` if `wikitext`
    isn't one (also `None` for a `#REDIRECT [[Page#Section]]` anchor redirect to part of a
    different page — re-fetching `Page` would hand every title anchored to it the *same* first
    infobox on that page regardless of which section each title actually names, which risks
    attributing the wrong sub-battle's numbers rather than leaving the title unresolved; see F2
    dev log entry).

    Used by `scripts/refresh_redirect_stubs.py` (F2) to find stale cache entries fetched before
    `fetch_wikitext_batch` followed redirects server-side (b57cc1b) — those entries are the
    one-line stub itself, not the target page's content, so they look infobox-less even though
    the target page has one.
    """
    match = _BARE_REDIRECT_RE.match(wikitext)
    if not match:
        return None
    target = match.group(1).strip()
    return None if "#" in target else target


def find_infobox_body(wikitext: str) -> str | None:
    """Return the inner content of the first `{{Infobox military conflict ...}}` template.

    Bounded by brace-depth tracking (`balanced_template_end`), not a `}}` lookahead — the old
    approach matched the *first* `}}` anywhere in the rest of the page, which is wrong whenever
    a field's value contains a nested template (a `{{efn|...}}` citation, say) whose own closing
    `}}` comes first. Returns None if no such infobox is found.
    """
    match = re.search(r"\{\{\s*Infobox military conflict", wikitext, re.IGNORECASE)
    if not match:
        return None
    end = balanced_template_end(wikitext, match.start())
    return wikitext[match.end() : end - 2]


def split_infobox_params(body: str) -> list[tuple[str, str]]:
    """Split an infobox template's inner body into (name, raw_value) pairs.

    A `|name = value` boundary only starts a new param when it occurs at template-brace depth
    0 — i.e. not inside a nested template the previous param's value contains. Real infobox
    fields nest templates routinely (a multi-line `{{efn|...}}` citation, a `{{ubl|...}}`
    breakdown whose own lines can themselves start with "|"), and depth-0-gating is what keeps
    those from being mistaken for the next field's boundary.
    """
    depth = 0
    i, n = 0, len(body)
    boundaries: list[tuple[int, int, str]] = []  # (boundary_start, value_start, name)
    while i < n:
        two = body[i : i + 2]
        if two == "{{":
            depth += 1
            i += 2
            continue
        if two == "}}":
            depth = max(depth - 1, 0)
            i += 2
            continue
        if depth == 0:
            match = _PARAM_START_RE.match(body, i)
            if match:
                boundaries.append((match.start(), match.end(), match.group(1)))
                i = match.end()
                continue
        i += 1

    pairs = []
    for idx, (_, value_start, name) in enumerate(boundaries):
        value_end = boundaries[idx + 1][0] if idx + 1 < len(boundaries) else n
        pairs.append((name, body[value_start:value_end].strip()))
    return pairs


def parse_military_infobox(wikitext: str) -> dict[str, str]:
    """Extract known infobox fields from a page's raw wikitext, as cleaned text.

    Only looks inside the first `{{Infobox military conflict ...}}` template (case-insensitive,
    tolerates the "Infobox military conflict" / "military conflict" naming variants Wikipedia
    uses). Returns {} if no such infobox is found — callers should treat that as "no draft
    available, research this one by hand" rather than an error.

    This generic text cleanup is a reasonable baseline for the text fields (date, place,
    combatant/commander names), but is not the real numeric parser for strength/casualties —
    see `war.infobox_numbers.extract_strength_and_casualties` for that.
    """
    body = find_infobox_body(wikitext)
    if body is None:
        return {}

    fields: dict[str, str] = {}
    for name, raw_value in split_infobox_params(body):
        if name not in _INFOBOX_FIELDS:
            continue
        cleaned = _strip_wikitext_markup(raw_value)
        if cleaned:
            fields[name] = cleaned
    return fields


def extract_battle_titles(wikitext: str) -> list[str]:
    """Pull candidate battle-page titles out of a "List of battles" page's wikitext.

    Scans every `[[wikilink]]` on the page — this works unchanged whether the page's markup
    for a given era is a bullet list or a wikitable, since a wikilink looks the same in raw
    wikitext either way — and keeps targets containing a battle-like keyword (see
    `_BATTLE_LINK_KEYWORDS`), after stripping any `#section` fragment and excluding namespaced
    links (`File:`, `Category:`, interwiki language prefixes like `:es:`) and "List of ..."
    links. Order of first appearance is preserved; duplicate targets are dropped.

    >>> extract_battle_titles("[[Battle of Cannae]] and [[List of sieges]] and [[Rome]]")
    ['Battle of Cannae']
    """
    titles: list[str] = []
    seen: set[str] = set()
    for raw_target in _WIKILINK_RE.findall(wikitext):
        target = raw_target.split("#", 1)[0].strip()
        if not target or ":" in target:
            continue
        if target.lower().startswith("list of") or target.lower().startswith("lists of"):
            continue
        if not any(keyword in target.lower() for keyword in _BATTLE_LINK_KEYWORDS):
            continue
        if target not in seen:
            seen.add(target)
            titles.append(target)
    return titles


def fetch_wikitext(title: str) -> str:
    """Fetch raw wikitext for a page title via the Wikipedia API. Network call."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
        "formatversion": "2",
    }
    query = "&".join(f"{k}={urllib.parse.quote(v)}" for k, v in params.items())
    request = urllib.request.Request(
        f"{WIKIPEDIA_API}?{query}", headers={"User-Agent": USER_AGENT}
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read())
    if "error" in payload:
        raise ValueError(f"Wikipedia API error for {title!r}: {payload['error']}")
    return payload["parse"]["wikitext"]


def fetch_wikitext_batch(
    titles: list[str],
    batch_size: int = MAX_TITLES_PER_BATCH,
    delay_seconds: float = 1.0,
    max_retries: int = 5,
) -> dict[str, str]:
    """Fetch wikitext for many pages in as few HTTP requests as possible.

    Chosen over one-call-per-page (A2 measurement, see dev log): action=query with
    pipe-separated titles returns up to `batch_size` pages per request, cutting round trips
    by that same factor versus `fetch_wikitext` called in a loop, for byte-identical wikitext.
    Network calls. Retries on HTTP 429 with exponential backoff — Wikipedia's anonymous rate
    limit was hit in practice even at modest request rates during that measurement. Titles with
    no matching page (redirect-less 404s) are silently omitted from the result, not raised.
    """
    results: dict[str, str] = {}
    for start in range(0, len(titles), batch_size):
        chunk = titles[start : start + batch_size]
        results.update(_fetch_wikitext_batch_once(chunk, max_retries))
        if start + batch_size < len(titles):
            time.sleep(delay_seconds)
    return results


def _fetch_wikitext_batch_once(titles: list[str], max_retries: int) -> dict[str, str]:
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": "|".join(titles),
        "redirects": "1",
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

    out: dict[str, str] = {}
    for page in payload.get("query", {}).get("pages", []):
        if "missing" in page:
            continue
        try:
            content = page["revisions"][0]["slots"]["main"]["content"]
        except (KeyError, IndexError):
            continue
        out[page["title"]] = content
    # With redirects=1, a requested title that is itself a #REDIRECT page is resolved
    # server-side and `pages` carries the *target*'s content keyed under the target's own
    # title — the originally requested title (e.g. "Siege of Alesia" -> "Battle of Alesia")
    # would otherwise be missing from `out` entirely, silently losing every redirect title's
    # infobox. `query.redirects` lists each `from`/`to` pair so callers can still look the
    # content up by the title they asked for.
    for redirect in payload.get("query", {}).get("redirects", []):
        target_content = out.get(redirect["to"])
        if target_content is not None:
            out[redirect["from"]] = target_content
    return out


def fetch_category_members(
    category_title: str,
    page_limit: int = 500,
    delay_seconds: float = 1.5,
    max_retries: int = 5,
) -> list[str]:
    """Return the article (namespace-0) page titles directly in a Wikipedia category.

    Network calls, one `list=categorymembers` request per up-to-500-member page (MediaWiki's
    anonymous page size cap), following `cmcontinue` until exhausted. Same HTTP-429
    exponential-backoff pattern as `_fetch_wikitext_batch_once` — this project's probing found
    categorymembers hits the same anonymous rate limit `action=query&prop=revisions` does.
    Subcategories (namespace 14) and other non-article members are excluded via `cmnamespace=0`
    rather than filtered after the fact, since the API does that server-side for free.
    `page_limit` caps the number of *paginated requests*, not members — left high (effectively
    unbounded for any category this project crawls) rather than silently truncating a category's
    recall; lower it only for a bounded test.
    """
    titles: list[str] = []
    cmcontinue: str | None = None
    for _ in range(page_limit):
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category_title,
            "cmlimit": "500",
            "cmnamespace": "0",
            "format": "json",
            "formatversion": "2",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
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

        titles.extend(
            member["title"] for member in payload.get("query", {}).get("categorymembers", [])
        )
        next_continue = payload.get("continue", {}).get("cmcontinue")
        if not next_continue:
            break
        cmcontinue = next_continue
        time.sleep(delay_seconds)
    return titles


def draft_for_battle(title: str) -> InfoboxDraft:
    """Fetch + parse a battle page. Network call. Result is a draft, not a citable source."""
    wikitext = fetch_wikitext(title)
    return InfoboxDraft(title=title, fields=parse_military_infobox(wikitext))
