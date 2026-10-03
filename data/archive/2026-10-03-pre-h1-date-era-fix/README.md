# 2026-10-03 — pre-H1 date-parsing/era-assignment fix snapshot

What this is: `data/auto/generals.csv` (341 lines incl. header, 340 generals) and
`data/auto/battles.csv` (1,885 lines incl. header, 1,884 battle rows) exactly as G2's regen last
wrote them (`roster_selection_report.json`/`c6_report.json` in this directory, from that run),
before PROGRESS.md's H1 task fixed three real bugs in the pipeline this snapshot was built with.

Source and method: same as the G2/G4 snapshots this one supersedes nothing else about — E1-E4's
identity resolution and seedless/must-include roster, F1-F3's redirect/demonym/outcome fixes,
`--min-battles 4`. The only thing different between this snapshot and the one that replaces it is
the two H1 code fixes below; no re-crawl, no roster/outcome logic change.

Why replaced — three bugs, found by hand-checking absurd outputs the ranking diagnosis phase
flagged (Eisenhower #1, Napoleon #49, 13 generals with >80-year careers):

1. **`war/scrape.py`'s `_strip_wikitext_markup` deleted `{{template}}` markup outright instead of
   replacing it with a space.** A date range written `"11{{ndash}}12 April 1796"` (no surrounding
   whitespace around the template) became `"1112 April 1796"` once the template vanished, and
   `war.roster.extract_year`'s leftmost-match year regex then read `1112` as the year instead of
   `1796`. Same mechanism hit `"21{{ndash}}22 April 1809{{sfn|...}}"` (Eckmühl, parsed as `2122`)
   and `"9{{ndash}}11 March 1811"` (Pombal, parsed as `911`). Fixed by replacing templates with a
   space instead of an empty string (the existing whitespace-collapse step at the end of the same
   function cleans up the resulting double spaces); `extract_year` itself was correct and
   untouched.
2. **The same function never decoded HTML entities at all**, and turned out to be the bigger
   contributor of the two: a BC-era date written `"335&nbsp;BC"` has no real whitespace between
   the year and the BC marker once scraped (`&nbsp;` is six literal characters, not a space), so
   `extract_year`'s BC regex (which requires `\s*` there) never matched, and the plain-year
   fallback read `335` as a positive year instead of `-335`. This alone explains Alexander
   (`-335` to `335`), Hannibal (`-219` to `217`), Scipio Africanus (`-208` to `209`), and Pyrrhus
   of Epirus (`-280` to `278`) all showing 400+ year "careers" in this snapshot. Some infobox
   fields double-encode the entity (`"209&amp;nbsp;BC"`, Cartagena — a literal `&amp;` followed by
   `nbsp;`), which needs two `html.unescape` passes to reach a real space, not one. Fixed by
   `war.scrape._unescape_html_entities`, which unescapes to a fixed point so both the single- and
   double-encoded cases resolve.
3. **`war/rules.py`'s `_ERA_BREAKPOINTS` had no upper bound on "WWII"** — every year >= 1914 fell
   into that bucket, including 2001-2017 Libya/Iraq/Syria/Macedonia battles (64 rows in this
   snapshot). Added a `"Modern"` era starting 1945 (`war/schema.py`'s `ERAS` tuple, `RESOURCE_
   ERA_DEFAULT`) and a breakpoint at that year.

Measured effect of all three fixes together (H1's sanity check, `war.roster.suspicious_year_rows`,
flags a row whose year is >80 years from its own title's year or from the same general's other
battles): **12 flagged rows in this snapshot, 3 in the regenerated one** (the remaining 3 are a
different bug — generic rank words like "Captain"/"Colonel" collapsing multiple real people into
one `general_id`, not a date-parsing issue; flagged in PROGRESS.md's Notes as a candidate for a
future identity-resolution task, not fixed here). Napoleon's career span: this snapshot has his
`data/auto/generals.csv` row reading `1018-2122` (an 1,105-year "career"); the regenerated one
reads `1794-1815`. Of the 13 generals with >80-year career spans in this snapshot, 9 resolve to a
normal span once the date bug is fixed; the remaining 4 are the generic-rank-word identity
collisions above, not real individual generals at all.

Quality gate: `scripts/eval_ingest.py` against the 177-row gold set gives identical numbers before
and after these fixes (own/enemy troop strength coverage 67%/65%, casualties 58%/61%, matching
`data/raw/eval_ingest_report_c7.json` exactly) — none of the three fixes touches the C2/C3
strength/commander extraction path in a way that changes gold-set scoring.
`scripts/validate_data.py` passes on both.
