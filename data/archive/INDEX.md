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
- `2026-10-03-pre-h1-date-era-fix/` (2026-10-03) — `data/auto/{generals,battles}.csv` from G2's
  regen, before H1 fixed a wikitext-template-stripping bug and a missing HTML-entity decode (both
  in `war/scrape.py`, together the cause of Napoleon's 1,105-year "career" and 8 other absurd
  spans) and an unbounded "WWII" era bucket (`war/rules.py`, added a "Modern" era); superseded by
  a rerun of `scripts/build_roster_selection.py`/`build_auto_battles.py` against the fixed code.
- `2026-10-03-pre-h4-combatant-date-template-fix/` (2026-10-03) — `data/auto/{generals,battles}.csv`
  from H1's regen, before H4 fixed three (four, counting a Wikipedia redirect alias) template-
  expansion bugs in `war/scrape.py` (flag templates, date-range templates, and list templates were
  deleted outright instead of having their argument text kept, the literal reason Waterloo had zero
  rows and most of Rommel's battles were missing); superseded by a rerun of
  `scripts/build_roster_selection.py`/`build_auto_battles.py` against the fixed code.
