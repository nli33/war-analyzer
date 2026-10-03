"""C4b: turn the C1 battle universe + C2/C3 extraction into a selected general roster.

Scans every candidate battle page (C1's `data/raw/battle_universe.csv`), parses commanders (C3)
and strength numbers (C2) from each infobox, and inverts each page into 0-2 `BattleAppearance`s
-- one per side with an identifiable primary commander. `select_roster` then keeps *any* general
(seed-listed or not) with at least `min_usable_battles` battles where both sides' troop strength
were extracted -- PROGRESS.md's "usable strength figures" line. E4 dropped the original seed-list
gate (a non-seed general used to need to additionally face an already-kept general to join); the
seed list is now purely informational, carried through to `generals_csv_rows`'s `notes` column
rather than used to decide membership. `must_include_ids` (PROGRESS.md's must-include list, E3)
forces membership regardless of `min_usable_battles`, including generals with zero appearances at
all -- callers are expected to check `usable_battle_counts` themselves and substitute hand-curated
data for any must-include general that's still thin (see `scripts/build_roster_selection.py`).

`generals_csv_rows` then builds `GENERAL_COLUMNS`-shaped rows: era and career years come from
the dates of the general's own kept battles (`war.rules.era_for_year`), not hand judgment.
"""

import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from war.commanders import extract_commander_fields, general_id_from_title, primary_commander
from war.infobox_numbers import extract_strength_and_casualties
from war.rules import era_for_year
from war.scrape import parse_military_infobox

# A year with an explicit BC/BCE marker directly after it (allowing for "B.C."/"B.C.E." dotted
# spellings) is unambiguous. Without one, a bare 3-4 digit number is taken to be the year — a
# day-of-month number in a date like "18 June 1815" is at most 2 digits, so this does not need
# to disambiguate against it. Century-only dates ("4th century BC") have no digit run matching
# either pattern and come back None — a known, accepted gap (same tradeoff C1/C4a's "recall
# first, drop what a simple pattern misses" makes), not worth a bespoke parser for.
_BC_YEAR_RE = re.compile(r"(\d{1,4})\s*(?:BCE|BC|B\.C\.E?\.?)\b", re.IGNORECASE)
_PLAIN_YEAR_RE = re.compile(r"\b(\d{3,4})\b")


def extract_year(date_field: str | None) -> int | None:
    """Pull one headline year out of an infobox `date` field's free text. None if no year-shaped
    number is found at all (see module-level note on the century-only gap).

    >>> extract_year("18 June 1815")
    1815
    >>> extract_year("9 August 48 BC")
    -48
    >>> extract_year("1861-1865")
    1861
    >>> extract_year(None)
    """
    if not date_field:
        return None
    bc_match = _BC_YEAR_RE.search(date_field)
    if bc_match:
        return -int(bc_match.group(1))
    plain_match = _PLAIN_YEAR_RE.search(date_field)
    if plain_match:
        return int(plain_match.group(1))
    return None


@dataclass(frozen=True)
class BattleAppearance:
    """One general's perspective on one battle page, found by scanning the battle universe."""

    battle_title: str
    general_id: str
    display_name: str
    opponent_general_id: str | None
    year: int | None
    own_strength: int | None
    enemy_strength: int | None

    @property
    def has_usable_strength(self) -> bool:
        return (
            self.own_strength is not None
            and self.own_strength > 0
            and self.enemy_strength is not None
            and self.enemy_strength > 0
        )


def battle_appearances(
    title: str, wikitext: str, identity_resolver: dict[str, str | None] | None = None
) -> list[BattleAppearance]:
    """Parse one battle page into 0-2 `BattleAppearance`s (combines C2 + C3, side-aware).

    `war.commanders.invert_to_general_battles` already does the commander-only half of this
    inversion, but its output doesn't carry which original infobox side (1 or 2) a link came
    from, which is exactly what's needed to pair a general with their *own* (not the
    opponent's) strength number — so this re-derives the side-aware pairing directly from
    `primary_commander` on each side instead of calling it.

    `identity_resolver` (E2's `war.identity.build_general_id_resolver` output) is forwarded to
    `war.commanders.extract_commander_fields` unchanged; `None` (the default) keeps the pre-E2
    raw-slug behavior.
    """
    year = extract_year(parse_military_infobox(wikitext).get("date"))

    commander_fields = extract_commander_fields(wikitext, identity_resolver)
    side1 = commander_fields.get("commander1", [])
    side2 = commander_fields.get("commander2", [])
    primary1 = primary_commander(side1)
    primary2 = primary_commander(side2)

    numbers = extract_strength_and_casualties(wikitext)
    strength1 = numbers.get("strength1")
    strength2 = numbers.get("strength2")
    point1 = strength1.point if strength1 else None
    point2 = strength2.point if strength2 else None

    appearances = []
    for mine, theirs, my_strength, their_strength in (
        (primary1, primary2, point1, point2),
        (primary2, primary1, point2, point1),
    ):
        if mine is None:
            continue
        appearances.append(
            BattleAppearance(
                battle_title=title,
                general_id=mine.general_id,
                display_name=mine.display_name,
                opponent_general_id=theirs.general_id if theirs else None,
                year=year,
                own_strength=my_strength,
                enemy_strength=their_strength,
            )
        )
    return appearances


def seed_general_ids(
    seed_titles: list[str], identity_resolver: dict[str, str | None] | None = None
) -> set[str]:
    """C4a's seed roster titles, canonicalized the same way commander wikilinks are (E2) so seed
    membership and battle-commander `general_id`s are comparable after identity merging.

    A seed title that resolves to `None` (disambiguation — not expected for a general's own
    article, but not structurally ruled out) or that isn't a key in `identity_resolver` at all
    (E1's scan only covers titles seen as commander wikilink targets, not every seed-roster
    title) falls back to the raw slug rather than dropping the general from the seed set.
    """
    ids: set[str] = set()
    for title in seed_titles:
        resolved = identity_resolver.get(title) if identity_resolver is not None else None
        ids.add(resolved if resolved is not None else general_id_from_title(title))
    return ids


def usable_battle_counts(appearances: list[BattleAppearance]) -> dict[str, int]:
    """Usable-strength battle count per `general_id`, the number `select_roster`'s bar and E3/E4's
    thin-must-include checks both key off. Exposed separately so a caller can classify a
    must-include general as thin (usable count below the chosen `min_usable_battles`) without
    duplicating `select_roster`'s internal grouping."""
    counts: dict[str, int] = defaultdict(int)
    for appearance in appearances:
        if appearance.has_usable_strength:
            counts[appearance.general_id] += 1
    return dict(counts)


def pipeline_general_id_for(canonical_title: str, resolver: dict[str, str | None]) -> str:
    """The `general_id` the pipeline assigns to a person identified by their canonical Wikipedia
    title (as `data/must_include.csv` records it): the resolver's answer if that exact title was
    itself seen as a commander wikilink (and so is a resolver key), else the same raw-slug
    fallback every other pipeline caller uses for a title outside E1's scan."""
    resolved = resolver.get(canonical_title)
    return resolved if resolved is not None else general_id_from_title(canonical_title)


def select_roster(
    appearances: list[BattleAppearance],
    min_usable_battles: int,
    must_include_ids: frozenset[str] = frozenset(),
) -> dict[str, list[BattleAppearance]]:
    """Return `{general_id: [appearances]}` for the selected roster (see module docstring).

    E4: a general joins if they have at least `min_usable_battles` usable-strength battles,
    seed-listed or not -- no opponent-of-a-kept-general hop needed any more, since that hop only
    ever admitted generals who *already* cleared the bar on their own; the thing it depended on
    (the seed-only gate) is gone. Every id in `must_include_ids` joins unconditionally, even with
    zero appearances at all, so a thin must-include general still gets a (possibly empty) roster
    entry for the caller to detect via `usable_battle_counts` and substitute hand-curated data
    for (see `scripts/build_roster_selection.py`).
    """
    by_general: dict[str, list[BattleAppearance]] = defaultdict(list)
    for appearance in appearances:
        by_general[appearance.general_id].append(appearance)

    usable_count = usable_battle_counts(appearances)

    kept: set[str] = {
        general_id
        for general_id, count in usable_count.items()
        if count >= min_usable_battles
    }
    kept |= set(must_include_ids)

    return {general_id: by_general[general_id] for general_id in kept}


def generals_csv_rows(
    roster: dict[str, list[BattleAppearance]],
    seed_ids: frozenset[str] = frozenset(),
    extra_notes: dict[str, str] | None = None,
) -> list[dict]:
    """Build `war.schema.GENERAL_COLUMNS`-shaped rows from a selected roster.

    A general with no dateable battle (every `date` field unparseable) is dropped here — the
    schema requires `career_start_year`/`career_end_year`, and there is nothing to derive them
    from. `era` is the most common `era_for_year` result across the general's own battles, not
    just their first one, since a long career can span a boundary.

    `seed_ids` no longer gates membership (E4) but is still recorded in `notes` so the roster's
    seed/non-seed split stays visible. `extra_notes` (keyed by `general_id`) appends a caller-
    supplied sentence, e.g. E4's thin-must-include-with-no-hand-curated-fallback flag for Han Xin.
    """
    rows = []
    for general_id, items in sorted(roster.items()):
        years = [a.year for a in items if a.year is not None]
        if not years:
            continue
        era_counts = Counter(era_for_year(year) for year in years)
        era = era_counts.most_common(1)[0][0]
        usable = sum(1 for a in items if a.has_usable_strength)
        note = (
            f"auto-generated (C4b): {usable} usable-strength battle(s) of {len(items)} found "
            f"(seed={'true' if general_id in seed_ids else 'false'})"
        )
        if extra_notes and general_id in extra_notes:
            note += f"; {extra_notes[general_id]}"
        rows.append(
            {
                "general_id": general_id,
                "display_name": items[0].display_name,
                "era": era,
                "career_start_year": min(years),
                "career_end_year": max(years),
                "notes": note,
            }
        )
    return rows
