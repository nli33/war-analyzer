"""C5: collect strength/casualty infobox fields that deterministic parsing (C2) could not turn
into a number, and resolve as many as possible with one bounded `claude -p` pass.

Scope: a field only enters the queue if (a) the battle has at least one appearance by a roster
general (war/roster.py's C4b selection — these are the rows that matter for data/auto/
battles.csv) and (b) the infobox sets the field (non-empty raw text) but
`war.infobox_numbers.extract_numeric_field` could not parse a number from it. A field the infobox
never sets at all isn't queued: there's no text for an LLM to read either, so that gap is a
genuine data hole, not an "uncertain" one C5 can do anything about.

Every queued item with a digit in its raw text is sent to the model exactly once, batched (never
one call per battle, per PROGRESS.md). Items with no digit at all (e.g. "Unknown", "Heavy", a
unit name with no count) are resolved to `None` without a call — there is no number anywhere in
the text for even an LLM to recover, so spending a call would only relearn what the regex already
proved. They still appear in the full queue dump for transparency.

This module is pure logic (queue building, prompt/schema, response parsing, sanity bounds); the
CLI driver that actually shells out to `claude -p` is `scripts/resolve_uncertain_fields.py`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from war.infobox_numbers import extract_numeric_field, raw_numeric_fields
from war.roster import battle_appearances

# Run limits (PROGRESS.md: "at most 3,000 rows and 60 CLI calls in total").
MAX_ROWS = 3000
MAX_CALLS = 60
DEFAULT_BATCH_SIZE = 40

# Absolute sanity ceiling: no single battle's per-side personnel figure in this dataset's eras
# (Ancient through WWII) plausibly exceeds this. Generous on purpose — a floor against a
# hallucinated/misread number, not a tight historical bound.
MAX_PLAUSIBLE_PERSONNEL = 3_000_000

# A resolved casualty figure is rejected if it exceeds this multiple of the corresponding
# strength figure for the same battle/side, when that strength is known (PROGRESS.md: "casualties
# not far above strength").
MAX_CASUALTY_TO_STRENGTH_RATIO = 3

_DIGIT_RE = re.compile(r"\d")


@dataclass(frozen=True)
class QueueItem:
    id: int
    battle_title: str
    field: str  # "strength1" | "strength2" | "casualties1" | "casualties2"
    raw_text: str

    @property
    def has_digit(self) -> bool:
        return bool(_DIGIT_RE.search(self.raw_text))

    @property
    def is_casualties(self) -> bool:
        return self.field.startswith("casualties")

    @property
    def side(self) -> str:
        """The infobox side suffix ("1" or "2"), for pairing a casualties field with its
        same-side strength field."""
        return self.field[-1]


def build_queue(
    titles: list[str],
    wikitext_cache: dict[str, str],
    roster_ids: set[str],
    max_rows: int = MAX_ROWS,
) -> list[QueueItem]:
    """Every (battle, field) whose raw infobox text regex couldn't parse, restricted to battles
    touching a roster general. Deterministic order (sorted by title, then field name) so a
    truncation at `max_rows` is reproducible, not a hash-order accident."""
    candidates: list[tuple[str, str, str]] = []
    for title in titles:
        wikitext = wikitext_cache.get(title)
        if not wikitext:
            continue
        appearances = battle_appearances(title, wikitext)
        if not any(a.general_id in roster_ids for a in appearances):
            continue
        for field, text in raw_numeric_fields(wikitext).items():
            if extract_numeric_field(text).point is None:
                candidates.append((title, field, text))

    candidates.sort(key=lambda row: (row[0], row[1]))
    return [
        QueueItem(id=i, battle_title=title, field=field, raw_text=text)
        for i, (title, field, text) in enumerate(candidates[:max_rows])
    ]


RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "value": {"type": ["integer", "null"]},
                },
                "required": ["id", "value"],
            },
        }
    },
    "required": ["results"],
}

_PROMPT_PREAMBLE = (
    "Each item is one field from a Wikipedia military-conflict infobox that a deterministic "
    "regex parser could not turn into a number. For each item, read its raw wikitext and give "
    "your single best-estimate integer for the field, or null if the text states no number at "
    'all (e.g. "Unknown", "Heavy", a unit/division name with no count) or only a non-personnel '
    "count (e.g. a count of guns/ships with no troop figure). For a 'strength' field this is "
    "total personnel on that side. For a 'casualties' field this is total "
    "killed+wounded+captured+missing on that side (sum categories if listed separately; take the "
    "stated total if one is given instead). Never invent a number the text does not support — if "
    "genuinely unknown, answer null. Ignore equipment counts (cannons, guns, ships, aircraft) "
    "entirely; they are not personnel."
)


def build_prompt(batch: list[QueueItem]) -> str:
    import json

    items = [
        {"id": item.id, "battle": item.battle_title, "field": item.field, "text": item.raw_text}
        for item in batch
    ]
    return _PROMPT_PREAMBLE + "\n\n" + json.dumps(items, ensure_ascii=False)


def extract_results(payload: dict) -> dict[int, int | None]:
    """Pull `{id: value}` out of a parsed `claude -p --output-format json` response. Returns {}
    for an error response or one with no structured output (e.g. budget/timeout cutoff) — the
    caller treats missing ids as unresolved, not a crash."""
    structured = payload.get("structured_output") or {}
    results = structured.get("results") or []
    out: dict[int, int | None] = {}
    for row in results:
        try:
            out[int(row["id"])] = row["value"]
        except (KeyError, TypeError, ValueError):
            continue
    return out


def sanity_clean(
    item: QueueItem,
    value: int | None,
    strength_lookup: dict[tuple[str, str], int],
) -> int | None:
    """Apply PROGRESS.md's output sanity bounds to one resolved value. `strength_lookup` maps
    `(battle_title, "strength1"/"strength2")` to a known point estimate (regex-parsed or
    LLM-resolved in this same pass), used to catch a casualties figure wildly out of line with
    that side's own strength."""
    if value is None:
        return None
    if value < 0 or value > MAX_PLAUSIBLE_PERSONNEL:
        return None
    if item.is_casualties:
        strength = strength_lookup.get((item.battle_title, f"strength{item.side}"))
        if strength and value > strength * MAX_CASUALTY_TO_STRENGTH_RATIO:
            return None
    return value
