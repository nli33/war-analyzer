# CLAUDE.md — project instructions for war

This project follows the global karpathy-style guidelines already loaded from
`~/.claude/CLAUDE.md` (think before coding, simplicity first, surgical changes,
goal-driven execution). The rules below are additions specific to this repo.

## Code style

- Prioritize readable code over clever code. Avoid syntax gymnastics (nested
  ternaries, one-liner comprehensions doing three things at once, cute
  metaprogramming) even if it's shorter — a longer, obvious version wins.
- Split or refactor any file that grows past ~500 lines. Don't let the metrics
  pipeline or data-loading code become one giant module.

## Commits

- Use `feat:` prefix (or `fix:`, `test:`, `data:` where clearly more accurate).
- One line, no body required. Don't sweat grammar/capitalization perfection.
- Don't reference internal milestone/phase names (M1, Phase 3, etc.) in the
  message — describe what changed, not where it sits in the plan.
- Keep commits small and incremental. No big-bang diffs — commit after each
  meaningful step (a metric implemented, a batch of battles added, a test
  passing), not once at the end of a phase.

## Development log

Document the actual development process using the `project-notes` skill —
not just what was built, but:
- deviations from PLAN.md / SCOPE.md and why
- decisions made where the plan was ambiguous
- tradeoffs taken (e.g., data coverage vs. time, a metric simplified)
- rough narrative of how the work actually went, including dead ends

Use the global project-notes skill as-is — don't copy it into this repo.

## Writing documentation

When writing any prose documentation (README, dev notes, ranking write-ups),
use the `ai-writing` skill to avoid characteristic AI writing patterns —
negative parallelism ("it's not just X, it's Y"), empty hedging, listicle
padding, etc. Skip the "make it sound human" parts of that skill (added typos,
inserted emotion) — just avoid the egregious patterns, keep the writing plain
and direct. Use the global skill as-is — don't copy it into this repo.

## Environment

The overnight autonomous run happens in a CLI-only sandbox — no browser, no display. Don't rely
on visually opening a rendered chart to verify it works; see SCOPE.md Phase 6 and OVERNIGHT.md
for how to verify visualization output without a display.

No human is watching this run in real time — this overrides the global "if uncertain, ask" rule
during the overnight loop. If something is ambiguous, don't stop and wait for an answer: make
the most reasonable judgment call, write it down as a decision/assumption in PROGRESS.md's Notes
section, and keep going. Only genuinely halt the loop (per SCOPE.md's "stop and flag" conditions)
when you can't proceed at all — not merely when you're unsure of the best choice.

## Adding new data fields or metrics

See SCOPE.md's "Deciding whether to add a new data field/feature" section —
weigh historical/historian-consensus grounding against added complexity before
extending the schema beyond what PLAN.md specifies.
