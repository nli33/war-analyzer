"""Scaffold-level checks: the schema module and the CSV headers agree.

These exist mostly so the test harness has something real to run before the
dataset and the metrics pipeline land. The thorough row-by-row validation is a
separate script (Phase 2).
"""

import csv
from pathlib import Path

import pytest

from war import schema

REPO_ROOT = Path(__file__).resolve().parent.parent


def read_header(relative_path: str) -> list[str]:
    """Return the header row of a CSV in the repo."""
    with open(REPO_ROOT / relative_path, newline="", encoding="utf-8") as handle:
        return next(csv.reader(handle))


def test_battles_csv_header_matches_schema():
    assert read_header(schema.BATTLES_CSV) == list(schema.BATTLE_FIELD_NAMES)


def test_generals_csv_header_matches_schema():
    assert read_header(schema.GENERALS_CSV) == list(schema.GENERAL_FIELD_NAMES)


def test_column_names_are_unique():
    for columns in (schema.BATTLE_COLUMNS, schema.GENERAL_COLUMNS):
        names = [spec.name for spec in columns]
        assert len(names) == len(set(names))


def test_enum_columns_list_their_choices():
    for columns in (schema.BATTLE_COLUMNS, schema.GENERAL_COLUMNS):
        for spec in columns:
            if spec.kind == "enum":
                assert spec.choices, f"{spec.name} is an enum with no choices"


def test_column_lookup():
    assert schema.column(schema.BATTLE_COLUMNS, "outcome").choices == schema.OUTCOMES
    with pytest.raises(KeyError):
        schema.column(schema.BATTLE_COLUMNS, "not_a_column")


@pytest.mark.parametrize(
    "date_text, expected_year",
    [
        ("1815-06-18", 1815),
        ("1757-12", 1757),
        ("1941", 1941),
        ("-0052", -52),
        ("-0331-10-01", -331),
    ],
)
def test_parse_year(date_text, expected_year):
    assert schema.parse_year(date_text) == expected_year


@pytest.mark.parametrize("bad_date", ["", "   ", "eighteen-fifteen", "-"])
def test_parse_year_rejects_junk(bad_date):
    with pytest.raises(ValueError):
        schema.parse_year(bad_date)


def test_bool_round_trip():
    for value in (True, False):
        assert schema.parse_bool(schema.format_bool(value)) is value


def test_parse_bool_rejects_other_spellings():
    with pytest.raises(ValueError):
        schema.parse_bool("yes")
