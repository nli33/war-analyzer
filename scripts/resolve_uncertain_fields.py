#!/usr/bin/env python3
"""C5: run the single bounded `claude -p` pass over the uncertain-row queue and write
data/auto/c5_resolved_fields.json for C6 to merge into the final strength/casualty extraction.

    python scripts/resolve_uncertain_fields.py [--dry-run] [--batch-size N] [--refresh]

See war/uncertain_fields.py for what goes in the queue and why. In short: every strength/
casualties infobox field, on a battle touching a roster general (data/auto/generals.csv), that
has real text but that war.infobox_numbers.extract_numeric_field could not turn into a number.
Items whose text has no digit at all are resolved to None without a model call (nothing for even
an LLM to recover); the rest are batched (never one call per battle) to the lowest model/effort
(haiku, low effort), with --tools "" (no tool use needed, pure text-in/JSON-out) and a JSON schema
for structured output.

Hard caps (war.uncertain_fields.MAX_ROWS / MAX_CALLS, matching PROGRESS.md's C5 run limits): the
queue is truncated to MAX_ROWS items, and the script refuses to run if the batch size would need
more than MAX_CALLS calls to cover everything sent to the model.

Resumable: resolved ids are cached at data/raw/c5_llm_cache.json (gitignored, like every other
raw/* cache in this project) so a rerun after a crash only calls for ids not yet resolved and a
plain rerun with no changes makes zero new calls. --refresh ignores that cache and starts clean.

Outputs:
  data/raw/c5_uncertain_queue.json   full queue dump (every item, for transparency/debugging)
  data/raw/c5_llm_cache.json         resumable id -> raw model value cache
  data/auto/c5_resolved_fields.json  {battle_title: {field: int}}, sanity-checked, for C6 (tracked)
  data/raw/c5_report.json            row/call counts and rough cost, printed to stdout too
"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.infobox_numbers import extract_strength_and_casualties  # noqa: E402
from war.uncertain_fields import (  # noqa: E402
    DEFAULT_BATCH_SIZE,
    MAX_CALLS,
    MAX_ROWS,
    RESPONSE_SCHEMA,
    build_prompt,
    build_queue,
    sanity_clean,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
BATTLE_UNIVERSE_PATH = REPO_ROOT / "data" / "raw" / "battle_universe.csv"
WIKITEXT_CACHE_PATH = REPO_ROOT / "data" / "raw" / "battle_wikitext_cache.json"
GENERALS_PATH = REPO_ROOT / "data" / "auto" / "generals.csv"
QUEUE_DUMP_PATH = REPO_ROOT / "data" / "raw" / "c5_uncertain_queue.json"
LLM_CACHE_PATH = REPO_ROOT / "data" / "raw" / "c5_llm_cache.json"
RESOLVED_OUTPUT_PATH = REPO_ROOT / "data" / "auto" / "c5_resolved_fields.json"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "c5_report.json"

MODEL = "haiku"
EFFORT = "low"
MAX_BUDGET_USD_PER_CALL = "0.25"
CALL_TIMEOUT_SECONDS = 180


def _read_column(path: Path, column: str) -> list[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row[column] for row in csv.DictReader(handle)]


def call_batch(batch) -> dict:
    """One `claude -p` call for one batch. Returns the parsed JSON response (or {} if the
    process produced no stdout, e.g. it errored before emitting anything)."""
    prompt = build_prompt(batch)
    cmd = [
        "claude",
        "-p",
        prompt,
        "--model",
        MODEL,
        "--effort",
        EFFORT,
        "--tools",
        "",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(RESPONSE_SCHEMA),
        "--no-session-persistence",
        "--strict-mcp-config",
        "--permission-prompts",
        "none",
        "--max-budget-usd",
        MAX_BUDGET_USD_PER_CALL,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=CALL_TIMEOUT_SECONDS)
    return json.loads(proc.stdout) if proc.stdout.strip() else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="build and report the queue, make no model calls")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS)
    parser.add_argument("--refresh", action="store_true", help="ignore the resumable LLM-answer cache")
    args = parser.parse_args()

    titles = _read_column(BATTLE_UNIVERSE_PATH, "battle_title")
    roster_ids = set(_read_column(GENERALS_PATH, "general_id"))
    cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))

    queue = build_queue(titles, cache, roster_ids, max_rows=args.max_rows)
    QUEUE_DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_DUMP_PATH.write_text(
        json.dumps(
            [{"id": i.id, "battle": i.battle_title, "field": i.field, "text": i.raw_text} for i in queue],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sendable = [item for item in queue if item.has_digit]
    num_batches = -(-len(sendable) // args.batch_size) if sendable else 0
    print(f"{len(queue)} uncertain fields queued ({len(queue) - len(sendable)} have no digit, resolved to None for free)")
    print(f"{len(sendable)} fields have a digit worth sending to the model, in {num_batches} batch(es) of up to {args.batch_size}")

    if num_batches > MAX_CALLS:
        raise SystemExit(
            f"{num_batches} calls needed exceeds MAX_CALLS={MAX_CALLS}; raise --batch-size or lower --max-rows"
        )

    if args.dry_run:
        print("--dry-run: stopping before any model calls")
        return 0

    llm_cache: dict[str, int | None] = {}
    if LLM_CACHE_PATH.exists() and not args.refresh:
        llm_cache = json.loads(LLM_CACHE_PATH.read_text(encoding="utf-8"))
    pending = [item for item in sendable if str(item.id) not in llm_cache]
    print(f"{len(sendable) - len(pending)} already resolved in the cache, {len(pending)} left to call for")

    total_cost = 0.0
    calls_made = 0
    for start in range(0, len(pending), args.batch_size):
        batch = pending[start : start + args.batch_size]
        payload = call_batch(batch)
        calls_made += 1
        total_cost += payload.get("total_cost_usd") or 0.0
        structured = payload.get("structured_output") or {}
        for row in structured.get("results") or []:
            try:
                llm_cache[str(int(row["id"]))] = row["value"]
            except (KeyError, TypeError, ValueError):
                continue
        LLM_CACHE_PATH.write_text(json.dumps(llm_cache), encoding="utf-8")
        print(f"  batch {calls_made}/{num_batches}: {len(batch)} items, cost so far ${total_cost:.4f}")

    # Strength lookup for the casualties sanity cross-check: regex-parsed strengths first, then
    # fill in gaps with this pass's own resolved strengths.
    strength_lookup: dict[tuple[str, str], int] = {}
    for title in {item.battle_title for item in queue}:
        wikitext = cache.get(title) or ""
        for field, extracted in extract_strength_and_casualties(wikitext).items():
            if field.startswith("strength") and extracted.point is not None:
                strength_lookup[(title, field)] = extracted.point
    for item in queue:
        if item.field.startswith("strength"):
            value = llm_cache.get(str(item.id))
            if value is not None:
                strength_lookup.setdefault((item.battle_title, item.field), value)

    resolved: dict[str, dict[str, int]] = {}
    resolved_count = 0
    rejected_count = 0
    for item in queue:
        raw_value = llm_cache.get(str(item.id))
        clean = sanity_clean(item, raw_value, strength_lookup)
        if raw_value is not None and clean is None:
            rejected_count += 1
        if clean is not None:
            resolved.setdefault(item.battle_title, {})[item.field] = clean
            resolved_count += 1

    RESOLVED_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESOLVED_OUTPUT_PATH.write_text(json.dumps(resolved, indent=2, sort_keys=True), encoding="utf-8")

    report = {
        "queue_rows": len(queue),
        "rows_sent_to_model": len(sendable),
        "calls_made": calls_made,
        "resolved_count": resolved_count,
        "rejected_by_sanity_count": rejected_count,
        "total_cost_usd": round(total_cost, 4),
        "model": MODEL,
        "effort": EFFORT,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"wrote {RESOLVED_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
