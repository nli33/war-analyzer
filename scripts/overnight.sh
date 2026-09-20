#!/usr/bin/env bash
# Outer loop for the overnight autonomous run. See OVERNIGHT.md for the design.
# Run this inside a sandboxed container/VM, not on the primary machine.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

MAX_ITERATIONS="${MAX_ITERATIONS:-40}"
STALL_LIMIT="${STALL_LIMIT:-3}"
stall_count=0
prev_commit="$(git rev-parse HEAD)"

PROMPT='You are running unattended overnight - no human will see or answer anything you write.
Never stop to ask a question or wait for input. If something is ambiguous, make the most
reasonable judgment call, note it as a decision/assumption in PROGRESS.md, and keep going.
Only halt per the "stop and flag" conditions in SCOPE.md, where you genuinely cannot proceed.

Read PROGRESS.md and CLAUDE.md. Pick up the next unchecked task. Do the work for
that ONE task only - do not jump ahead. Follow SCOPE.md'"'"'s verification method for that phase
before marking it done. Update PROGRESS.md (check the task, add a one-line note on what
happened or any deviation) and commit your work with a message per CLAUDE.md'"'"'s commit rules.
If a phase'"'"'s exit criteria can'"'"'t be verified, stop and write why in PROGRESS.md instead of
guessing. If everything in PROGRESS.md is checked off, write DONE as the last line of
PROGRESS.md and stop.

For battle-curation tasks specifically: for each battle, first run
`python scripts/scrape_wikipedia_infobox.py "<battle name>"` to get a draft strength/casualties
scaffold - it is unverified and only saves you a first-pass lookup. Cross-check every number
against an academic source (Clodfelter, Osprey, or another named source) before writing the
battles.csv row, and set source_citation to the academic source you actually checked it against,
not "Wikipedia". If the scraper finds no infobox, research the battle by hand as before.'

for i in $(seq 1 "$MAX_ITERATIONS"); do
  echo "=== iteration $i ==="

  claude -p "$PROMPT" \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --verbose

  new_commit="$(git rev-parse HEAD)"
  if [ "$new_commit" = "$prev_commit" ]; then
    stall_count=$((stall_count + 1))
    echo "no new commit (stall_count=$stall_count)"
  else
    stall_count=0
  fi
  prev_commit="$new_commit"

  if grep -qx "DONE" PROGRESS.md; then
    echo "PROGRESS.md marked DONE, stopping."
    break
  fi
  if [ "$stall_count" -ge "$STALL_LIMIT" ]; then
    echo "No commits in $STALL_LIMIT iterations, stopping (stuck)."
    break
  fi
done
