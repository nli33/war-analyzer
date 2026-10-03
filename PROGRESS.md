# Progress: find out why the ranking disagrees with historian consensus

The auto dataset now has 340 generals and 1,887 battle rows (task log archived at
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
- [ ] H2. Baseline diagnostic. For the top 30 and for the must-include generals, print each
      component's z-score and its weighted contribution to the composite (OAR, WAR residual,
      decisiveness, longevity). Report, over all ranked generals: the rank correlation of each
      component and of the composite with battle count; how many top-30 generals owe their place
      to a single component; the win-rate-by-battle-count table; the tier distributions; and how
      sparse the decisiveness input is. Answer: what puts generals who are not considered the best
      in the top 25?
- [ ] H3. Ablation harness. Write a script that recomputes the ranking under variants and compares
      each with the reference lists (`data/reference/top_n_lists.csv`) and with the baseline: each
      component alone, drop-one component, equal weights, minimum battles of 1/3/5/10/20, and a
      shrinkage version (average pulled toward 0.5 by a pseudo-count) as a comparison only. Report
      Spearman against each reference list, the top 20 for each variant, and which variant moves the
      reference agreement most. Answer: which component is overrated and which is underrated?
- [ ] H4. Missing battles. Find out why Waterloo has no rows for either side, why Rommel has only 2
      rows, and why Patton and Bradley are not in the roster. Trace each through the funnel
      (candidate, parsed commander, side match, strength, outcome). Then measure how many battles
      with several named commanders per side are lost or credited to only one of them, and how many
      of the top 50 most famous battles (use the 41 reference-list generals' battles as a probe) are
      missing. Fix a clear bug if one is found, with tests. Otherwise write down the cause and the
      size of the loss.
- [ ] H5. Row granularity and credit. Sample 40 rows across the strength range and classify them as
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
