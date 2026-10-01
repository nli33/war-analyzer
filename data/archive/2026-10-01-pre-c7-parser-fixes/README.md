# 2026-10-01 — pre-C7-parser-fixes snapshot

What this is: `data/auto/generals.csv` (297 rows incl. header) and `data/auto/battles.csv` (718
rows incl. header) exactly as written by C6's full run (commit `e1075d7`), before the parser
fixes made while building and running C7's gold-set quality gate (`scripts/eval_ingest.py`).

Source and method: same as C6 — `war.commanders`/`war.infobox_numbers` (C2/C3) over the C1
battle universe (8,824 candidate titles, 8,430 found in `data/raw/battle_wikitext_cache.json`),
roster selected by `war.roster.select_roster` at `--min-battles 2` (C4b), C5's bounded LLM pass
folded in as a fallback.

Why replaced: running `scripts/eval_ingest.py` against the gold set for C7 surfaced three real
bugs in the C2/C3 parsers that this snapshot's run still has:

1. `war/commanders.py`'s commander-field segment splitter (`\n`/`;`/`,`) was not bracket-aware,
   so a wikilinked name whose *target* title contains a comma (e.g.
   `[[Arthur Wellesley, 1st Duke of Wellington|Arthur Wellesley]]`) was split in two, losing the
   wikilink and the `general_id` it would have produced. Fixed by routing the split through
   `war.wikitext.split_top_level` (generalized to accept multiple separator characters).
2. Both `war/commanders.py` and `war/infobox_numbers.py`'s list-template unwrapping recognized
   `{{ubl}}`/`{{plainlist}}` but not the real variants `{{ubli}}`/`{{Indented plainlist}}` (seen
   on Battle of Lodi, Battle of Marengo), silently dropping the whole field.
3. `war/scrape.py`'s `fetch_wikitext_batch` didn't pass `redirects=1`, so a candidate title that
   is itself a `#REDIRECT` page (e.g. "Siege of Alesia" -> "Battle of Alesia") came back with the
   redirect stub's own one-line wikitext instead of the target's infobox.

Measured impact on the gold-set eval (own/enemy troop strength coverage): 39%/38% before any of
these three fixes, 67%/65% after. Full before/after numbers and the eval methodology are in
`~/notes/war-analyzer/ingestion.md`'s C7 entry.

Floor used (A6, unchanged): strength within 3x of gold on >=75% of rows where both sides exist,
strength present both sides on >=60% of battles, casualties kept only if >=40% coverage. This
snapshot was never itself scored against the gold set with the real extractor (C7 didn't exist
yet when C6 ran) — A3's naive-baseline numbers are the closest prior measurement, and they are
not comparable (different method, oracle-picked orientation).

Row/general counts: 296 generals, 717 battle rows, 250 generals with >=1 row (see
`data/raw/c6_report.json`/`data/raw/roster_selection_report.json` as they stood at the time,
reproduced in this directory's two CSVs).

Not re-crawled for the redirect fix: `data/raw/battle_wikitext_cache.json` (122MB) still holds
pre-fix content for any candidate title that is itself a redirect — refreshing it would mean
re-fetching all 8,824 titles over the network, out of scope for C7's gold-set gate check. Left as
a known gap for a future full re-crawl; the regenerated `data/auto/` this snapshot was replaced
by only benefits from fixes 1 and 2 above (pure re-parsing of already-cached text), not fix 3.
