"""Typed in-memory records for `data/battles.csv` and `data/generals.csv`.

`war/schema.py` defines what a legal cell looks like; `war/validate.py` checks
raw CSV text against that. This module is the next step down the pipeline:
it turns already-valid rows into typed dataclasses so the metrics pipeline
(Phase 3 onward) works with ints/bools/Optional[str], not raw strings.

Loading does not re-validate — run `scripts/validate_data.py` first. A row
that fails schema validation will raise here instead of loading silently.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from war import schema

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Battle:
    """One row of `data/battles.csv`, typed."""

    battle_id: str
    general_id: str
    battle_name: str
    date: str
    era: str
    own_troop_strength: int | None
    enemy_troop_strength: int | None
    own_casualties: int | None
    enemy_casualties: int | None
    outcome: str
    decisiveness: str | None
    opponent_general_id: str | None
    resource_backing_tier: int
    tech_era_tier: int
    source_citation: str
    notes: str | None
    # Low/high range siblings for when two sources disagree (see schema.py's
    # module docstring); default None since most battles have a single source.
    own_troop_strength_low: int | None = None
    own_troop_strength_high: int | None = None
    enemy_troop_strength_low: int | None = None
    enemy_troop_strength_high: int | None = None
    own_casualties_low: int | None = None
    own_casualties_high: int | None = None
    enemy_casualties_low: int | None = None
    enemy_casualties_high: int | None = None


@dataclass(frozen=True)
class General:
    """One row of `data/generals.csv`, typed."""

    general_id: str
    display_name: str
    era: str
    career_start_year: int
    career_end_year: int
    notes: str | None


def _optional(value: str) -> str | None:
    value = value.strip()
    return value if value else None


def _optional_int(value: str) -> int | None:
    value = value.strip()
    return int(value) if value else None


def _battle_from_row(row: dict) -> Battle:
    return Battle(
        battle_id=row["battle_id"].strip(),
        general_id=row["general_id"].strip(),
        battle_name=row["battle_name"].strip(),
        date=row["date"].strip(),
        era=row["era"].strip(),
        own_troop_strength=_optional_int(row["own_troop_strength"]),
        own_troop_strength_low=_optional_int(row["own_troop_strength_low"]),
        own_troop_strength_high=_optional_int(row["own_troop_strength_high"]),
        enemy_troop_strength=_optional_int(row["enemy_troop_strength"]),
        enemy_troop_strength_low=_optional_int(row["enemy_troop_strength_low"]),
        enemy_troop_strength_high=_optional_int(row["enemy_troop_strength_high"]),
        own_casualties=_optional_int(row["own_casualties"]),
        own_casualties_low=_optional_int(row["own_casualties_low"]),
        own_casualties_high=_optional_int(row["own_casualties_high"]),
        enemy_casualties=_optional_int(row["enemy_casualties"]),
        enemy_casualties_low=_optional_int(row["enemy_casualties_low"]),
        enemy_casualties_high=_optional_int(row["enemy_casualties_high"]),
        outcome=row["outcome"].strip(),
        decisiveness=_optional(row["decisiveness"]),
        opponent_general_id=_optional(row["opponent_general_id"]),
        resource_backing_tier=int(row["resource_backing_tier"]),
        tech_era_tier=int(row["tech_era_tier"]),
        source_citation=row["source_citation"].strip(),
        notes=_optional(row["notes"]),
    )


def _general_from_row(row: dict) -> General:
    return General(
        general_id=row["general_id"].strip(),
        display_name=row["display_name"].strip(),
        era=row["era"].strip(),
        career_start_year=int(row["career_start_year"]),
        career_end_year=int(row["career_end_year"]),
        notes=_optional(row["notes"]),
    )


def load_battles(path: Path | str = REPO_ROOT / schema.BATTLES_CSV) -> list[Battle]:
    """Load and type every row of a battles CSV, in file order."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [_battle_from_row(row) for row in csv.DictReader(handle)]


def load_generals(path: Path | str = REPO_ROOT / schema.GENERALS_CSV) -> list[General]:
    """Load and type every row of a generals CSV, in file order."""
    with open(path, newline="", encoding="utf-8") as handle:
        return [_general_from_row(row) for row in csv.DictReader(handle)]
