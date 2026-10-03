# H5: row granularity and credit

Measured against `data/auto/battles.csv` (2327 rows, 343 generals) and the baseline composite ranking from `war.metrics.composite.composite_ranking` with `war.config.DEFAULT_COMPOSITE_WEIGHTS`. Diagnosis only, per Phase H's rules: nothing in `war/` changed.

## Title classification, corpus-wide

Classified by a title-keyword regex: `campaign`/`war` -> campaign, `operation`/`siege` -> siege/operation, neither -> single engagement (checked case-insensitively, campaign checked first).

| category | rows | % of corpus |
|---|---|---|
| single engagement | 1970 | 84.7% |
| campaign | 3 | 0.1% |
| siege/operation | 354 | 15.2% |

357 of 2327 rows (15.3%) are campaign- or siege/operation-scale by this keyword rule, not a single tactical engagement.

## 40-row stratified sample (`H5-sample-40.csv`)

Sampled evenly across the own_troop_strength range (40 of 2073 rows with a recorded strength; rows without one can't be placed on a strength axis and are excluded from the sampling frame, though still counted above). Category breakdown of the sample:

- single engagement: 37
- campaign: 0
- siege/operation: 3

The sample's category mix (close to the corpus-wide mix above, since both are driven by the same title-keyword rates at every strength level) confirms campaign/operation rows aren't concentrated at one end of the strength range -- they appear from the smallest to the largest recorded strengths, which is itself the point: a "campaign" row's own_troop_strength is not reliably bigger than a single battle's, because (see below) it isn't reliably a troop count at all.

## Do campaign/siege-operation generals rank higher?

151 of 343 ranked generals (44.0%) have at least one campaign- or siege/operation-scale row. Mean composite rank (1 = best) for that group: 158. Mean rank for generals whose every row is a single engagement: 183. Top 30: 16 of 30 (53.3%) have at least one campaign/siege-operation row, against a 44.0% base rate in the full ranked population.

Having a campaign/operation-scale row is higher on average than having none, by mean rank. This is a correlation over whichever generals happen to have that kind of row (mostly WWII/Napoleonic theater commanders, who also have other things going for them -- longer careers, more battles, named opponents), not a controlled test that isolates row granularity's own effect; H3's ablation harness is the tool for isolating one input's effect; this task only measures the plain association.

## Force-ratio input for campaign/siege-operation rows

Median own_troop_strength: 18,000 for campaign/siege-operation rows (n=289) vs 13,625 for single-engagement rows (n=1784).

The task's own named example, Eisenhower's "Western Allied invasion of Germany (Rhine crossing and final drive)" (4,500,000 vs 1,600,000), is **not** a pipeline-generated row -- Eisenhower is one of the 3 `hand_curated_fallback_general_ids` in `data/raw/roster_selection_report.json` (with Zhukov and Subutai), so every one of his rows is copied verbatim from the hand-curated gold set (`scripts/build_auto_battles.py`'s `gold_battle_rows`), not derived from an infobox by the auto pipeline. The row's own `notes` field already documents, by a human curator's hand, exactly the force-ratio concern this task asks about: those two numbers are "the infobox's own campaign totals," not personal commands -- the actual river crossings were "each a subordinate army-group commander's own execution," and Eisenhower "does not even appear in [Operation] Plunder's own Wikipedia command list." So for this one general the force-ratio-at-theater-scale issue was already known and flagged by hand; it is not evidence of a pipeline bug by itself.

The same failure mode reproduces procedurally, though, with the opposite distortion: when an infobox's strength field gives a unit-composition breakdown ("8 infantry divisions / 3 armored divisions") instead of one headline troop number, `war/infobox_numbers.py`'s `extract_numeric_field` falls back to its "no headline total -> sum every parsed segment" rule and sums the bare division/brigade counts as if they were soldiers -- `_UNIT_MULTIPLIER` only knows "thousand"/"million"/"k"/"m", not "division"/"brigade"/"battalion". Two real pipeline-generated examples, both titled "Operation…" or a plain battle name:

- `bernard-montgomery-operation-cobra`: own_troop_strength=11, enemy_troop_strength=8 -- the infobox's `strength1` is "8 infantry divisions / 3 armored divisions / 2,451 tanks…", summed to 11 (divisions only, since 2,451 is attached to "tanks", caught by the equipment-count stripper); `strength2` similarly sums to 8 divisions.
- `bernard-montgomery-battle-for-caen`: own_troop_strength=22, enemy_troop_strength=24 -- same mechanism, `strength1`'s `{{ubl|4 armoured divisions|10 infantry divisions|…}}` summed as bare counts.

Corpus-wide: 16 of 289 campaign/siege-operation rows with a recorded strength have an own or enemy troop_strength <= 200 (implausible as an actual headcount at any battle's scale), vs 176 of 1784 single-engagement rows. force_ratio for a row like Operation Cobra (enemy/own = 8/11 = 0.73) is a division-count ratio, not a troop-strength ratio, feeding straight into `war.metrics.war_residual`'s pooled OLS fit and `rate.py`'s `avg_force_ratio_faced` alongside rows where the same field genuinely is a headcount in the hundreds of thousands -- the column mixes two different units with nothing in the data to tell them apart, not just a scale difference between a campaign and a battle.

## Attacker/defender

Not distinguished anywhere in the schema or the pipeline. `war/schema.py`'s `BATTLE_COLUMNS` has no attacker/defender field; the infobox fields the pipeline reads are Wikipedia's own `combatant1`/`combatant2` (`war/scrape.py`), which are whatever order that battle's article editors wrote them in -- not a verified battlefield role. `own_troop_strength`/`enemy_troop_strength` are assigned by which side the `general_id`'s own commander link falls on (`war/commanders.py`), with no attacker/defender asymmetry anywhere downstream (`force_ratio`, the composite, Elo). A general who successfully held a defensive position against a larger attacking force and one who attacked with a larger force and won score identically on every input this pipeline computes.

## Draws

159 of 2327 rows (6.83%) are outcome=Draw, detected by `war/rules.py`'s `_RESULT_DRAW_RE` matching "inconclusive"/"indecisive"/"stalemate"/"draw"/"status quo" in the infobox `result` text. 0 of those 159 have a non-empty `decisiveness` -- `decisiveness_from_result` returns `None` unconditionally for a Draw (schema.py: "there is no stronger label than a drawn outcome"), so this should always be 0 (confirms it is: 0). Both `war/metrics/oar.py` and `war/metrics/war_residual.py` map Draw to actual score 0.5, the same symmetric treatment as a human chess-Elo draw -- scored, not dropped, and not biased toward either side. No asymmetry found between how a Win, Draw, and Loss are scored beyond that 1.0/0.5/0.0 mapping.

## Credit for several commanders on one side

A side's primary commander (`war/commanders.py`'s `primary_commander`: whichever name is listed *first* in the infobox's `commander1`/`commander2` field, if wikilinked) gets the **entire** side's row -- the full `own_troop_strength` (the whole side's total, not divided by the number of named commanders) and the full Win/Loss/Draw outcome, exactly as if they had commanded alone. Every other named commander on that side gets zero rows for that battle (`invert_to_general_battles` only emits a link for each side's single `primary_commander`) -- already measured corpus-wide by H4 (49% of sides name more than one commander; 18,278 named co-commanders get zero credit). What H4 didn't measure directly: credit is never *split* between the named commanders who could in principle share it -- it is all-or-nothing per side, first name wins all of it, nobody else gets a fraction. The Eisenhower Rhine-crossing row above is the clearest real example: own_troop_strength=4,500,000 is the entire Allied force across Montgomery's, Bradley's, Patton's, and Devers' separate army groups, credited whole to Eisenhower as though he personally commanded all of it, while Montgomery/Bradley/Patton get no row for this battle at all (Bradley and Patton are absent from the roster altogether per H4; Montgomery is on the roster via his own, separate, smaller-scale battles).

A pipeline-side example: "Battle of Stalingrad" lists 16 commander(s) on side 1 and 24 on side 2; `invert_to_general_battles` produces 2 `GeneralBattleLink`(s) total for the battle (at most one per side), regardless of how many names the infobox gives.

## Answer

Row granularity is mixed and the data carries no flag for which kind a row is. 15.3% of rows are campaign/siege-operation scale by title keyword, and those rows do not behave like a tactical engagement scaled up -- their strength numbers are sometimes a theater-wide troop total (Eisenhower, hand-curated) and sometimes a bare division/brigade count mistaken for a headcount (Montgomery's Operation Cobra/Caen rows, pipeline-generated), with nothing in the schema distinguishing either case from an ordinary single-battle headcount. Attacker/defender is never tracked. Draws are scored evenly and consistently (0.5/0.5). Credit for a battle is all-or-nothing per side, going entirely to whichever name is listed first in the infobox, with no mechanism to split it among several commanders who may have truly shared command -- a campaign-scale row magnifies this because campaigns are exactly where several commanders sharing a side is most common (army-group command structures), so the single-commander-gets-everything rule and the row-granularity problem compound each other rather than being independent issues.

