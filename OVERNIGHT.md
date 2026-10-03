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
compaction. Instead, run a **"Ralph loop"**: an outer script repeatedly starts a brand-new,
stateless `claude -p` invocation. Each invocation reads state from disk (PROGRESS.md, git log,
the repo itself), does one unit of work, writes state back to disk, commits, and exits. No
conversation history carries between iterations — the filesystem is the memory, not the context
window. This sidesteps context-rot entirely instead of fighting it.

```bash
python3 scripts/overnight.py --min-remaining-pct 10 --wait-for-reset
# ./scripts/overnight.sh passes its arguments through to the same script
```

`scripts/overnight.py` starts a fresh `claude -p` with the prompt in `scripts/overnight_prompt.txt`,
streams a short line per tool call to the terminal, and writes the full event stream for each
iteration to `logs/overnight/` (gitignored). Options:

- `--max-iterations` (default 40, or `MAX_ITERATIONS`) and `--stall-limit` (default 3, or
  `STALL_LIMIT`): hard caps on iterations and on consecutive iterations that leave the repo exactly
  as it was. An iteration counts as progress if it moved HEAD or changed any file, committed or not.
- `BLOCKED:` line: the prompt tells the agent to end `PROGRESS.md` with a line starting `BLOCKED:`
  and the reason when stopping is the right outcome. The loop halts on it, and refuses to start
  while one is present, so delete a stale line before restarting.
- `--model` and `--effort`: passed to `claude`. Unset means whatever the machine defaults to.
- `--min-remaining-pct N`: each run reports how much of the five-hour and weekly usage windows is
  used and when they reset. After a task finishes, if either window has less than N% left, the
  loop stops instead of starting a task it may not be able to finish.
- `--wait-for-reset`: instead of stopping, sleep until the window resets and carry on. It only
  waits when the reset is within `--max-wait-hours` (default 6), so a nearly used-up weekly window
  still stops the run. `--reset-margin-sec` (default 120) is added to the reset time.
- If the limit is hit in the middle of a task, that iteration does not count as a stall. The loop
  waits for the reset (with `--wait-for-reset`) or stops, then retries, and the prompt tells the
  next iteration to finish the interrupted task first. Three limit hits in a row stop the run.

Exit codes: 0 = PROGRESS.md says DONE, 1 = stuck, 2 = iteration cap, 3 = stopped for usage,
4 = BLOCKED line.
Look at `git status` before restarting after a usage stop in case a task was cut off.

The usage-limit failure path (what `claude -p` prints when it is actually cut off) has not been
seen on a real run; the loop treats a non-allowed `rate_limit_event` status, or an error result
that mentions a usage or rate limit, as a limit hit.

Run it inside a sandboxed container/VM, not against your primary machine. It passes
`--dangerously-skip-permissions`, the same guidance Anthropic gives for "auto mode."

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
