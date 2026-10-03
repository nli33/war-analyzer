#!/usr/bin/env python3
"""F3: run the single bounded `claude -p` pass over the unresolved-outcome queue and write
data/auto/f3_resolved_outcomes.json for G2 to merge into the final outcome extraction (the same
split C5/C6 used for strength/casualty fields -- see war/uncertain_outcomes.py's module
docstring).

    python scripts/resolve_uncertain_outcomes.py [--dry-run] [--batch-size N] [--refresh]

In short: every battle page that clears every earlier `war.battles_dataset.build_battle_rows`
gate (infobox, year, a wikilinked primary commander) but whose `result` text
`war.rules.outcome_from_result` could not match to a side, and that has real text on at least one
`combatant` field for the model to match against. Pages with no side-identifying text at all are
resolved to "unresolvable" without a call (see war/uncertain_outcomes.py). Batched (never one
call per battle), lowest model/effort (haiku, low effort), with --tools "" (no tool use needed,
pure text-in/JSON-out) and a JSON schema for structured output.

Hard caps (war.uncertain_outcomes.MAX_ROWS / MAX_CALLS, matching PROGRESS.md's F3 run limits):
the queue is truncated to MAX_ROWS items, and the script refuses to run if the batch size would
need more than MAX_CALLS calls to cover everything sent to the model.

Resumable: resolved ids are cached at data/raw/f3_llm_cache.json (gitignored, like every other
raw/* cache in this project) so a rerun after a crash only calls for ids not yet resolved and a
plain rerun with no changes makes zero new calls. --refresh ignores that cache and starts clean.

Outputs:
  data/raw/f3_uncertain_outcome_queue.json  full queue dump (every item, for transparency/debugging)
  data/raw/f3_llm_cache.json                resumable id -> raw model value cache
  data/auto/f3_resolved_outcomes.json       {battle_title: "side1"|"side2"|"draw"}, sanity-checked,
                                             for G2 (tracked)
  data/raw/f3_report.json                   row/call counts and rough cost, printed to stdout too
"""

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from war.uncertain_outcomes import (  # noqa: E402
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
QUEUE_DUMP_PATH = REPO_ROOT / "data" / "raw" / "f3_uncertain_outcome_queue.json"
LLM_CACHE_PATH = REPO_ROOT / "data" / "raw" / "f3_llm_cache.json"
RESOLVED_OUTPUT_PATH = REPO_ROOT / "data" / "auto" / "f3_resolved_outcomes.json"
REPORT_PATH = REPO_ROOT / "data" / "raw" / "f3_report.json"

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
    cache = json.loads(WIKITEXT_CACHE_PATH.read_text(encoding="utf-8"))

    queue = build_queue(titles, cache, max_rows=args.max_rows)
    QUEUE_DUMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_DUMP_PATH.write_text(
        json.dumps(
            [
                {
                    "id": i.id,
                    "battle": i.battle_title,
                    "result": i.result_text,
                    "combatant1": i.combatant1_text,
                    "combatant2": i.combatant2_text,
                }
                for i in queue
            ],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    sendable = [item for item in queue if item.has_side_text]
    num_batches = -(-len(sendable) // args.batch_size) if sendable else 0
    print(f"{len(queue)} unresolved outcomes queued ({len(queue) - len(sendable)} have no side-identifying text, resolved to unresolvable for free)")
    print(f"{len(sendable)} outcomes have side text worth sending to the model, in {num_batches} batch(es) of up to {args.batch_size}")

    if num_batches > MAX_CALLS:
        raise SystemExit(
            f"{num_batches} calls needed exceeds MAX_CALLS={MAX_CALLS}; raise --batch-size or lower --max-rows"
        )

    if args.dry_run:
        print("--dry-run: stopping before any model calls")
        return 0

    llm_cache: dict[str, str | None] = {}
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
                llm_cache[str(int(row["id"]))] = row["winner"]
            except (KeyError, TypeError, ValueError):
                continue
        LLM_CACHE_PATH.write_text(json.dumps(llm_cache), encoding="utf-8")
        print(f"  batch {calls_made}/{num_batches}: {len(batch)} items, cost so far ${total_cost:.4f}")

    resolved: dict[str, str] = {}
    resolved_count = 0
    rejected_count = 0
    for item in queue:
        raw_value = llm_cache.get(str(item.id))
        clean = sanity_clean(raw_value)
        if raw_value is not None and clean is None:
            rejected_count += 1
        if clean is not None:
            resolved[item.battle_title] = clean
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
