"""F3: collect battle pages whose infobox `result` text `war.rules.outcome_from_result` could
not turn into a Win/Loss/Draw, and resolve as many as possible with one bounded `claude -p` pass.

Scope: a title only enters the queue if (a) it already clears every earlier gate
`war.battles_dataset.build_battle_rows` applies (has an infobox, a year, a wikilinked primary
commander on at least one side) so that resolving its outcome would actually produce a row, (b)
`outcome_from_result` returns `(None, None)` on it, and (c) the infobox sets real `result` text
*and* at least one of `combatant1`/`combatant2` has real text -- something for the model to match
the result text against. A title with no `result` text, or with `result` text but both combatant
fields empty, has nothing for even an LLM to compare against (there's no side-identifying text at
all), so those resolve to "unresolvable" without a call -- same free-resolution rule
`war.uncertain_fields` applies to a field with no digit in it.

This module is pure logic (queue building, prompt/schema, response parsing, sanity bounds); the
CLI driver that actually shells out to `claude -p` is `scripts/resolve_uncertain_outcomes.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from war.commanders import extract_commander_fields, primary_commander
from war.roster import extract_year
from war.rules import outcome_from_result
from war.scrape import parse_military_infobox

# Run limits (PROGRESS.md: "at most 3,000 rows and 60 calls in total").
MAX_ROWS = 3000
MAX_CALLS = 60
DEFAULT_BATCH_SIZE = 40

_ALLOWED_VALUES = frozenset({"side1", "side2", "draw"})


@dataclass(frozen=True)
class QueueItem:
    id: int
    battle_title: str
    result_text: str
    combatant1_text: str | None
    combatant2_text: str | None

    @property
    def has_side_text(self) -> bool:
        return bool(self.combatant1_text or self.combatant2_text)


def build_queue(
    titles: list[str],
    wikitext_cache: dict[str, str],
    max_rows: int = MAX_ROWS,
) -> list[QueueItem]:
    """Every battle page whose outcome `war.rules.outcome_from_result` left unresolved, among
    titles that already clear every earlier pipeline gate. Deterministic order (sorted by title)
    so a truncation at `max_rows` is reproducible, not a hash-order accident."""
    candidates: list[tuple[str, str, str | None, str | None]] = []
    for title in sorted(titles):
        wikitext = wikitext_cache.get(title)
        if not wikitext:
            continue
        infobox = parse_military_infobox(wikitext)
        if not infobox:
            continue
        year = extract_year(infobox.get("date"))
        if year is None:
            continue
        commander_fields = extract_commander_fields(wikitext)
        primary1 = primary_commander(commander_fields.get("commander1", []))
        primary2 = primary_commander(commander_fields.get("commander2", []))
        if primary1 is None and primary2 is None:
            continue
        result_text = infobox.get("result")
        if not result_text:
            continue
        combatant1_text, combatant2_text = infobox.get("combatant1"), infobox.get("combatant2")
        outcome1, _ = outcome_from_result(result_text, combatant1_text, combatant2_text)
        if outcome1 is not None:
            continue
        candidates.append((title, result_text, combatant1_text, combatant2_text))

    return [
        QueueItem(id=i, battle_title=title, result_text=result, combatant1_text=c1, combatant2_text=c2)
        for i, (title, result, c1, c2) in enumerate(candidates[:max_rows])
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
                    "winner": {"type": ["string", "null"], "enum": ["side1", "side2", "draw", None]},
                },
                "required": ["id", "winner"],
            },
        }
    },
    "required": ["results"],
}

_PROMPT_PREAMBLE = (
    "Each item is one Wikipedia military-conflict infobox whose `result` field a deterministic "
    "parser could not match to a side. For each item, read `result` together with `combatant1` "
    "and `combatant2` (the raw text naming who fought on each side; one may be missing) and "
    'decide: did side 1 win ("side1"), did side 2 win ("side2"), was it a draw/inconclusive '
    '("draw"), or can this not be told from the given text alone ("unresolvable")? Base your '
    "answer only on the text given for this item -- do not use outside knowledge about the "
    "battle. If the wording in `result` could plausibly name either side, or neither, answer "
    "unresolvable rather than guessing."
)


def build_prompt(batch: list[QueueItem]) -> str:
    import json

    items = [
        {
            "id": item.id,
            "result": item.result_text,
            "combatant1": item.combatant1_text,
            "combatant2": item.combatant2_text,
        }
        for item in batch
    ]
    return _PROMPT_PREAMBLE + "\n\n" + json.dumps(items, ensure_ascii=False)


def extract_results(payload: dict) -> dict[int, str | None]:
    """Pull `{id: winner}` out of a parsed `claude -p --output-format json` response. Returns {}
    for an error response or one with no structured output (e.g. budget/timeout cutoff) -- the
    caller treats missing ids as unresolved, not a crash."""
    structured = payload.get("structured_output") or {}
    results = structured.get("results") or []
    out: dict[int, str | None] = {}
    for row in results:
        try:
            out[int(row["id"])] = row["winner"]
        except (KeyError, TypeError, ValueError):
            continue
    return out


def sanity_clean(value: str | None) -> str | None:
    """Apply the output sanity bound to one resolved value: must be one of the three real
    answers, or null/"unresolvable"/anything else counts as unresolved. Guards against a
    malformed or hallucinated response value making it into the dataset."""
    if value not in _ALLOWED_VALUES:
        return None
    return value
