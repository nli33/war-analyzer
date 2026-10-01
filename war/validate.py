"""Row-level validation for `data/battles.csv` and `data/generals.csv`.

Checks every row against the `Column` specs in `war/schema.py`: required fields
are present, enums (including `outcome`) hold a listed value, numeric fields
respect their `min_value`/`max_value` (this is where "non-negative" is
enforced, since every numeric column's `min_value` is 0), dates parse, and
booleans are `true`/`false`. Also checks invariants the schema docstrings
claim but a single `Column` spec can't express on its own: `battle_id` and
`general_id` are unique within their file, every battle's `general_id`
resolves to a row in `generals.csv`, and for each of the four strength/
casualty fields, if its `_low`/`_high` range is recorded then `low <= high`
and the point estimate (when also recorded) falls within that range.
"""

import csv
import re
from pathlib import Path

from war import schema

REPO_ROOT = Path(__file__).resolve().parent.parent

# YYYY, YYYY-MM, or YYYY-MM-DD, negative year allowed (see schema.py module docstring).
_DATE_RE = re.compile(r"^-?\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$")


class ValidationError(Exception):
    """One row/column failed a schema check; str(e) is the human-readable reason."""


def validate_value(spec: schema.Column, raw_value: str) -> None:
    """Raise ValidationError if `raw_value` doesn't satisfy `spec`.

    An empty value is fine iff the column is optional; that's the only case
    where an empty string is not an error.
    """
    value = raw_value.strip()

    if not value:
        if spec.required:
            raise ValidationError(f"{spec.name} is required but empty")
        return

    if spec.kind == "int":
        try:
            number = int(value)
        except ValueError:
            raise ValidationError(f"{spec.name}={value!r} is not an integer") from None
        if spec.min_value is not None and number < spec.min_value:
            raise ValidationError(f"{spec.name}={number} is below minimum {spec.min_value}")
        if spec.max_value is not None and number > spec.max_value:
            raise ValidationError(f"{spec.name}={number} is above maximum {spec.max_value}")
    elif spec.kind == "bool":
        try:
            schema.parse_bool(value)
        except ValueError:
            raise ValidationError(f"{spec.name}={value!r} is not 'true'/'false'") from None
    elif spec.kind == "enum":
        if value not in spec.choices:
            raise ValidationError(f"{spec.name}={value!r} not in {spec.choices}")
    elif spec.kind == "date":
        if not _DATE_RE.match(value):
            raise ValidationError(f"{spec.name}={value!r} is not YYYY[-MM[-DD]]")
        schema.parse_year(value)
    # "text" columns need nothing beyond the required/empty check above.


def _read_rows(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# Base strength/casualty fields that carry an optional "<field>_low"/"<field>_high"
# sibling pair for when two sources disagree (see war/schema.py's module docstring).
_RANGE_FIELDS = (
    "own_troop_strength",
    "enemy_troop_strength",
    "own_casualties",
    "enemy_casualties",
)


def validate_ranges(path: Path) -> list[str]:
    """Check that each row's recorded `<field>_low`/`_high` pairs make sense.

    Only runs on rows where both bounds are present (either may be empty).
    """
    errors = []
    for line_number, row in enumerate(_read_rows(path), start=2):  # header is line 1
        row_id = row.get("battle_id", "").strip()
        for field in _RANGE_FIELDS:
            low_text = row.get(f"{field}_low", "").strip()
            high_text = row.get(f"{field}_high", "").strip()
            if not low_text or not high_text:
                continue
            try:
                low, high = int(low_text), int(high_text)
            except ValueError:
                continue  # validate_value already reports the malformed int
            if low > high:
                errors.append(
                    f"{path.name}:{line_number} ({row_id or '?'}): "
                    f"{field}_low={low} is above {field}_high={high}"
                )
                continue
            point_text = row.get(field, "").strip()
            try:
                point = int(point_text) if point_text else None
            except ValueError:
                continue  # validate_value already reports the malformed int
            if point is not None and not (low <= point <= high):
                errors.append(
                    f"{path.name}:{line_number} ({row_id or '?'}): "
                    f"{field}={point_text} falls outside its own range [{low}, {high}]"
                )
    return errors


def validate_file(path: Path, columns: tuple[schema.Column, ...]) -> list[str]:
    """Return human-readable errors for one CSV; empty list means the file is clean.

    Also enforces that the file's id column (its first column, e.g. `battle_id`
    or `general_id`) is unique across rows.
    """
    errors = []
    seen_ids: set[str] = set()
    id_column = columns[0].name

    for line_number, row in enumerate(_read_rows(path), start=2):  # header is line 1
        row_id = row.get(id_column, "").strip()
        for spec in columns:
            try:
                validate_value(spec, row.get(spec.name, ""))
            except ValidationError as exc:
                errors.append(f"{path.name}:{line_number} ({row_id or '?'}): {exc}")

        if row_id:
            if row_id in seen_ids:
                errors.append(f"{path.name}:{line_number}: duplicate {id_column} {row_id!r}")
            seen_ids.add(row_id)

    return errors


def validate_all(repo_root: Path = REPO_ROOT) -> list[str]:
    """Validate both CSVs, plus that every battle's `general_id` has a roster row."""
    battles_path = repo_root / schema.BATTLES_CSV
    generals_path = repo_root / schema.GENERALS_CSV

    errors = validate_file(battles_path, schema.BATTLE_COLUMNS)
    errors += validate_file(generals_path, schema.GENERAL_COLUMNS)
    errors += validate_ranges(battles_path)

    known_generals = {row["general_id"].strip() for row in _read_rows(generals_path)}
    for line_number, row in enumerate(_read_rows(battles_path), start=2):
        general_id = row.get("general_id", "").strip()
        if general_id and general_id not in known_generals:
            errors.append(
                f"battles.csv:{line_number}: general_id {general_id!r} has no row in generals.csv"
            )

    return errors
