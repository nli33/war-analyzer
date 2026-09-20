# Overnight Autonomous Run — Mechanics

How the overnight run in SCOPE.md is actually executed, with a focus on context management
across many hours of unattended work.

**Environment note:** the sandbox/container this runs in is CLI-only — no browser, no display.
Any visualization work (Phase 6) can't be visually verified by Claude itself during the run; see
the note in SCOPE.md's Phase 6. Write chart code so it can be sanity-checked from data/output
files (non-empty, expected shape) rather than by looking at the rendered image, and leave the
actual visual review to the user afterward.

## Architecture: fresh process per iteration, not one long session

Don't try to keep a single Claude Code session alive all night and manage its context via
compaction. Instead, run a **"Ralph loop"**: an outer bash script repeatedly starts a brand-new,
stateless `claude -p` invocation. Each invocation reads state from disk (PROGRESS.md, git log,
the repo itself), does one unit of work, writes state back to disk, commits, and exits. No
conversation history carries between iterations — the filesystem is the memory, not the context
window. This sidesteps context-rot entirely instead of fighting it.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/n/code/war

MAX_ITERATIONS=40
STALL_LIMIT=3          # consecutive no-progress iterations before abort
stall_count=0
prev_commit=""

for i in $(seq 1 "$MAX_ITERATIONS"); do
  echo "=== iteration $i ==="

  claude -p "You are running unattended overnight — no human will see or answer anything you
  write. Never stop to ask a question or wait for input. If something is ambiguous, make the
  most reasonable judgment call, note it as a decision/assumption in PROGRESS.md, and keep
  going. Only halt per the 'stop and flag' conditions in SCOPE.md, where you genuinely cannot
  proceed.

  Read PROGRESS.md and CLAUDE.md. Pick up the next unchecked task. Do the work for
  that ONE task only — don't jump ahead. Follow SCOPE.md's verification method for that phase
  before marking it done. Update PROGRESS.md (check the task, add a one-line note on what
  happened/any deviation) and commit your work with a message per CLAUDE.md's commit rules.
  If a phase's exit criteria can't be verified, stop and write why in PROGRESS.md instead of
  guessing. If everything in PROGRESS.md is checked off, write DONE as the last line of
  PROGRESS.md and stop." \
    --dangerously-skip-permissions \
    --output-format stream-json \
    --verbose

  new_commit="$(git rev-parse HEAD)"
  if [ "$new_commit" = "$prev_commit" ]; then
    stall_count=$((stall_count + 1))
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
```

Run this in a locked-down sandbox (container/VM, network egress limited to what the run actually
needs — web research + git push) — never against your primary machine unattended with
`--dangerously-skip-permissions`. This is the same guidance Anthropic gives for "auto mode."

## PROGRESS.md — the living task file

This is the file that survives across iterations (and across compaction, if a single session
does get long within one iteration). Structure:

```markdown
# Progress

## Phase 1: Scaffold
- [x] repo structure + CSV schema — done, matches PLAN.md Section 2 exactly
- [x] pytest harness runs with 0 tests

## Phase 2: Data curation
- [x] Caesar: 10 battles entered, citations from Osprey + Clodfelter
- [ ] Alexander the Great
- [ ] Genghis Khan
...

## Notes / deviations
- Frederick the Great's Kunersdorf casualty figures conflict between sources by ~2x;
  tagged Low confidence, widened Monte Carlo range instead of picking one.
```

Rules for this file:
- One checkbox per concrete, independently-committable unit of work — not per phase.
- Each `claude -p` invocation touches ONE unchecked item, then stops (don't let a single
  invocation try to clear the whole file — that's how you get a giant uncommitted diff and
  lose the incremental-commit property from CLAUDE.md).
- Deviations/decisions go in the Notes section as they happen, not reconstructed after the fact
  — this doubles as raw material for the project-notes dev log.
- Never delete a checked-off line; it's the audit trail of what happened overnight.

## Guardrails

- **Iteration cap** (`MAX_ITERATIONS`) and **stall detection** (no new commit for N iterations
  → abort) in the loop script above — catches both runaway loops and quietly-stuck ones.
- **Exit condition is a file marker (`DONE` in PROGRESS.md) plus tests passing**, not the model's
  own claim of completion inside a response.
- **Verification before advancing**: each task's checkbox should only flip once the phase's
  verification step from SCOPE.md actually ran (pytest passing, validation script clean) — not
  just "the code looks right." This is enforced by the prompt, not the loop mechanics, so it's
  only as reliable as the model following it — spot-check PROGRESS.md notes in the morning
  against actual test output/commit diffs, don't just trust the checkmarks.
- **Small commits**: the fresh-process-per-task structure naturally forces this — one task per
  invocation means one commit per invocation, in line with CLAUDE.md's incremental-commit rule.

## What NOT to use for this

- `--continue`/`--resume` to keep one session going all night — this is exactly the
  context-accumulation problem file-based state is meant to avoid.
- `ScheduleWakeup`/the `/loop` skill — those self-pace a single session's own turns and are for
  "check back periodically," not for running many independent fresh work units overnight.
- `CronCreate`/scheduled routines could replace the bash `while` loop as the thing that kicks off
  each iteration (server-side, no local terminal needed) — worth using instead of the script above
  if this run needs to survive a laptop closing, but the per-iteration prompt and PROGRESS.md
  contract stay the same either way.
