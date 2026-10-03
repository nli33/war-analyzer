# 2026-10-03 — pre-H4 combatant/date/list-template fix snapshot

What this is: `data/auto/generals.csv` (334 lines incl. header, 333 generals) and
`data/auto/battles.csv` (1,888 lines incl. header, 1,887 battle rows) exactly as H1's regen last
wrote them (`roster_selection_report.json`/`c6_report.json` in this directory, from that run),
before PROGRESS.md's H4 task fixed three template-expansion bugs in `war/scrape.py`. Superseded
by a rerun of `scripts/build_roster_selection.py`/`build_auto_battles.py` against the fixed code,
no re-crawl.

Why replaced — H4 traced why Waterloo has no rows for either side, why Rommel has only 2 rows,
and why many famous battles probed against the reference-list generals never produce a row, down
to one root mechanism: `_strip_wikitext_markup`'s generic "delete every `{{template}}`" pass
assumed a template's content is never the field's *only* copy of its information. That is true
for citation/formatting templates (`{{sfn|...}}`, `{{ndash}}`), which this snapshot already
handled correctly, but false for three template families whose argument text *is* the field:

1. **Flag templates** (`{{flag|X}}`, `{{flagcountry|X}}`, `{{flagicon|X}}`, `{{flagdeco|X}}`,
   `{{flagu|X}}`) write a combatant's country as a template argument, not surrounding plain
   text. Deleting the template deleted the country name outright. Most WWII-era infoboxes write
   combatants this way — Battle of Arras (1940)'s `combatant2` was entirely empty in this
   snapshot because `{{flagcountry|Nazi Germany}}` was its whole value, leaving the deterministic
   outcome rule nothing to match "German victory" against on either side.
2. **Date-range templates** (`{{Start date|...}}`, `{{End date|...}}`, `{{Start date and
   age|...}}`, `{{End date and age|...}}`) write a date as positional template arguments. Battle
   of Waterloo's `date` field is `{{Start date and age|1815|06|18|df=yes}}` with no plain-text
   fallback anywhere else in the field, so deleting the template left an empty string,
   `war.roster.extract_year` saw nothing to parse, and the row never got a year at all — the
   literal reason Waterloo had zero rows in this snapshot, for both sides.
3. **List templates** (`{{ubl|...}}`, `{{plainlist|...}}`, etc.) wrap several items, each
   commonly itself a flag template (a coalition's national contingents). Once the inner flag
   templates were already erased by bug 1, the list template had no nested braces left inside it
   by the time the generic delete regex reached it, so the whole list collapsed to nothing
   instead of each item surviving as its own clause.

Fixed by `war/scrape.py`'s new `_expand_known_templates`, which runs before the generic
template-delete pass and replaces only these three families with their meaningful argument text
(recursing into nested templates, since a flag template is routinely one item of a `{{ubl|...}}`
list) — every other template is left alone for the existing blanket delete. Tests:
`tests/test_scrape.py`'s `test_start_date_template_expands_to_a_parseable_date`,
`test_flag_templates_keep_the_country_name_not_just_the_icon`,
`test_flag_template_with_year_disambiguator_keeps_only_the_country_name`,
`test_ubl_list_of_flag_templates_keeps_every_country_name`.

A fourth, smaller bug in the same family was found and fixed in the same pass: `{{ublist|...}}`
— Wikipedia's own redirect alias for `{{Unbulleted list}}` — was missing from the list-template
name set even though the longer-named aliases (`"unbulleted list"`, `"ubl"`) were already
present, so any `result` field wrapped in `{{ublist|...}}` (132 of 8,433 cached battle infoboxes,
including Battle of the Bulge's `{{ublist|Allied victory}}`) lost its result text entirely.
Fixed by adding `"ublist"` to `_LIST_TEMPLATE_NAMES`. Test:
`test_ublist_alias_keeps_result_field_text`.

Measured effect, this snapshot vs. the regenerated one (`data/raw/c6_report.json`, captured after
each regen): battle rows 1,887 -> 2,327; generals with at least one row 333 -> 343; Rommel's
own-perspective rows 2 -> 3. Full before/after numbers and the remaining causes these fixes do
*not* reach (demonym side-matching can't resolve generic "Allied victory"/"Axis victory"/
"Coalition victory" phrasing against literal country names, and `primary_commander`'s
first-listed-name rule still drops co-commanders like Bradley/Patton) are in
`notes/ranking-diagnosis/H4-missing-battles.md`.

Quality gate: `scripts/eval_ingest.py` against the 177-row gold set is unaffected by these fixes
(they touch combatant/date/result-field template expansion, not the strength/casualty extraction
path `eval_ingest.py` scores) — see the H4 report for the actual before/after numbers.
`scripts/validate_data.py` passes (it validates the hand-curated gold set, untouched by this
task). Full pytest suite: 500 passed (4 new tests added by this fix, on top of the 496 already
passing before it).
