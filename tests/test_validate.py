"""Tests for the Phase 2 data validation script (war/validate.py)."""

import csv
from pathlib import Path

import pytest

from war import schema
from war.validate import ValidationError, validate_all, validate_file, validate_value

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- validate_value: one column at a time -----------------------------------

def test_required_field_empty_is_rejected():
    outcome_spec = schema.column(schema.BATTLE_COLUMNS, "outcome")
    with pytest.raises(ValidationError):
        validate_value(outcome_spec, "")


def test_optional_field_empty_is_fine():
    decisiveness_spec = schema.column(schema.BATTLE_COLUMNS, "decisiveness")
    validate_value(decisiveness_spec, "")  # must not raise


def test_valid_enum_passes():
    outcome_spec = schema.column(schema.BATTLE_COLUMNS, "outcome")
    validate_value(outcome_spec, "Win")


def test_invalid_enum_is_rejected():
    outcome_spec = schema.column(schema.BATTLE_COLUMNS, "outcome")
    with pytest.raises(ValidationError):
        validate_value(outcome_spec, "Victory")


def test_negative_numeric_is_rejected():
    casualties_spec = schema.column(schema.BATTLE_COLUMNS, "own_casualties")
    with pytest.raises(ValidationError):
        validate_value(casualties_spec, "-5")


def test_non_negative_numeric_passes():
    casualties_spec = schema.column(schema.BATTLE_COLUMNS, "own_casualties")
    validate_value(casualties_spec, "0")


def test_tier_out_of_range_is_rejected():
    tier_spec = schema.column(schema.BATTLE_COLUMNS, "resource_backing_tier")
    with pytest.raises(ValidationError):
        validate_value(tier_spec, "6")


def test_bad_bool_is_rejected():
    flag_spec = schema.column(schema.BATTLE_COLUMNS, "objective_secured")
    with pytest.raises(ValidationError):
        validate_value(flag_spec, "yes")


def test_bad_date_is_rejected():
    date_spec = schema.column(schema.BATTLE_COLUMNS, "date")
    with pytest.raises(ValidationError):
        validate_value(date_spec, "52 BC")


def test_good_date_passes():
    date_spec = schema.column(schema.BATTLE_COLUMNS, "date")
    validate_value(date_spec, "-0052-09-02")


# --- validate_file / validate_all: whole-CSV behavior -----------------------

def _write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _valid_battle_row(battle_id: str = "b1", general_id: str = "gen-a") -> list[str]:
    """A row that satisfies every BATTLE_COLUMNS check, keyed by column order."""
    values = {
        "battle_id": battle_id,
        "general_id": general_id,
        "battle_name": "Some Battle",
        "date": "1800-01-01",
        "era": "Napoleonic",
        "own_troop_strength": "10000",
        "enemy_troop_strength": "12000",
        "own_casualties": "1000",
        "enemy_casualties": "2000",
        "outcome": "Win",
        "decisiveness": "Strategic",
        "objective_secured": "true",
        "opponent_general_id": "",
        "resource_backing_tier": "3",
        "tech_era_tier": "3",
        "political_constraint_flag": "false",
        "source_confidence": "High",
        "source_citation": "Some Source, 1900",
        "notes": "",
    }
    return [values[name] for name in schema.BATTLE_FIELD_NAMES]


def test_validate_file_accepts_clean_row(tmp_path):
    csv_path = tmp_path / "battles.csv"
    _write_csv(csv_path, list(schema.BATTLE_FIELD_NAMES), [_valid_battle_row()])
    assert validate_file(csv_path, schema.BATTLE_COLUMNS) == []


def test_validate_file_reports_missing_citation(tmp_path):
    csv_path = tmp_path / "battles.csv"
    row = _valid_battle_row()
    row[schema.BATTLE_FIELD_NAMES.index("source_citation")] = ""
    _write_csv(csv_path, list(schema.BATTLE_FIELD_NAMES), [row])
    errors = validate_file(csv_path, schema.BATTLE_COLUMNS)
    assert any("source_citation" in error for error in errors)


def test_validate_file_reports_duplicate_ids(tmp_path):
    csv_path = tmp_path / "battles.csv"
    rows = [_valid_battle_row(battle_id="dup"), _valid_battle_row(battle_id="dup")]
    _write_csv(csv_path, list(schema.BATTLE_FIELD_NAMES), rows)
    errors = validate_file(csv_path, schema.BATTLE_COLUMNS)
    assert any("duplicate" in error for error in errors)


def test_validate_all_catches_orphan_general_id(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _write_csv(
        data_dir / "battles.csv",
        list(schema.BATTLE_FIELD_NAMES),
        [_valid_battle_row(general_id="nobody")],
    )
    _write_csv(data_dir / "generals.csv", list(schema.GENERAL_FIELD_NAMES), [])

    errors = validate_all(repo_root=tmp_path)
    assert any("nobody" in error and "generals.csv" in error for error in errors)


def test_current_repo_data_is_clean():
    """data/*.csv today is header-only (Phase 2 curation hasn't landed yet), so this
    should pass trivially; it'll start doing real work once battle rows are added."""
    assert validate_all(repo_root=REPO_ROOT) == []
