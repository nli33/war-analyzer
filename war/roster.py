"""C4b: turn the C1 battle universe + C2/C3 extraction into a selected general roster.

Scans every candidate battle page (C1's `data/raw/battle_universe.csv`), parses commanders (C3)
and strength numbers (C2) from each infobox, and inverts each page into 0-2 `BattleAppearance`s
— one per side with an identifiable primary commander. `select_roster` then keeps a general (C4a
seed or not) if they have at least `min_usable_battles` battles where *both* sides' troop
strength were extracted — PROGRESS.md's "usable strength figures" line. A non-seed general may
still join if they turn up as the opponent in a kept general's battle and clear the same bar
(PROGRESS.md: "Opponents who appear in kept battles but are not on the seed list may join if
they clear the same bar") — this is deliberately a one-hop-from-a-kept-general join, not "anyone
in the whole universe with enough battles," so an unrelated figure the seed crawl simply missed
doesn't enter just because they happen to have fought a lot.

`generals_csv_rows` then builds `GENERAL_COLUMNS`-shaped rows: era and career years come from
the dates of the general's own kept battles (`war.rules.era_for_year`), not hand judgment.
"""

from __future__ import annotations

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


def battle_appearances(title: str, wikitext: str) -> list[BattleAppearance]:
    """Parse one battle page into 0-2 `BattleAppearance`s (combines C2 + C3, side-aware).

    `war.commanders.invert_to_general_battles` already does the commander-only half of this
    inversion, but its output doesn't carry which original infobox side (1 or 2) a link came
    from, which is exactly what's needed to pair a general with their *own* (not the
    opponent's) strength number — so this re-derives the side-aware pairing directly from
    `primary_commander` on each side instead of calling it.
    """
    year = extract_year(parse_military_infobox(wikitext).get("date"))

    commander_fields = extract_commander_fields(wikitext)
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


def seed_general_ids(seed_titles: list[str]) -> set[str]:
    """C4a's seed roster titles, slugged the same way commander wikilinks are (C3)."""
    return {general_id_from_title(title) for title in seed_titles}


def select_roster(
    appearances: list[BattleAppearance],
    seed_ids: set[str],
    min_usable_battles: int,
) -> dict[str, list[BattleAppearance]]:
    """Return `{general_id: [appearances]}` for the selected roster (see module docstring for
    the seed-bar / opponent-join rule)."""
    by_general: dict[str, list[BattleAppearance]] = defaultdict(list)
    for appearance in appearances:
        by_general[appearance.general_id].append(appearance)

    usable_count = {
        general_id: sum(1 for a in items if a.has_usable_strength)
        for general_id, items in by_general.items()
    }

    kept: set[str] = {
        general_id for general_id in seed_ids if usable_count.get(general_id, 0) >= min_usable_battles
    }

    changed = True
    while changed:
        changed = False
        opponents_of_kept = {
            appearance.opponent_general_id
            for general_id in kept
            for appearance in by_general[general_id]
            if appearance.opponent_general_id
        }
        for opponent_id in opponents_of_kept - kept:
            if usable_count.get(opponent_id, 0) >= min_usable_battles:
                kept.add(opponent_id)
                changed = True

    return {general_id: by_general[general_id] for general_id in kept}


def generals_csv_rows(roster: dict[str, list[BattleAppearance]]) -> list[dict]:
    """Build `war.schema.GENERAL_COLUMNS`-shaped rows from a selected roster.

    A general with no dateable battle (every `date` field unparseable) is dropped here — the
    schema requires `career_start_year`/`career_end_year`, and there is nothing to derive them
    from. `era` is the most common `era_for_year` result across the general's own battles, not
    just their first one, since a long career can span a boundary.
    """
    rows = []
    for general_id, items in sorted(roster.items()):
        years = [a.year for a in items if a.year is not None]
        if not years:
            continue
        era_counts = Counter(era_for_year(year) for year in years)
        era = era_counts.most_common(1)[0][0]
        usable = sum(1 for a in items if a.has_usable_strength)
        rows.append(
            {
                "general_id": general_id,
                "display_name": items[0].display_name,
                "era": era,
                "career_start_year": min(years),
                "career_end_year": max(years),
                "notes": (
                    f"auto-generated (C4b): {usable} usable-strength battle(s) "
                    f"of {len(items)} found"
                ),
            }
        )
    return rows
