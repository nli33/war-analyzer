# Progress: find out why the ranking disagrees with historian consensus

The auto dataset now has 343 generals and 2,327 battle rows (task log archived at
`notes/PROGRESS-v3.md`, earlier ones at `notes/PROGRESS-v2.md` and `notes/PROGRESS-v1.md`). The
ranking it produces does not pass a gut check: Eisenhower is #1 on 6 rows, Nelson A. Miles is #4 on
1 battle, Napoleon is #49, Wellington #120, Genghis Khan #142, Hannibal #147, Rommel #312.

This run is diagnosis first. The goal is a written list of root causes, each with a measured effect
on the ranking, and an honest answer to "which parts of the method are overrated or underrated".
Fix clear bugs (task H1, and H4 if it finds one). Do not redesign the composite or its weights in
this run. The user reviews the report and decides.

## What is already known (check it, do not take it on faith)

- Career length comes from the min and max battle year. **Fixed by H1** (two `war/scrape.py` date-
  parsing bugs — Napoleon's Montenotte/Eckmühl and Wellington's Pombal were the named symptoms,
  a missing HTML-entity decode breaking BC years turned out to be the bigger cause). Napoleon's
  career is now 1794-1815, Wellington's 1799-1815; 4 of the 13 generals that had >80-year careers
  still do, but those are a different bug (generic rank words like "Captain" collapsing several
  real people into one `general_id`, not a date-parsing issue — still open). Longevity is wins
  divided by career years, so a correctly-dated short career still scores high relative to a long
  one; that shape of the metric itself is unchanged by H1 and is H8's to look at.
- 2006-2017 rows (Libya, Iraq, Syria, Macedonia; 64 rows, not 41) were tagged era WWII. **Fixed by
  H1**: a `"Modern"` era now starts in 1945.
- Only 41 of 1,884 rows are labeled Strategic or Rout, so decisiveness (15% of the composite) is
  mostly zeros, with a few 1.0s from one battle (Eisenhower, Zhukov).
- Roster generals win 62% of their rows. Generals with 11 or more rows win 73%. Wikipedia lists
  winners' commanders more fully, and the roster needs 4 usable battles.
- Resource tier is 3 on 63% of rows, and tech tier is nearly a function of era, so the WAR
  regression is mostly outcome against force ratio.
- Waterloo has no rows for either side. Rommel has 2 rows, and Patton and Bradley are not in the
  roster.
- Only 35% of opponents are on the roster. The rest sit at a flat 1500 Elo, so beating a garrison
  commander counts the same as beating Napoleon.
- The composite z-scores every input inside an era cohort. Cohorts range from 18 (Ancient) to 106
  (Early Modern) generals.
- Elo and the WAR residual use win/draw/loss only. Casualty counts are not in the composite, but
  strength is, through force ratio.

## Rules that still apply (do not re-ask)

- No agents or sub-agents researching individual battles or generals. No new LLM calls in this run.
  Reuse the existing caches (`data/raw/`, `data/auto/*.json`).
- Diagnosis tasks write reports and scripts only. Put reports in `notes/ranking-diagnosis/` (one
  markdown file per task, with a CSV next to it when there are tables). Use the ai-writing skill for
  the prose.
- Every claim in a report needs a number from the data. Say how it was measured.
- Time-box each task to one iteration. When a question needs more than that, write down what was
  found, what is left, and move on.
- The 19 hand-curated generals in `data/` stay untouched as the gold set. Before regenerating
  `data/auto/`, archive the current version to `data/archive/<YYYY-MM-DD>-<short-label>/` with a
  `README.md` (source, settings, counts, why replaced) and a line in `data/archive/INDEX.md`.
- Published "top N generals" lists are a reference check only, never a weight.
- Must-include generals (`data/must_include.csv`) stay in the roster.
- Do not change `war/config.py` weights or the composite formula. Experiments run through scripts
  that take the variant as a parameter and leave the shipped code alone.
- No `Co-Authored-By` or other AI attribution in commit messages.

## Phase H: Ranking diagnosis

- [x] H1. Fix date parsing and era assignment. Find why Montenotte parses as 1112, Eckmühl as 2122,
      and Pombal as 911 (likely a digit-grabbing regex on dates like "11-12 April 1796" or
      "1809 ... 22 April"). Fix it with tests built from the real infobox strings. Then add a
      sanity check that flags rows whose parsed year differs from the year in the battle title or
      from the general's other rows by more than a lifetime, and report how many rows were wrong.
      Fix the era assignment so post-1945 rows are not tagged WWII (add a modern era or exclude
      them, and note which). Regenerate `data/auto/` and `output/viz_auto/` after archiving. Verify:
      no career over 80 years except hand-checked ones, Napoleon's career is about 1796-1815, the
      quality floor still passes, and the gold-set comparison from `eval_ingest.py` does not get
      worse.
- [x] H2. Baseline diagnostic. For the top 30 and for the must-include generals, print each
      component's z-score and its weighted contribution to the composite (OAR, WAR residual,
      decisiveness, longevity). Report, over all ranked generals: the rank correlation of each
      component and of the composite with battle count; how many top-30 generals owe their place
      to a single component; the win-rate-by-battle-count table; the tier distributions; and how
      sparse the decisiveness input is. Answer: what puts generals who are not considered the best
      in the top 25?
- [x] H3. Ablation harness. Write a script that recomputes the ranking under variants and compares
      each with the reference lists (`data/reference/top_n_lists.csv`) and with the baseline: each
      component alone, drop-one component, equal weights, minimum battles of 1/3/5/10/20, and a
      shrinkage version (average pulled toward 0.5 by a pseudo-count) as a comparison only. Report
      Spearman against each reference list, the top 20 for each variant, and which variant moves the
      reference agreement most. Answer: which component is overrated and which is underrated?
- [x] H4. Missing battles. Find out why Waterloo has no rows for either side, why Rommel has only 2
      rows, and why Patton and Bradley are not in the roster. Trace each through the funnel
      (candidate, parsed commander, side match, strength, outcome). Then measure how many battles
      with several named commanders per side are lost or credited to only one of them, and how many
      of the top 50 most famous battles (use the 41 reference-list generals' battles as a probe) are
      missing. Fix a clear bug if one is found, with tests. Otherwise write down the cause and the
      size of the loss.
- [x] H5. Row granularity and credit. Sample 40 rows across the strength range and classify them as
      single engagement, campaign, or siege/operation, using title keywords (Campaign, Operation,
      War, Siege). Measure how many rows are campaign-scale and whether those generals rank higher.
      Check how the force-ratio input behaves for those rows (Eisenhower's 4.5M vs 1.6M "Rhine
      crossing and final drive"). Check whether attackers and defenders are distinguished, how
      draws are scored, and whether each of several commanders on a side gets full credit for a win.
- [ ] H6. Opponent strength. Today 65% of opponents are off-roster at a flat 1500. Test two
      variants in a script, not in the shipped code: rate off-roster opponents by their own
      record in the full battle universe (not only roster rows), and weight each battle by
      opponent rating quality. Report how many opponents have enough rows to rate and how the top 30
      and the must-include ranks change. Check the Napoleon-Wellington effect specifically: with
      Waterloo missing, what do the two ratings depend on?
- [ ] H7. Gold set against auto. Rank the 19 gold generals on the hand-curated data and on the
      auto data and compare. For each general, list the difference in battle count, outcomes, and
      strengths, and what moved their rank. This separates data error from method error. Answer:
      if the method is fed good data, how close does it get to the reference lists?
- [ ] H8. Era cohorts and longevity. Measure how much of each general's composite comes from their
      cohort (rank under a global z-score against rank under per-era z-scores), the effect of
      cohort size, and the singleton-era problem. For longevity, compare wins per career year with
      alternatives (wins per battle, career span from the general's birth and death years from
      Wikidata if cheap) after H1's fix. Report whether longevity still rewards tiny careers.
- [ ] H9. Findings report at `notes/ranking-diagnosis/FINDINGS.md`. List root causes ranked by how
      much of the gap to the reference lists each explains (use H3's numbers). For each: what it
      is, evidence, whether it is a data bug, a method flaw, or a scope limit, a proposed fix with
      cost, and what it would risk. End with a recommended order of work and the open decisions for
      the user. Update the README's known-limitations section. Do not implement the proposals.

## Notes / deviations

- **H1**: two bugs in `war/scrape.py`'s shared infobox-field cleanup, not one — template deletion
  splicing adjacent digits together (Montenotte/Eckmühl/Pombal, the named symptoms) and a missing
  HTML-entity decode that broke the BC-year regex (Alexander/Hannibal/Scipio/Pyrrhus, found by the
  new sanity check, bigger effect than the named bugs: 9 of 13 >80-year careers resolved, not 3).
  Era fix: added a `"Modern"` era at 1945 rather than excluding post-1945 rows, so they keep a
  real era cohort instead of being dropped. Sanity check (`war.roster.suspicious_year_rows`) is
  wired into `build_auto_battles.py`'s report, not a standalone script — prints flagged rows and
  the count. 3 rows still flagged after the fix: `general_id` in `{captain, brigadier-general}`
  etc. collapse multiple real people under a generic rank-word id, a identity-resolution bug, not
  a date bug — left for a future task (closest fit is H4's funnel tracing). Full writeup:
  `data/archive/2026-10-03-pre-h1-date-era-fix/README.md`. Napoleon moved #49 -> #27 and Hannibal
  #147 -> #123 in the composite as a side effect (not the point of this task, not re-tuned).
- **H2**: wrote `scripts/diagnose_baseline.py`, report at `notes/ranking-diagnosis/H2-baseline.md`
  (table CSV alongside it). Deviation found and fixed in the diagnostic script itself (not the
  pipeline): resolving must-include generals by `data/must_include.csv`'s own `general_id` column
  silently dropped Napoleon/Hannibal/Wellington, because that column is a hand-curated gold-set
  label (`napoleon-bonaparte`) that doesn't match the id the auto pipeline actually assigned
  (`napoleon`) — fixed by resolving through the same canonical-title identity pipeline
  `scripts/report_must_include.py` already uses. Headline finding: 11 of the top 30 have fewer
  than 5 battles and 11 of 30 (37%) are carried by one component outweighing the other three
  combined (8 OAR, 3 decisiveness) — thin samples swinging small-cohort z-scores, not rounded
  records. Full numbers and the correlation/win-rate/tier tables are in the report; this is
  diagnosis only, no weights or roster changed.
- **H3**: wrote `scripts/ablation_harness.py` (+ `tests/test_ablation_harness.py`), report at
  `notes/ranking-diagnosis/H3-ablation.md` (CSVs alongside it). 16 variants against 330 ranked
  generals and 4 reference-list sources, reusing `scripts/report_reference_rankings.py`'s cached
  identity resolution (all 32 reference names already cached, zero new network calls). Picked
  decisiveness as the one component to shrink — H3's "average pulled toward 0.5 by a pseudo-count"
  only fits a [0,1] rate, and of the four inputs only `decisive_win_rate` is one — with
  pseudo_count=5 reusing the project's existing `MIN_BATTLES_FOR_HEADLINE_RANKING` floor rather
  than guessing a number; min-battles variants filter the baseline ranking rather than re-rank it,
  matching `ranking_tables.py`'s own display-floor convention. Side finding, not fixed (out of
  this task's scope, flagged for H9): `composite_ranking`'s tie-breaking for generals with equal
  composite score depends on Python's hash-randomized set iteration order, so `decisiveness alone`
  (96 of 330 generals tied at the "no data" z=0.0 default) gives a different exact top-20 on every
  process run, confirmed by rerunning under several `PYTHONHASHSEED` values; every other variant's
  tied group is small enough that this doesn't matter. Headline numbers: dropping decisiveness or
  WAR-residual from the default weights both *hurt* mean reference-list Spearman (-0.026, -0.022),
  dropping OAR *helps* it slightly (+0.026) — on this reference-list signal OAR is mildly overrated
  and decisiveness/WAR-residual are not overweighted, though decisiveness alone is the
  single worst-performing input (-0.614 vs. baseline) because of its sparsity, not its weight.
  Shrinking decisiveness toward 0.5 was the biggest overall improvement of any variant tried
  (+0.032 mean Spearman), bigger than equal weights (-0.013, i.e. no help). No weights or roster
  changed.
- **H4**: wrote `scripts/h4_missing_battles.py` (funnel trace, report at
  `data/raw/h4_report.json`, gitignored), report at `notes/ranking-diagnosis/H4-missing-battles.md`.
  Root cause: `war/scrape.py`'s generic "delete every `{{template}}`" pass lost information for
  three template families whose argument text is a field's *only* copy of the data (flag templates
  for combatant country, date-range templates for Waterloo's whole `date` field, and list templates
  once their nested flags were already erased) plus a fourth alias (`ublist`) missing from the list
  set and dropping `result` text (e.g. Battle of the Bulge). Fixed with `_expand_known_templates`
  in `war/scrape.py`, 4 new tests in `tests/test_scrape.py`. Regenerated `data/auto/` after
  archiving to `data/archive/2026-10-03-pre-h4-combatant-date-template-fix/`: battle rows 1,887 ->
  2,327, generals with >=1 row 333 -> 343, Rommel's own-perspective rows 2 -> 3. Verified: 500
  pytest passing, `scripts/validate_data.py` passes, `scripts/eval_ingest.py` unchanged within
  noise (67%/65% strength coverage, 58%/61% casualty coverage, matching pre-fix). Waterloo still
  produces zero rows after the fix (second, unfixed cause): its `result` field is "Coalition
  victory", and demonym side-matching has no literal "coalition" to match against either
  combatant's text without a per-conflict alliance lookup table, which is out of scope
  (historical judgment, not parsing). Same mechanism explains most of Rommel's other missing North
  Africa battles (Allied/Axis phrasing) and is unrelated to Patton/Bradley's absence, which is
  `primary_commander`'s documented first-listed-commander limitation, not a bug — both list
  someone else first on their headline battles. Measured corpus-wide: 49% of battle sides name
  more than one commander, 18,278 named co-commanders get zero credit under the current rule.
  Famous-battle probe (18 reference-list generals not in must_include): 18/18 titles found in
  cache, only 6/18 (33%) produce a row, for the same generic-victory-phrasing and first-listed-name
  reasons. No weights, roster design, or `war/rules.py` changed; all open causes flagged for H9.
- **H5**: wrote `scripts/h5_row_granularity.py`, report at
  `notes/ranking-diagnosis/H5-row-granularity.md` (sample CSV alongside it). 15.3% of rows (357 of
  2,327) are campaign/siege-operation scale by title keyword; generals with at least one such row
  rank higher on average (mean rank 158 vs 183) but it's a plain association, not a controlled
  test. Biggest finding, not in the task's own framing: the force-ratio input mixes two
  incompatible units with nothing in the schema to tell them apart. The task's own named example
  (Eisenhower's 4.5M-vs-1.6M Rhine-crossing row) turned out to be hand-curated gold-set data
  copied verbatim (Eisenhower is one of 3 `hand_curated_fallback_general_ids`, not pipeline-
  derived), and its own notes field already flags the theater-vs-personal-command gap by hand. The
  pipeline reproduces the same failure in the opposite direction on its own, unprompted: when an
  infobox gives a strength field as a division/brigade breakdown instead of one troop number (e.g.
  Montgomery's Operation Cobra: "8 infantry divisions / 3 armored divisions" with no headline
  total), `war/infobox_numbers.py`'s sum-every-segment fallback adds the bare division counts as
  if they were soldiers (own_troop_strength=11), since `_UNIT_MULTIPLIER` has no entry for
  "division"/"brigade". Confirmed on 2 real pipeline rows and flagged corpus-wide (16 of 289
  campaign/siege-operation rows have an implausibly small <=200 strength figure, vs 176 of 1,784
  single-engagement rows). Confirmed no attacker/defender field anywhere (only Wikipedia's own
  combatant1/combatant2 order) and draws score symmetrically at 0.5/0.5 with no decisiveness
  label, matching the schema's documented rule. Credit-sharing: confirmed via a real example
  (Battle of Stalingrad, 16 vs 24 named commanders) that credit is all-or-nothing per side -- the
  first-listed commander gets the whole row, undivided, never split, which is the H4 finding's
  other half. No weights, roster, or `war/` code changed -- diagnosis only.
