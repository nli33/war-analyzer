"""Canonical schema for the battle-level dataset.

This is the authoritative definition of `data/battles.csv` and `data/generals.csv`
(PLAN.md Section 2 is the prose version; this module is what the code enforces).
Every column name, type, and allowed value lives here so the loader, the validation
script, and the metrics pipeline all agree on one description of the data.

Conventions used across both files:

* Dates are strings in `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` form. Years before 1 CE
  are written with a leading minus and are astronomical-style: `-0052` means 52 BC
  as historians write it (we do not bother with the year-zero offset; a one-year
  shift is far below the resolution of anything we compute). `parse_year` pulls
  the signed year back out.
* Booleans are the lowercase strings `true` / `false`.
* Empty cells mean "not recorded". Required fields may not be empty; optional
  fields may.
* Numeric estimates (strengths, casualties) are best single-point estimates. The
  honesty about how good that estimate is lives in `source_confidence`, which is
  what drives the Monte Carlo resampling later in the pipeline.
"""

from dataclasses import dataclass


# --- Enumerations -----------------------------------------------------------

ERAS = (
    "Ancient",
    "Medieval",
    "Early Modern",
    "Napoleonic",
    "Industrial",
    "WWII",
)

OUTCOMES = ("Win", "Loss", "Draw")

# Describes the *result of the battle for this general*, not just a win flavour:
#   Tactical  - won (or held) the field, but it bought no lasting strategic gain
#   Strategic - the result advanced the campaign's actual objective
#   Pyrrhic   - nominally the winner, but the cost gutted the force
#   Rout      - one side's army broke and was destroyed or scattered
# For a Loss, "Rout" means this general's own army was the one that broke.
DECISIVENESS_LEVELS = ("Tactical", "Strategic", "Pyrrhic", "Rout")

SOURCE_CONFIDENCE_LEVELS = ("High", "Medium", "Low")

BOOL_STRINGS = ("true", "false")

# 1-5 tiers. Both are judgement calls made relative to the general's own period,
# documented per row by the citation:
#   resource_backing_tier - manpower reserves, treasury, industrial capacity the
#       general could actually draw on at the time of the battle. 1 = scraping by
#       on what is already in the field, 5 = a state able to replace the army.
#   tech_era_tier - weapons/logistics/communications technology of the period,
#       used to normalise across eras. 1 = pre-gunpowder muscle-and-animal
#       logistics, 5 = mechanised warfare with radio and rail.
TIER_MIN = 1
TIER_MAX = 5


# --- Field specification ----------------------------------------------------

@dataclass(frozen=True)
class Column:
    """One CSV column: what it is, and what counts as a legal value."""

    name: str
    kind: str  # "text" | "int" | "bool" | "enum" | "date"
    description: str
    required: bool = True
    choices: tuple = ()
    min_value: int | None = None
    max_value: int | None = None


BATTLE_COLUMNS: tuple[Column, ...] = (
    Column(
        name="battle_id",
        kind="text",
        description="Stable slug for the row, e.g. 'caesar-alesia-52bc'. Unique across the file.",
    ),
    Column(
        name="general_id",
        kind="text",
        description="Slug of the commanding general; foreign key into generals.csv.",
    ),
    Column(
        name="battle_name",
        kind="text",
        description="Common English name of the battle or campaign.",
    ),
    Column(
        name="date",
        kind="date",
        description="YYYY, YYYY-MM, or YYYY-MM-DD; negative year for BC (see module docstring).",
    ),
    Column(
        name="era",
        kind="enum",
        description="Era cohort the battle belongs to; rate stats are z-scored within this.",
        choices=ERAS,
    ),
    Column(
        name="own_troop_strength",
        kind="int",
        description="Estimated troops under this general's command at the battle.",
        min_value=0,
    ),
    Column(
        name="enemy_troop_strength",
        kind="int",
        description="Estimated troops on the opposing side.",
        min_value=0,
    ),
    Column(
        name="own_casualties",
        kind="int",
        description="Estimated killed, wounded, captured, and missing on this general's side.",
        min_value=0,
    ),
    Column(
        name="enemy_casualties",
        kind="int",
        description="Estimated killed, wounded, captured, and missing on the opposing side.",
        min_value=0,
    ),
    Column(
        name="outcome",
        kind="enum",
        description="Result from this general's point of view.",
        choices=OUTCOMES,
    ),
    Column(
        name="decisiveness",
        kind="enum",
        description=(
            "How decisive the result was (see DECISIVENESS_LEVELS). Required for a Win; "
            "may be empty for a Loss or Draw where no stronger label than the outcome applies."
        ),
        required=False,
        choices=DECISIVENESS_LEVELS,
    ),
    Column(
        name="objective_secured",
        kind="bool",
        description="Was the general's stated objective (territory, siege, destruction of a force) achieved.",
    ),
    Column(
        name="opponent_general_id",
        kind="text",
        description=(
            "Slug of the opposing commander, for opponent adjustment. May reference a general "
            "who is not on the roster; may be empty when no single commander is identifiable."
        ),
        required=False,
    ),
    Column(
        name="resource_backing_tier",
        kind="int",
        description="1-5, resources behind the general at this battle (see module constants).",
        min_value=TIER_MIN,
        max_value=TIER_MAX,
    ),
    Column(
        name="tech_era_tier",
        kind="int",
        description="1-5, technology level of the period (see module constants).",
        min_value=TIER_MIN,
        max_value=TIER_MAX,
    ),
    Column(
        name="political_constraint_flag",
        kind="bool",
        description="Was the general under significant political interference in this battle.",
    ),
    Column(
        name="source_confidence",
        kind="enum",
        description="How reliable the strength/casualty figures are; drives Monte Carlo spread.",
        choices=SOURCE_CONFIDENCE_LEVELS,
    ),
    Column(
        name="source_citation",
        kind="text",
        description="Where the numbers came from. Never empty.",
    ),
    Column(
        name="notes",
        kind="text",
        description="Free text: disagreements between sources, why a figure was chosen, caveats.",
        required=False,
    ),
)


GENERAL_COLUMNS: tuple[Column, ...] = (
    Column(
        name="general_id",
        kind="text",
        description="Slug used as the foreign key from battles.csv, e.g. 'julius-caesar'.",
    ),
    Column(
        name="display_name",
        kind="text",
        description="Name as it should appear in rankings and charts.",
    ),
    Column(
        name="era",
        kind="enum",
        description="Primary era cohort for this general.",
        choices=ERAS,
    ),
    Column(
        name="career_start_year",
        kind="int",
        description="Year of first independent command (negative for BC).",
    ),
    Column(
        name="career_end_year",
        kind="int",
        description="Year of last command (negative for BC).",
    ),
    Column(
        name="notes",
        kind="text",
        description="Free text: scope of the career covered, known data gaps.",
        required=False,
    ),
)


BATTLE_FIELD_NAMES: tuple[str, ...] = tuple(c.name for c in BATTLE_COLUMNS)
GENERAL_FIELD_NAMES: tuple[str, ...] = tuple(c.name for c in GENERAL_COLUMNS)

BATTLES_CSV = "data/battles.csv"
GENERALS_CSV = "data/generals.csv"


def column(columns: tuple[Column, ...], name: str) -> Column:
    """Look up a column spec by name."""
    for spec in columns:
        if spec.name == name:
            return spec
    raise KeyError(f"no such column: {name}")


# --- Value parsing ----------------------------------------------------------

def parse_year(date_text: str) -> int:
    """Return the signed year from a schema date string.

    >>> parse_year("1815-06-18")
    1815
    >>> parse_year("-0331-10-01")
    -331
    """
    text = date_text.strip()
    if not text:
        raise ValueError("empty date")

    negative = text.startswith("-")
    if negative:
        text = text[1:]

    year_text = text.split("-")[0]
    if not year_text.isdigit():
        raise ValueError(f"cannot read a year from date {date_text!r}")

    year = int(year_text)
    return -year if negative else year


def parse_bool(text: str) -> bool:
    """Parse the lowercase 'true'/'false' the schema uses."""
    value = text.strip().lower()
    if value not in BOOL_STRINGS:
        raise ValueError(f"expected one of {BOOL_STRINGS}, got {text!r}")
    return value == "true"


def format_bool(value: bool) -> str:
    """Inverse of parse_bool, so writers and readers stay consistent."""
    return "true" if value else "false"
