# H4: missing battles

Three questions from PROGRESS.md: why Waterloo has no rows for either side, why Rommel has only 2
rows, why Patton and Bradley are not in the roster at all — traced through the funnel (candidate
title, parsed commander, side match, strength, outcome) using `scripts/h4_missing_battles.py`
(report at `data/raw/h4_report.json`, read-only against the existing wikitext cache, no new
network calls).

## Root cause found and fixed: three template-expansion bugs

`war/scrape.py`'s `_strip_wikitext_markup` deleted every `{{template}}` outright. That is correct
for templates whose content duplicates information already in the surrounding plain text
(`{{sfn|...}}`, `{{ndash}}`), but wrong for three families whose argument text *is* the field's
only copy of the information:

- **Flag templates** (`{{flag|X}}`, `{{flagcountry|X}}`, `{{flagicon|X}}`, `{{flagdeco|X}}`) —
  how most WWII-era infoboxes write a combatant's country. Deleting the template deleted the
  country name. Battle of Arras (1940)'s `combatant2` was entirely empty before the fix because
  `{{flagcountry|Nazi Germany}}` was its whole value.
- **Date-range templates** (`{{Start date|...}}`, `{{Start date and age|...}}`, and the `End
  date` variants) write a date as positional arguments. Battle of Waterloo's `date` field is
  `{{Start date and age|1815|06|18|df=yes}}` with no plain-text fallback anywhere else in the
  field — deleting the template left an empty string, `war.roster.extract_year` had nothing to
  parse, and the row never got a year. This is the literal, sole reason Waterloo produced zero
  rows before the fix.
- **List templates** (`{{ubl|...}}`, `{{plainlist|...}}`, etc.), once their nested flag templates
  were already erased by the bug above, had no remaining nested braces by the time the generic
  delete regex reached them, so the whole list collapsed to nothing instead of each item
  surviving as its own clause.

Fixed by `_expand_known_templates`, which runs before the generic delete and replaces only these
three families with their meaningful argument text, recursing into nested templates. Tests:
`tests/test_scrape.py`'s `test_start_date_template_expands_to_a_parseable_date`,
`test_flag_templates_keep_the_country_name_not_just_the_icon`,
`test_flag_template_with_year_disambiguator_keeps_only_the_country_name`,
`test_ubl_list_of_flag_templates_keeps_every_country_name`.

A fourth bug in the same family: `{{ublist|...}}` — Wikipedia's redirect alias for `{{Unbulleted
list}}` — was missing from the list-template name set even though `"unbulleted list"` and `"ubl"`
were already in it, so any `result` field wrapped in `{{ublist|...}}` lost its text entirely.
Measured against the full cache: 132 of 8,433 candidate titles' `result` field uses this alias,
including Battle of the Bulge's `{{ublist|Allied victory}}` — the reason that battle had no
`result` text at all (`stage=no_outcome reason=no_result_field` in the funnel trace) rather than
failing later at side-matching like the other WWII cases below. Fixed by adding `"ublist"` to
`_LIST_TEMPLATE_NAMES`. Test: `test_ublist_alias_keeps_result_field_text`.

Regenerating `data/auto/` against the fixed parser (same wikitext cache, `--min-battles 4`, no
re-crawl; archived pre-fix snapshot at `data/archive/2026-10-03-pre-h4-combatant-date-template-
fix/`):

| | Before (archived) | After (current) |
|---|---|---|
| battle rows | 1,887 | 2,327 |
| generals with >=1 row | 333 | 343 |
| Rommel's own-perspective rows | 2 | 3 |
| suspicious year-span rows (H1's sanity check) | 3 | 2 |

Side effect, not the point of this task: rerunning `war.roster.suspicious_year_rows` against
before/after `battles.csv` shows the set of flagged rows changed, not just shrank. Before:
`captain`/`Battle of Enniscorthy` (1798), `captain`/`First Battle of Garua` (1914),
`brigadier-general`/`Operation Strike of the Sword` (2009). After: `captain`/`Battle of
Enniscorthy` (1798, still flagged) and a new case, `general-officer`/`Battle of Eperjes` (1685),
that was not flagged before — most likely because more of that generic-rank-word `general_id`'s
battles now parse a usable year (new rows from this task's template-expansion fix), shifting
which year looks like the cluster and which looks like the outlier. The underlying bug (generic
rank words like "captain" collapsing multiple real people into one `general_id`, H1's open item)
is unchanged; this task did not investigate the new case further.

`scripts/eval_ingest.py` (177-row gold set): coverage and accuracy are unchanged within noise
(own/enemy troop strength 67%/65% coverage, 81-94%/77-91% within 1.5-3x; own/enemy casualties
58%/61% coverage, 70-95%/68-89% within 1.5-3x), as expected since these fixes touch
combatant/date/result-field template expansion rather than the strength/casualty extraction path
the gold set scores — confirmed by rerunning after the regen, not just assumed.

## Waterloo still has no rows — a second, unfixed cause

After the date fix, Waterloo's `date` field parses correctly (`1815-06-18`) and both `combatant1`
(`First French Empire`) and `combatant2` (`United Kingdom of Great Britain and Ireland`,
`Prussia`, `United Kingdom of the Netherlands`, `Hanover`, `Nassau`, `Brunswick`) expand fully.
The row is still lost at the outcome stage: `result` is `"Coalition victory"`, and
`war.rules.outcome_from_result`'s side-matching works by stemming the adjective before "victory"
into a demonym and looking for that stem as a literal word in each side's combatant text. Neither
combatant field contains the word "coalition" — no side-matching system that works for "Roman
victory" vs. "Rome" can turn "Coalition victory" into a side without a lookup table of which
coalition opposed which power in which conflict, which is exactly the kind of per-battle
historical judgment call PROGRESS.md's rules keep out of this pipeline (no individual-battle
research). Not fixed here; `war/rules.py` is unchanged.

The same mechanism, with "Allied"/"Axis" instead of "Coalition", explains most of the funnel
trace's other `ambiguous_side_match` cases (Siege of Tobruk: "Allied victory" against `Australia;
United Kingdom...` and `Nazi Germany; Fascist Italy`; Battle of Gazala: "Axis victory"; Second
Battle of El Alamein: "Allied victory"; Battle for Caen: "Allied victory") — none of these words
appear as literal tokens in either side's combatant text, so `_side_match_score` ties at 0-0 for
both sides and the row is dropped as unresolved rather than mis-assigned to the wrong side.
Battle of the Kasserine Pass fails earlier and differently: its `result` field is the literal
text "See Aftermath section" (`no_victory_or_draw_keyword`), a Wikipedia editing convention this
pipeline has no way to resolve without reading the Aftermath section's prose, which is
battle-specific research, not parsing.

## Why Rommel still has few rows, and Patton/Bradley none

Rommel's own-perspective row count rose from 2 to 3 once the template-expansion fix let
Arras (1940) and other flag-templated battles parse at all, but most of his other famous battles
(Tobruk, Gazala, El Alamein, Kasserine) are still lost to the Allied/Axis generic-victory problem
above, not a parsing bug.

Patton and Bradley are a different, already-documented limitation, not a bug this task fixes.
`war.commanders.primary_commander`'s own docstring already flags it: "whoever is listed first in
the infobox commander field" counts as personally commanding a side, and infobox order reflects
whatever the article's editors wrote, not a verified command hierarchy. Both of Patton's and
Bradley's headline battles list someone else first — Battle of the Bulge's `commander1` is
`["Bernard Montgomery", "Omar Bradley", "Courtney Hodges", "George S. Patton", ...]`, and Operation
Cobra's is `["Bernard Montgomery", "Omar Bradley"]` even though Cobra was First US Army's
operation under Bradley, with Montgomery as 21st Army Group commander nominally above him. Both
battles credit Montgomery, not Bradley or Patton, under the current first-listed rule; Battle of
the Bulge also fails independently at outcome-matching for the Allied/Axis reason above, so it
would produce no row for *anyone* even if Bradley or Patton were listed first.

## Multi-commander credit loss, measured across the whole corpus

Across all 8,824 candidate battle titles, counting both sides of every cached page:
**15,364 sides have at least one named commander**, of which **7,510 (49%) name more than one** —
coalition and multi-army-group battles are closer to the norm than the exception in this corpus,
not an edge case. Summing `len(side) - 1` for every multi-commander side gives **18,278 named
subordinate or co-commanders who get zero credit** under the current "first name only" rule, more
than 5x the number of rows actually written at either battle count. This does not distinguish a
titular figurehead listed first from a real second-in-command (the same ambiguity
`primary_commander`'s docstring already names) — it is an upper bound on the credit the current
rule leaves on the table, not a claim that all 18,278 names should become rows.

## Famous-battle probe

For 18 reference-list generals NOT in `data/must_include.csv` (so the probe exercises the real
auto funnel instead of a hand-curated fallback), 1-2 of their best-known battles each, named from
general historical knowledge the same way PROGRESS.md's own H4 task text names Waterloo/Rommel/
Patton/Bradley (no web search or sub-agent call):

- 18/18 are candidate titles and 18/18 are already in the wikitext cache — coverage of famous
  battles by title is not the bottleneck.
- 6/18 (33%) produce a row for the named general. The 12 that do not fail for a mix of the same
  causes above: generic Allied/Axis/Coalition-style result phrasing (Thermopylae: "Greek victory"
  — not the same bug, worth checking separately), the first-listed-commander rule (several of
  these generals are not listed first on their own iconic battle's side), or a `result` field
  this pipeline's rules do not yet parse at all.

Full per-battle detail: `data/raw/h4_report.json` (gitignored; regenerate with
`python scripts/h4_missing_battles.py`).

## What this does and does not fix

Fixed, with tests: the three (four, counting `ublist`) template-expansion bugs above, which were a
real data-loss bug affecting far more than the four named cases — any infobox using flag, date-
range, or list templates for a field with no plain-text fallback. Not fixed, left as a documented
cause and a measured size of loss: demonym side-matching cannot resolve generic coalition-name
result phrasing, and `primary_commander`'s first-listed-name rule drops the majority of named
co-commanders corpus-wide. Both are method/scope limitations already partially documented in the
code (`primary_commander`'s own docstring) rather than parsing bugs, and fixing either would need
either a per-conflict alliance lookup (historical judgment, out of scope for this ingestion
pipeline) or a roster-design decision about whether co-commanders should get their own rows
(a method change, flagged for H9 rather than decided here).
