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
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "war-analyzer-research-scraper/0.1 (draft-data only, not for direct citation)"

# Matches `|param = value` pairs inside a wikitext template, value running until the next
# `|param =` line or the template's closing `}}`.
_PARAM_RE = re.compile(r"\|\s*(\w+)\s*=\s*(.*?)(?=\n\s*\|\s*\w+\s*=|\n}}|\Z)", re.DOTALL)

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


def parse_military_infobox(wikitext: str) -> dict[str, str]:
    """Extract known infobox fields from a page's raw wikitext.

    Only looks inside the first `{{Infobox military conflict ...}}` template (case-insensitive,
    tolerates the "Infobox military conflict" / "military conflict" naming variants Wikipedia
    uses). Returns {} if no such infobox is found — callers should treat that as "no draft
    available, research this one by hand" rather than an error.
    """
    match = re.search(
        r"\{\{\s*Infobox military conflict(.*)", wikitext, re.IGNORECASE | re.DOTALL
    )
    if not match:
        return {}

    body = match.group(1)
    fields: dict[str, str] = {}
    for name, raw_value in _PARAM_RE.findall(body):
        if name not in _INFOBOX_FIELDS:
            continue
        cleaned = _strip_wikitext_markup(raw_value)
        if cleaned:
            fields[name] = cleaned
    return fields


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


def draft_for_battle(title: str) -> InfoboxDraft:
    """Fetch + parse a battle page. Network call. Result is a draft, not a citable source."""
    wikitext = fetch_wikitext(title)
    return InfoboxDraft(title=title, fields=parse_military_infobox(wikitext))
