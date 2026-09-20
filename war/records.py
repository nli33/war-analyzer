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
    own_troop_strength: int
    enemy_troop_strength: int
    own_casualties: int
    enemy_casualties: int
    outcome: str
    decisiveness: str | None
    objective_secured: bool
    opponent_general_id: str | None
    resource_backing_tier: int
    tech_era_tier: int
    political_constraint_flag: bool
    source_confidence: str
    source_citation: str
    notes: str | None


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


def _battle_from_row(row: dict) -> Battle:
    return Battle(
        battle_id=row["battle_id"].strip(),
        general_id=row["general_id"].strip(),
        battle_name=row["battle_name"].strip(),
        date=row["date"].strip(),
        era=row["era"].strip(),
        own_troop_strength=int(row["own_troop_strength"]),
        enemy_troop_strength=int(row["enemy_troop_strength"]),
        own_casualties=int(row["own_casualties"]),
        enemy_casualties=int(row["enemy_casualties"]),
        outcome=row["outcome"].strip(),
        decisiveness=_optional(row["decisiveness"]),
        objective_secured=schema.parse_bool(row["objective_secured"]),
        opponent_general_id=_optional(row["opponent_general_id"]),
        resource_backing_tier=int(row["resource_backing_tier"]),
        tech_era_tier=int(row["tech_era_tier"]),
        political_constraint_flag=schema.parse_bool(row["political_constraint_flag"]),
        source_confidence=row["source_confidence"].strip(),
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
