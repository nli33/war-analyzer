"""Deterministic numeric parser for Wikipedia infobox strength/casualty fields (C2).

`war.scrape.parse_military_infobox` cleans every infobox field the same generic way (strip refs,
collapse whitespace, delete templates) — good enough for text fields (dates, names), but wrong
for strength/casualties: collapsing whitespace erases the line breaks that separate a
killed/wounded/captured breakdown, and deleting templates outright destroys `{{plainlist|...}}`/
`{{ubl|...}}` breakdowns instead of unwrapping them. This module re-parses those four fields from
their raw (unstripped) wikitext instead.

Real infobox fields are far messier than a synthetic example suggests — pulled straight from the
cached "Battle of Waterloo" page, `strength2` reads (abbreviated):

    {{tree list}}
    * '''Total''': 118,000-120,000
    ** 91,000 infantrymen{{sfn|Bodart|1908|p=487}}
    ** 21,500 cavalrymen{{sfn|Bodart|1908|p=487}}
    ** 7,500 gunners{{sfn|Bodart|1908|p=487}}
    {{tree list/end}}{{Ubl|{{*}}282-288 guns{{#tag:ref|...|group=nb}}}}<hr />
    {{tree list}}
    *Wellington's army: {{approximately|68,000}} soldiers...
    ** ...per-nation breakdown...
    {{tree list/end}}{{Ubl|{{*}}156 guns...}}<hr />Blücher's army: {{approximately|50,000}}...

Observed rule, true across every messy real example checked (Waterloo, Borodino, Pharsalus): when
a field opens with a bare number/range (optionally "Total: ..."), that is the headline, and
everything after it is either an alternative citation, a breakdown of that SAME total, or a
different unit (guns) — never an amount to add to it. Only when the first parseable segment is
*not* bare — it names a single casualty category ("500 killed"), a unit type ("7,000 infantry"),
or a "<label>: <number>" per-nation line — is there no stated total, and the segments (that one
included) are meant to be summed. So: strip citation/footnote wrapper templates first (they're
not data, just corroborating cites), unwrap structural list templates into one item per line,
drop equipment-only segments ("40+ cannon" isn't troops), then trust a bare first segment alone
or sum every parsed segment otherwise.
"""

import re
from dataclasses import dataclass

from war.scrape import find_infobox_body, split_infobox_params
from war.wikitext import balanced_template_end, split_top_level, strip_templates, template_name_at

# Citation/footnote wrapper templates: their content is a corroborating source, not a second
# data point, so they're deleted whole (not parsed into).
_FOOTNOTE_TEMPLATE_NAMES = frozenset(
    {"efn", "efn-lr", "sfn", "sfnp", "sfnm", "citation", "refn", "r", "harvnb", "harv", "#tag:ref"}
)

# Templates whose items are the actual breakdown of a field's value, unwrapped into one line
# per item rather than deleted.
_LIST_TEMPLATE_NAMES = frozenset(
    {"ubl", "plainlist", "unbulleted list", "flatlist", "bulletedlist", "bulleted list"}
)


def _is_footnote_template(name: str) -> bool:
    name = name.strip().lower()
    return name in _FOOTNOTE_TEMPLATE_NAMES or name.startswith("cite") or name.startswith("sfn")


# Small inline templates that render as a word/number but carry no extra data once unwrapped:
# {{approximately|68,000}} -> "68,000", {{circa}}/{{circa|1800}} -> "" / "1800", {{ndash}} -> "–",
# {{*}} -> a bullet (treated as a line break so it starts a new segment), {{tree list}} and its
# `/end` counterpart are pure layout toggles.
_ARG_TEMPLATE_RE = re.compile(r"\{\{\s*(?:approximately|approx|circa)\s*(?:\|([^{}]*))?\}\}", re.IGNORECASE)
_NDASH_RE = re.compile(r"\{\{\s*ndash\s*\}\}", re.IGNORECASE)
_BULLET_TEMPLATE_RE = re.compile(r"\{\{\s*\*\s*\}\}")
_TREE_LIST_RE = re.compile(r"\{\{\s*tree list\s*\}\}", re.IGNORECASE)
_TREE_LIST_END_RE = re.compile(r"\{\{\s*tree list\s*/\s*end\s*\}\}", re.IGNORECASE)

_REF_TAG_RE = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
_SELF_CLOSE_REF_RE = re.compile(r"<ref[^>]*/>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_WIKILINK_RE = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
_BOLD_ITALIC_RE = re.compile(r"'''?")
_CITATION_BRACKET_RE = re.compile(r"\[[^\]]*\]")

# Segments describing equipment, not personnel, e.g. "40+ cannon" trailing a troop count — these
# don't count toward a strength/casualty total even when they carry the only number in a segment.
_EQUIPMENT_RE = re.compile(
    r"\b(?:cannons?|guns?|artillery\s+pieces?|mortars?|howitzers?|warships?|ships?|vessels?|"
    r"aircraft|tanks?|boats?|planes?|rifles?|muskets?)\b",
    re.IGNORECASE,
)

_UNIT_GROUP = r"(million|mil\b|thousand|k\b|m\b)?"
_NUM_GROUP = r"([\d,]*\d(?:\.\d+)?)"
_APPROX_PREFIX = r"(?:c\.|ca\.|~|about\s+)?\s*"
_RANGE_RE = re.compile(
    rf"{_APPROX_PREFIX}{_NUM_GROUP}\s*{_UNIT_GROUP}\s*(?:-|–|—|to)\s*{_APPROX_PREFIX}{_NUM_GROUP}\s*{_UNIT_GROUP}",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(rf"{_APPROX_PREFIX}{_NUM_GROUP}\s*{_UNIT_GROUP}", re.IGNORECASE)
_UNIT_MULTIPLIER = {"k": 1_000, "thousand": 1_000, "m": 1_000_000, "mil": 1_000_000, "million": 1_000_000}


# A segment is a bare "headline" value — trusted alone, with every other segment in the field
# ignored as a citation/breakdown/different-unit footnote to it — when, after an optional
# "Total:" label, it's *just* a number/range: nothing else, or only a trailing "+", or only a
# trailing multi-category casualty phrase ("killed, wounded or missing" names the whole total,
# not one part of it). Any other trailing text — a single casualty category ("500 killed"), a
# unit-type word ("7,000 infantry"), or a "<label>: <number>" per-nation line — marks it as one
# part of a breakdown instead, and every parsed segment in the field is summed.
_TOTAL_PREFIX_RE = re.compile(r"^total(?:s)?\s*:\s*", re.IGNORECASE)
_CASUALTY_CATEGORY_WORDS = ("killed", "wounded", "captured", "missing", "dead", "injured", "prisoner")


def _is_headline(segment: str) -> bool:
    text = _TOTAL_PREFIX_RE.sub("", segment.strip())
    match = _RANGE_RE.match(text) or _NUMBER_RE.match(text)
    if not match or text[: match.start()].strip():
        return False
    after = text[match.end() :].strip().lstrip("+").strip()
    if not after:
        return True
    found = {word for word in _CASUALTY_CATEGORY_WORDS if re.search(rf"\b{word}s?\b", after, re.IGNORECASE)}
    return len(found) >= 2


@dataclass(frozen=True)
class ExtractedNumber:
    """One parsed strength/casualty value. `point` is the best single estimate (a plain
    number, or a range's midpoint); `low`/`high` are set only when the source expressed a
    range, mirroring the schema's `_low`/`_high` sibling-column convention (war/schema.py)."""

    point: int | None
    low: int | None = None
    high: int | None = None


def _to_number(digits: str, unit: str | None) -> int:
    value = float(digits.replace(",", ""))
    if unit:
        value *= _UNIT_MULTIPLIER[unit.lower()]
    return round(value)


def _unwrap_list_templates(text: str) -> str:
    """Expand `{{ubl|a|b|c}}` / `{{plainlist|\\n* a\\n* b}}`-style templates into one item per
    line, so the later segment split sees each breakdown entry separately instead of losing the
    whole template to the generic template strip."""
    out = []
    i, n = 0, len(text)
    while i < n:
        if text[i : i + 2] == "{{":
            end = balanced_template_end(text, i)
            name = template_name_at(text, i).strip().lower()
            inner = text[i + 2 : end - 2]
            if name in _LIST_TEMPLATE_NAMES:
                _, _, args_text = inner.partition("|")
                items = []
                for part in split_top_level(args_text, "|"):
                    for line in part.split("\n"):
                        line = line.strip().lstrip("*").strip()
                        if line:
                            items.append(line)
                # Leading "\n" even when nothing preceded it on this line: the template's own
                # text may directly abut unrelated preceding text with no separator (a headline
                # number immediately followed by "{{Ubl|...}}", say), and without it the two
                # would merge into one unparseable segment.
                out.append("\n" + "\n".join(items))
            else:
                out.append("{{" + _unwrap_list_templates(inner) + "}}")
            i = end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _clean_for_parsing(raw_value: str) -> str:
    text = strip_templates(raw_value, _is_footnote_template)
    text = _REF_TAG_RE.sub("", text)
    text = _SELF_CLOSE_REF_RE.sub("", text)
    text = _COMMENT_RE.sub("", text)
    text = _ARG_TEMPLATE_RE.sub(lambda m: m.group(1) or "", text)
    text = _NDASH_RE.sub("–", text)
    text = _BULLET_TEMPLATE_RE.sub("\n*", text)
    text = _TREE_LIST_RE.sub("", text)
    text = _TREE_LIST_END_RE.sub("", text)
    text = _unwrap_list_templates(text)
    text = _BR_RE.sub("\n", text)
    text = _HR_RE.sub("\n", text)
    text = strip_templates(text, lambda name: True)  # catch-all: anything else is leftover markup
    text = _WIKILINK_RE.sub(r"\1", text)
    text = _BOLD_ITALIC_RE.sub("", text)
    text = _CITATION_BRACKET_RE.sub("", text)
    return text


def _parse_number_segment(segment: str) -> ExtractedNumber | None:
    """A single segment's number, or None for qualitative text ("Heavy", "Unknown") and
    equipment counts ("40+ cannon") — neither contributes to a troop/casualty total."""
    if not segment or _EQUIPMENT_RE.search(segment):
        return None
    range_match = _RANGE_RE.search(segment)
    if range_match:
        low = _to_number(range_match.group(1), range_match.group(2))
        high = _to_number(range_match.group(3), range_match.group(4))
        if low > high:
            low, high = high, low
        return ExtractedNumber(point=round((low + high) / 2), low=low, high=high)
    number_match = _NUMBER_RE.search(segment)
    if not number_match:
        return None
    return ExtractedNumber(point=_to_number(number_match.group(1), number_match.group(2)))


def extract_numeric_field(raw_value: str) -> ExtractedNumber:
    """Parse one infobox strength/casualty field's raw (unstripped) wikitext value.

    Rule (see module docstring for the real examples behind it): if the first parseable segment
    is a bare number/range, trust it alone — everything after is a citation, a breakdown of that
    same total, or a different unit, never an addend. Otherwise (no bare total was ever stated —
    the first parseable segment names a casualty category, a unit type, or a per-nation label)
    every parsed segment is summed.

    >>> extract_numeric_field("50,000 (33,000 infantry, 7,000 cavalry)")
    ExtractedNumber(point=50000, low=None, high=None)
    >>> extract_numeric_field("500 killed\\n1,200 wounded\\n300 captured")
    ExtractedNumber(point=2000, low=None, high=None)
    >>> extract_numeric_field("Unknown")
    ExtractedNumber(point=None, low=None, high=None)
    """
    text = _clean_for_parsing(raw_value)
    segments = [s.strip().lstrip("*").strip() for s in re.split(r"\n|;", text)]
    segments = [s for s in segments if s]

    per_segment = [_parse_number_segment(s) for s in segments]
    parsed_indices = [i for i, parsed in enumerate(per_segment) if parsed is not None]
    if not parsed_indices:
        return ExtractedNumber(None)

    first = parsed_indices[0]
    if _is_headline(segments[first]):
        return per_segment[first]

    present = [per_segment[i] for i in parsed_indices]
    total_point = sum(parsed.point for parsed in present)
    if any(parsed.low is not None for parsed in present):
        total_low = sum(parsed.low if parsed.low is not None else parsed.point for parsed in present)
        total_high = sum(parsed.high if parsed.high is not None else parsed.point for parsed in present)
        return ExtractedNumber(total_point, total_low, total_high)
    return ExtractedNumber(total_point)


_NUMERIC_FIELD_NAMES = ("strength1", "strength2", "casualties1", "casualties2")


def extract_strength_and_casualties(wikitext: str) -> dict[str, ExtractedNumber]:
    """Parse strength1/strength2/casualties1/casualties2 from a page's raw wikitext infobox.

    Returns {} if no `{{Infobox military conflict ...}}` is found; omits any of the four field
    names the infobox doesn't set. Callers combine this with commander-based side assignment
    (C3, not yet built) to know which of strength1/strength2 is "own" vs. "enemy".
    """
    body = find_infobox_body(wikitext)
    if body is None:
        return {}
    result = {}
    for name, raw_value in split_infobox_params(body):
        if name in _NUMERIC_FIELD_NAMES:
            result[name] = extract_numeric_field(raw_value)
    return result
