# H7: gold set vs. auto data

Three `composite_ranking` runs, same weights ({'oar': 0.35, 'war_residual': 0.35, 'decisiveness': 0.15, 'longevity': 0.15}), same unmodified method, three different inputs: **gold-19** (19 gold generals, gold battle rows, population=19), **auto-19** (same 19 people resolved to their pipeline `general_id`, auto battle rows, population=19 -- the data-only control), **auto-full** (the real 343-general pipeline ranking, for context).

## Per-general: battle count, outcomes, strength coverage, rank

| General | Era (gold/auto) | Battles (gold/auto) | Win-Draw-Loss gold | Win-Draw-Loss auto | Strength cov. gold/auto | Rank gold-19 (pctl) | Rank auto-19 (pctl) | Rank auto-full (pctl) | Biggest shifted component |
|---|---|---|---|---|---|---|---|---|---|
| Dwight D. Eisenhower | WWII/WWII | 6/6 | 6-0-0 | 6-0-0 | 100%/100% | 1 (0.00) | 1 (0.00) | 7 (0.02) | war_residual (-0.11) |
| Ulysses S. Grant | Industrial/Industrial | 15/13 | 9-3-3 | 10-3-0 | 100%/92% | 2 (0.06) | 5 (0.22) | 20 (0.06) | decisiveness (-0.15) |
| Subutai | Medieval/Medieval | 5/5 | 5-0-0 | 5-0-0 | 100%/100% | 3 (0.11) | 3 (0.11) | 21 (0.06) | oar (+0.15) |
| Alexander the Great | Ancient/Ancient | 9/15 | 9-0-0 | 15-0-0 | 100%/60% | 4 (0.17) | 4 (0.17) | 9 (0.02) | oar (+0.18) |
| Duke of Wellington | Napoleonic/Napoleonic | 19/27 | 18-0-1 | 19-3-5 | 100%/96% | 5 (0.22) | 17 (0.89) | 78 (0.23) | oar (-0.70) |
| Frederick the Great | Early Modern/Early Modern | 12/19 | 9-1-2 | 14-1-4 | 100%/95% | 6 (0.28) | 6 (0.28) | 100 (0.29) | oar (-0.16) |
| Scipio Africanus | Ancient/Ancient | 5/7 | 5-0-0 | 6-0-1 | 100%/71% | 7 (0.33) | 8 (0.39) | 34 (0.10) | oar (-0.40) |
| Genghis Khan | Medieval/Medieval | 8/10 | 8-0-0 | 8-0-2 | 100%/50% | 8 (0.39) | 11 (0.56) | 130 (0.38) | longevity (-0.35) |
| Douglas MacArthur | WWII/Modern * | 6/12 | 5-0-1 | 7-0-5 | 100%/75% | 9 (0.44) | 10 (0.50) | 157 (0.46) | war_residual (-0.26) |
| Georgy Zhukov | WWII/WWII | 6/6 | 5-0-1 | 5-0-1 | 100%/100% | 10 (0.50) | 7 (0.33) | 16 (0.04) | longevity (+0.16) |
| Tokugawa Ieyasu | Medieval/Early Modern * | 6/8 | 5-0-1 | 6-1-1 | 100%/88% | 11 (0.56) | 9 (0.44) | 142 (0.41) | decisiveness (+0.26) |
| Erich von Manstein | WWII/WWII | 5/5 | 3-0-2 | 3-0-2 | 100%/100% | 12 (0.61) | 12 (0.61) | 172 (0.50) | decisiveness (-0.26) |
| George Washington | Early Modern/Early Modern | 12/15 | 6-2-4 | 7-2-6 | 100%/100% | 13 (0.67) | 18 (0.94) | 174 (0.51) | decisiveness (-0.15) |
| Napoleon Bonaparte | Napoleonic/Napoleonic | 14/63 | 11-1-2 | 55-2-6 | 100%/95% | 14 (0.72) | 2 (0.06) | 12 (0.03) | oar (+0.70) |
| Hannibal Barca | Ancient/Ancient | 7/20 | 6-0-1 | 13-1-6 | 100%/50% | 15 (0.78) | 14 (0.72) | 147 (0.43) | decisiveness (+0.22) |
| Julius Caesar | Ancient/Ancient | 11/20 | 8-0-3 | 17-0-3 | 100%/85% | 16 (0.83) | 13 (0.67) | 77 (0.22) | oar (+0.41) |
| Robert E. Lee | Industrial/Industrial | 14/23 | 6-2-6 | 6-7-10 | 100%/87% | 17 (0.89) | 16 (0.83) | 179 (0.52) | decisiveness (+0.15) |
| Saladin | Medieval/Medieval | 8/14 | 3-0-5 | 7-2-5 | 100%/43% | 18 (0.94) | 15 (0.78) | 257 (0.75) | longevity (+0.31) |
| Erwin Rommel | WWII/WWII | 9/3 | 4-1-4 | 1-0-2 | 100%/100% | 19 (1.00) | 19 (1.00) | 273 (0.80) | longevity (-0.24) |

`*` marks a gold/auto era mismatch (the auto pipeline derives era from parsed career years; the gold set's era was hand-assigned) -- this changes which cohort a general's z-score is computed against between the gold-19 and auto-19 runs, on top of any row-level data difference, for the generals marked.

**Biggest rank shifts, gold-19 -> auto-19 (same population, method held fixed):** Duke of Wellington (12), Napoleon Bonaparte (12), George Washington (5), Ulysses S. Grant (3), Genghis Khan (3), Georgy Zhukov (3).

## What explains the biggest shifts

**Napoleon (rank 14 -> 2) is a data-volume effect, amplified by a near-singleton cohort.** Auto gives Napoleon 63 rows against the gold set's 14 (H4's template-expansion fix recovered dozens of smaller Napoleonic-era battles the hand curator never added), at a similar win rate (87% vs 79%) -- but the Napoleonic era inside this 19-general population has exactly two members, Napoleon and Wellington. With only one peer, the within-era z-score reduces to a two-point comparison: any gap between the two gets stretched to the same z regardless of how many battles produced it, so a modest win-rate edge over a much bigger sample swings OAR's weighted contribution by +0.70, the single largest shift in this table. The auto-19 control holds population size fixed at 19 as designed, but not era-cohort *size* per era -- this is the same cohort-size sensitivity H8 is tasked with measuring, showing up here as a confound in this task's own control rather than a clean data-only effect.

**Napoleon and Wellington's relative order still has no shared battle in the auto data, unlike the gold set.** The gold set's two Waterloo rows cross-reference each other directly (`opponent_general_id=wellington` / `napoleon-bonaparte`), the one head-to-head anchor between them. H4 already found the auto pipeline produces zero Waterloo row for either side (the "Coalition victory" demonym-matching gap), and H6 measured the consequence: with no shared battle, their OAR gap is purely a function of each one's disjoint opponent pool and swings ~115 Elo points across three reasonable rating methods. This table's rank-14-to-2 swing for Napoleon and rank-6-to-17 swing for Wellington (in opposite directions) is that same missing-anchor problem, now visible in the composite ranking itself rather than just the raw OAR gap.

**Several generals lose real strength-field coverage going from gold to auto**, which feeds directly into the WAR-residual regression's `force_ratio` input (H5's territory): Saladin 100% -> 43%, Genghis Khan 100% -> 50%, Alexander 100% -> 60%, Hannibal 100% -> 50%. These are all pre-gunpowder generals, where infobox strength figures are more often textual estimates ("tens of thousands") that `war/infobox_numbers.py` cannot parse into a number at all, rather than a clean headline figure -- the hand curator filled in a researched estimate the automated parser has nothing to extract.

**Wellington's auto data picks up losses and draws the gold set doesn't have** (19-3-5 vs. the gold set's 18-0-1): the hand-curated 19 rows are the Peninsular War's well-known victories plus Waterloo, while the 8 extra auto rows include less selectively-chosen engagements (smaller actions, rearguard fights) that a research-driven curation would have filtered for relevance -- not a parsing bug, but a scope difference between "a general's major battles" (gold set's brief) and "every battle page Wikipedia's commander wikilink points to" (the auto pipeline's brief).

## Answer: if the method is fed good data, how close does it get to the reference lists?

15 of the 19 gold generals appear on at least one of `data/reference/top_n_lists.csv`'s published lists (under 16 distinct listed name strings, since some sources list the same person as both "Napoleon" and "Napoleon Bonaparte"): ['Alexander the Great', 'Douglas MacArthur', 'Dwight D. Eisenhower', 'Erwin Rommel', 'Frederick the Great', 'Genghis Khan', 'George Washington', 'Georgy Zhukov', 'Hannibal Barca', 'Julius Caesar', 'Napoleon Bonaparte', 'Robert E. Lee', 'Saladin', 'Subutai', 'Ulysses S. Grant']. Missing: ['Duke of Wellington', 'Erich von Manstein', 'Scipio Africanus', 'Tokugawa Ieyasu'].

Pooled Spearman correlation between published-list percentile and our composite percentile, over every (reference entry, source) pair that resolves to one of these 19 generals, across all sources at once (percentile, not raw rank, since gold-19's population is 19 and the published lists and auto-full's 343-general roster are on different scales -- same percentile normalization `war/reference_rankings.py`'s `biggest_disagreements` already uses):

| Data source | Spearman (published pctl vs. ours) | n pairs |
|---|---|---|
| gold-19 (hand-curated data, 19-general population) | +0.296 | 24 |
| auto-19 (auto data, same 19-general population) | +0.222 | 24 |
| auto-full (auto data, real 343-general pipeline) | +0.188 | 24 |

Fed the gold set's own hand-curated data, the unmodified composite method reaches +0.296 agreement with the published lists over these 24 pairs -- positive, but weak, nowhere near the strong agreement a reader expecting a "greatest generals" list would want. Switching only the data (auto-19, same 19-general population) drops that to +0.222; switching to the real pipeline's full 343-general population and era cohorts drops it further to +0.188. Both steps hurt, roughly equally -- data quality (H1/H4/H5/H6's territory) and cohort/population shape (H8's territory) each cost a comparable amount of reference-list agreement on top of the method's own, data-independent ceiling. That ceiling is the headline number for H7: even perfect data would not make this composite agree closely with "greatest general" intuition, because the composite is answering a different question (z-scored statistical performance within an era cohort) than the published lists are (subjective historical reputation) -- a method-shape limit, not merely a data-cleanliness one, for H9 to weigh against the cost of chasing better data alone.

