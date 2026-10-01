"""Commander/side extraction from a battle infobox, and the general-battle inversion (C3).

`war/scrape.py`'s `parse_military_infobox` cleans `commander1`/`commander2` the same generic way
as every other text field — it keeps only the *display* text of a wikilink
(`[[Target|Display]]` -> `Display`), throwing away `Target`, the one piece of information this
task actually needs: a Wikipedia page title that can become a `general_id` slug and, later
(C4), a source of career-year data. So this module re-parses those two raw (unstripped) field
values straight from `war.scrape.split_infobox_params`, the same "bypass the generic cleanup"
pattern `war/infobox_numbers.py` already uses for the numeric fields.

Real infobox commander fields list more than one name per side — co-commanders, subordinates, a
coalition's several national contingents — joined by `<br>`, commas, the word "and", or a
`{{plainlist|...}}`/`{{Ubl|...}}`/`{{tree list}}...{{tree list/end}}` template, often with a
decoration template stuck directly on a name (`{{KIA}}`, `{{WIA}}`) and no separator before the
next one. None of that changes *order*, though, and order is what this task's rule depends on: a
general counts as personally commanding a battle only if they are the first name listed on their
side (see `primary_commander`'s docstring for exactly what that misses).
"""

import re
from dataclasses import dataclass

from war.scrape import find_infobox_body, split_infobox_params
from war.wikitext import balanced_template_end, split_top_level, strip_templates, template_name_at

_COMMANDER_FIELD_NAMES = ("commander1", "commander2")

# Templates whose items are the actual list of commanders, unwrapped into one line per item
# rather than deleted. `{{tree list}}`/`{{tree list/end}}` (seen wrapping ancient-battle
# subordinate hierarchies, e.g. "*Caesar\n**Antony\n**...") are *not* here deliberately: they
# don't take their content as a template argument the way `{{ubl|...}}` does — the bulleted
# lines between the two tags are already plain wikitext, one per line — so the generic
# catch-all template strip below removes the two marker tags and leaves the lines untouched,
# with no special-casing needed.
_LIST_TEMPLATE_NAMES = frozenset(
    {
        "ubl",
        "ubli",
        "plainlist",
        "plain list",
        "indented plainlist",
        "unbulleted list",
        "flatlist",
        "bulletedlist",
        "bulleted list",
    }
)

_REF_TAG_RE = re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL)
_SELF_CLOSE_REF_RE = re.compile(r"<ref[^>]*/>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_HR_RE = re.compile(r"<hr\s*/?>", re.IGNORECASE)
_BOLD_ITALIC_RE = re.compile(r"'''?")
_WIKILINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|([^\]]*))?\]\]")
_SEGMENT_SPLIT_CHARS = "\n;,"
_AND_SPLIT_RE = re.compile(r"\s+and\s+", re.IGNORECASE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class CommanderRef:
    """One named commander on one side of a battle, in the order the infobox lists them.

    `general_id`/`wikipedia_title` are both `None` when the name isn't wikilinked — a real
    person, but with no Wikipedia page for C4 to pull era/career-year data from, so they can't
    become a usable roster entry no matter how the rest of this pipeline treats them.
    """

    display_name: str
    wikipedia_title: str | None
    general_id: str | None


@dataclass(frozen=True)
class GeneralBattleLink:
    """One identifiable general's perspective on a battle, inverted from the infobox's
    two-sided `commander1`/`commander2` view. `opponent_general_id`/`opponent_display_name`
    are `None` when the other side has no identifiable primary commander either.

    This stops at a single battle — callers (C6) accumulate `GeneralBattleLink`s across many
    battles into `general_id -> [battles]` and `generals.csv`/`battles.csv` rows; nothing here
    does that aggregation itself.
    """

    general_id: str
    display_name: str
    wikipedia_title: str
    opponent_general_id: str | None
    opponent_display_name: str | None


def general_id_from_title(title: str) -> str:
    """Slug a Wikipedia page title into a `general_id`, matching the gold set's style
    (`data/generals.csv`'s `julius-caesar`, `genghis-khan`): lowercase, non-alphanumeric runs
    collapsed to one hyphen, leading/trailing hyphens trimmed. A disambiguator in parentheses is
    kept (slugged like everything else) since it's what makes two same-named historical figures
    resolve to different ids.

    >>> general_id_from_title("Napoleon")
    'napoleon'
    >>> general_id_from_title("Lucius Aemilius Paullus (consul 216 BC)")
    'lucius-aemilius-paullus-consul-216-bc'
    """
    return _SLUG_RE.sub("-", title.strip().lower()).strip("-")


def _unwrap_list_templates(text: str) -> str:
    """Expand `{{ubl|a|b|c}}` / `{{plainlist|\\n* a\\n* b}}`-style templates into one item per
    line. Same approach as `war.infobox_numbers._unwrap_list_templates` (duplicated rather than
    imported — small, and the two modules' cleanup pipelines diverge enough elsewhere, e.g. this
    one keeps wikilinks, that sharing the function would need a parameter to describe what not
    to do)."""
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
                out.append("\n" + "\n".join(items))
            else:
                out.append("{{" + _unwrap_list_templates(inner) + "}}")
            i = end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def _clean_for_parsing(raw_value: str) -> str:
    text = _REF_TAG_RE.sub("", raw_value)
    text = _SELF_CLOSE_REF_RE.sub("", text)
    text = _COMMENT_RE.sub("", text)
    text = _unwrap_list_templates(text)
    text = strip_templates(text, lambda name: True)  # KIA/WIA/sfn/tree list markers/etc.
    text = _BR_RE.sub("\n", text)
    text = _HR_RE.sub("\n", text)
    text = _BOLD_ITALIC_RE.sub("", text)
    return text


def _ref_from_segment(segment: str) -> CommanderRef | None:
    segment = segment.strip().lstrip("*").strip()
    if not segment:
        return None
    # A real example this caught: a national flag-icon template directly ahead of the name,
    # `[[File:Royal flag of France.svg|22px]] [[Duke of Nemours|...]]`, with no separator this
    # module's segment splitter (newline/`;`/`,`/" and ") would ever break on — both wikilinks
    # land in the same segment. `_WIKILINK_RE.search` alone would grab the *first* one, the
    # image, and misread it as a commander; skip every namespaced link (File:/Image:/Category:/
    # a language-interwiki prefix — none of those is a person, same exclusion
    # war.scrape.extract_battle_titles already applies to list-page wikilinks) to find the real
    # name link, if any, instead of stopping at the first wikilink found.
    for match in _WIKILINK_RE.finditer(segment):
        title = match.group(1).split("#", 1)[0].strip()
        if title and ":" not in title:
            display = (match.group(2) or title).strip()
            return CommanderRef(
                display_name=display, wikipedia_title=title, general_id=general_id_from_title(title)
            )
    plain = re.sub(r"\[\[[^\]]*\]\]", "", segment).strip("[]").strip()
    if not plain:
        return None
    return CommanderRef(display_name=plain, wikipedia_title=None, general_id=None)


def parse_commander_field(raw_value: str) -> list[CommanderRef]:
    """Parse one infobox `commander1`/`commander2` raw (unstripped) wikitext value into an
    ordered list of commanders — ordered because `primary_commander` depends on it.

    Known limitations, inherent to parsing free text rather than structured data: a plain
    (non-wikilinked) name containing a literal comma or the word "and" could be mis-split into
    two entries; this doesn't come up in any real example checked while building this, but
    isn't structurally ruled out. The word "and" split (unlike the comma/semicolon/newline split
    just below) also isn't bracket-aware, so a wikilink target containing the word "and" (none
    found in a real example yet) could still be mis-split the same way a comma target used to be.

    >>> [ref.display_name for ref in parse_commander_field("[[Hannibal]]")]
    ['Hannibal']
    >>> [ref.display_name for ref in parse_commander_field("[[Napoleon]]<br>[[Michel Ney|Ney]]")]
    ['Napoleon', 'Ney']
    >>> [ref.general_id for ref in parse_commander_field(
    ...     "[[Arthur Wellesley, 1st Duke of Wellington|Arthur Wellesley]]")]
    ['arthur-wellesley-1st-duke-of-wellington']
    """
    text = _clean_for_parsing(raw_value)
    segments = []
    for piece in split_top_level(text, _SEGMENT_SPLIT_CHARS):
        segments.extend(_AND_SPLIT_RE.split(piece))

    refs = []
    for segment in segments:
        ref = _ref_from_segment(segment)
        if ref is not None:
            refs.append(ref)
    return refs


def extract_commander_fields(wikitext: str) -> dict[str, list[CommanderRef]]:
    """Parse `commander1`/`commander2` from a page's raw wikitext infobox.

    Returns `{}` if no `{{Infobox military conflict ...}}` is found; omits a field name the
    infobox doesn't set at all (an empty/whitespace-only value is also omitted — same "no data"
    convention `war.infobox_numbers.extract_strength_and_casualties` uses).
    """
    body = find_infobox_body(wikitext)
    if body is None:
        return {}
    result: dict[str, list[CommanderRef]] = {}
    for name, raw_value in split_infobox_params(body):
        if name in _COMMANDER_FIELD_NAMES and raw_value.strip():
            result[name] = parse_commander_field(raw_value)
    return result


def primary_commander(side: list[CommanderRef]) -> CommanderRef | None:
    """The commander who counts as personally commanding this side (C3's rule): whoever is
    listed first in the infobox commander field — provided that name is wikilinked.

    Known misses, inherent to reading infobox order as a command hierarchy rather than
    confirming it per battle (out of scope: no per-battle research, see PROGRESS.md):

    - Infobox order is whatever the article's editors wrote, not a verified seniority ranking.
      A joint-command or coalition battle may list a nominal/titular figure (a king present but
      not actually directing the battle) ahead of the real field commander, or list one
      coalition nation's commander first for no reason tied to overall seniority.
    - If the first-listed name has no Wikipedia page (common for minor commanders, and for
      ancient battles generally), nobody is treated as personally commanding this side even
      though a real person is named — a real name with no article is still not a usable roster
      entry for C4 (no page to pull era/career years from).
    - Spot-checked against real cached pages (Battle of Issus, Battle of Pharsalus): both mark
      the overall commander with wikitext bold (`'''[[Alexander the Great]]'''`) *and* list them
      first, so this rule and that convention agree on every example found — but the rule keys
      only on position, not on bold, since bold is inconsistently present across articles.
    """
    if not side:
        return None
    first = side[0]
    return first if first.general_id else None


def invert_to_general_battles(
    side1: list[CommanderRef], side2: list[CommanderRef]
) -> list[GeneralBattleLink]:
    """Turn a battle's two parsed commander sides into one `GeneralBattleLink` per side with an
    identifiable primary commander (see `primary_commander`).

    Both sides identifiable -> two links, each the other's `opponent_general_id`. One side
    identifiable -> one link, `opponent_general_id` is `None`. Neither -> `[]`.
    """
    primary1 = primary_commander(side1)
    primary2 = primary_commander(side2)

    links = []
    for mine, theirs in ((primary1, primary2), (primary2, primary1)):
        if mine is None:
            continue
        links.append(
            GeneralBattleLink(
                general_id=mine.general_id,
                display_name=mine.display_name,
                wikipedia_title=mine.wikipedia_title,
                opponent_general_id=theirs.general_id if theirs else None,
                opponent_display_name=theirs.display_name if theirs else None,
            )
        )
    return links
