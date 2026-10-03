"""C6: assemble `data/auto/battles.csv` rows from one battle page's wikitext.

Combines every piece Phase C already built standalone (C2's `war.infobox_numbers`, C3's
`war.commanders`, C4b's `war.roster` side-aware pairing, B2/C6's `war.rules`) into one row per
roster general per battle, in `war.schema.BATTLE_COLUMNS` shape. The CLI driver that crawls the
battle universe, loads the roster and C5's resolved fields, and writes the CSV is
`scripts/build_auto_battles.py`.

A battle page contributes zero, one, or two rows: one per side whose primary commander (C3's
rule) is both wikilinked (has a `general_id`) and on the roster (`war.roster`'s C4b selection).
A row is dropped (not written) rather than written with a fabricated value when either of the
two columns the schema requires can't be derived at all: `outcome` (see
`war.rules.outcome_from_result` for when that fails) or `date`/`era` (when `war.roster.extract_year`
finds no year-shaped text in the infobox `date` field). Every numeric field
(own/enemy strength and casualties) stays `None` rather than dropping the row when it alone is
missing — nullable by design since B1.
"""

from __future__ import annotations

from war.commanders import extract_commander_fields, primary_commander
from war.infobox_numbers import extract_strength_and_casualties
from war.roster import extract_year
from war.rules import (
    decisiveness_from_result,
    era_for_year,
    outcome_from_result,
    resource_backing_tier,
    tech_era_tier_for_year,
)
from war.schema import format_year
from war.scrape import parse_military_infobox

_SIDE_NUMBERS = ("1", "2")


def _resolved_point(
    field_numbers: dict, resolved_fields: dict, field_name: str
) -> int | None:
    """A field's point estimate: regex-parsed (C2) if present, else C5's LLM-resolved value."""
    extracted = field_numbers.get(field_name)
    if extracted is not None and extracted.point is not None:
        return extracted.point
    return resolved_fields.get(field_name)


def build_battle_rows(
    title: str,
    wikitext: str,
    roster_ids: set[str],
    resolved_fields: dict | None = None,
    identity_resolver: dict[str, str | None] | None = None,
) -> list[dict]:
    """Zero-to-two `war.schema.BATTLE_COLUMNS`-shaped dict rows for one battle page.

    `resolved_fields` is one battle's entry from C5's `data/auto/c5_resolved_fields.json`
    (`{"strength1": 30000, ...}`), used as a fallback only where C2's regex parser found no
    number at all. `roster_ids` is `war.roster`'s C4b-selected general id set — a side whose
    primary commander isn't in it produces no row. `identity_resolver` (E2's
    `war.identity.build_general_id_resolver` output) is forwarded to
    `war.commanders.extract_commander_fields` unchanged, so `general_id`/`opponent_general_id`
    here use the same canonicalized ids `roster_ids` was built from; `None` keeps the pre-E2
    raw-slug behavior.
    """
    resolved_fields = resolved_fields or {}

    infobox = parse_military_infobox(wikitext)
    year = extract_year(infobox.get("date"))
    if year is None:
        return []

    commander_fields = extract_commander_fields(wikitext, identity_resolver)
    primaries = {
        side: primary_commander(commander_fields.get(f"commander{side}", []))
        for side in _SIDE_NUMBERS
    }
    if not any(primaries.values()):
        return []

    outcome1, outcome2 = outcome_from_result(
        infobox.get("result"), infobox.get("combatant1"), infobox.get("combatant2")
    )
    outcomes = {"1": outcome1, "2": outcome2}

    field_numbers = extract_strength_and_casualties(wikitext)
    era = era_for_year(year)
    date_text = format_year(year)
    tech_tier = tech_era_tier_for_year(year)
    backing_tier = resource_backing_tier(year, era)  # no general->COW state mapping available

    rows = []
    for side, other_side in (("1", "2"), ("2", "1")):
        mine = primaries[side]
        if mine is None or mine.general_id not in roster_ids:
            continue
        outcome = outcomes[side]
        if outcome is None:
            continue
        theirs = primaries[other_side]
        result_text = infobox.get("result")

        own_strength = _resolved_point(field_numbers, resolved_fields, f"strength{side}")
        enemy_strength = _resolved_point(field_numbers, resolved_fields, f"strength{other_side}")
        own_casualties = _resolved_point(field_numbers, resolved_fields, f"casualties{side}")
        enemy_casualties = _resolved_point(field_numbers, resolved_fields, f"casualties{other_side}")

        rows.append(
            {
                "general_id": mine.general_id,
                "display_name": mine.display_name,
                "battle_title": title,
                "date": date_text,
                "era": era,
                "own_troop_strength": own_strength,
                "own_troop_strength_low": None,
                "own_troop_strength_high": None,
                "enemy_troop_strength": enemy_strength,
                "enemy_troop_strength_low": None,
                "enemy_troop_strength_high": None,
                "own_casualties": own_casualties,
                "own_casualties_low": None,
                "own_casualties_high": None,
                "enemy_casualties": enemy_casualties,
                "enemy_casualties_low": None,
                "enemy_casualties_high": None,
                "outcome": outcome,
                "decisiveness": decisiveness_from_result(result_text, outcome),
                "opponent_general_id": theirs.general_id if theirs else None,
                "resource_backing_tier": backing_tier,
                "tech_era_tier": tech_tier,
                "source_citation": f"Wikipedia infobox: {title} (auto-ingested, C6)",
                "notes": None,
            }
        )
    return rows
