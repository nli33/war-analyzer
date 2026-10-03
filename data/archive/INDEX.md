# Archive index

One line per archived dataset snapshot: path, date, one-sentence purpose. See each directory's
own README.md for the full source/method/scores/replacement-reason.

- `2026-10-01-pre-c7-parser-fixes/` (2026-10-01) — `data/auto/{generals,battles}.csv` from C6's
  run, before C7 found and fixed three real C2/C3 parser bugs (comma-in-wikilink segment split,
  missing `ubli`/`Indented plainlist` template names, no redirect-following); superseded by a
  rerun of C4b/C6 against the fixed parser.
- `2026-10-03-pre-e4-f3-regen/` (2026-10-03) — `data/auto/{generals,battles}.csv` from C6's
  2026-10-01 run, before Phase E (identity resolution, seedless/must-include roster) and Phase F
  (redirect-stub refresh, demonym/outcome parser fixes, F3's bounded LLM outcome pass) were
  folded into a regenerated `data/auto/` by G2; superseded by that regeneration.
