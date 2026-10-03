# H9: findings report

Synthesis of H1-H8. Root causes below are ranked by measured effect on agreement with the
published reference lists (`data/reference/top_n_lists.csv`), using H3's ablation numbers where a
cause maps onto one of the four composite inputs, and H4/H5/H6/H7/H8's own measurements where it
doesn't. Diagnosis only — nothing in `war/` or `data/auto/` changes here beyond this file and the
README's known-limitations section.

## 1. The composite answers a different question than "greatest general" intuition does

**What it is.** `composite_ranking` z-scores four performance statistics within an era cohort and
sums them. The published lists rank subjective historical reputation. These are not the same
quantity, and no amount of data cleanup closes that gap.

**Evidence.** H7 fed the method its best-case input: the 19 hand-curated gold generals, on their
gold battle rows. Pooled Spearman against the four reference lists: +0.296 (24 pairs). Switching
only the data to the auto pipeline's version of the same 19 people drops that to +0.222; switching
to the real 343-general population and era cohorts drops it again to +0.188. Two separate,
roughly equal-sized costs stack on top of a ceiling that was never high to begin with — +0.296,
fed hand-curated data with nothing else in the way.

**Classification.** Method flaw, not a data bug. The method's own definition of "good" is the
limit.

**Proposed fix, cost, risk.** None available at the diagnosis level — this is a scope decision for
the user, not a bug to patch. Three directions, not mutually exclusive: (a) accept the composite
as a statistical-performance ranking and stop expecting it to track "greatest general" lists,
relabeling the UI/README accordingly (cost: near zero, risk: none, but concedes the project's
original framing); (b) add a fifth input that is closer to reputation itself, such as reference-
list rank or citation count, which then needs a decision about whether a ranking that partly
encodes "what people already think" is still measuring what this project set out to measure (cost:
moderate — new data source, new weight to justify; risk: circularity); (c) leave the method as-is
and treat the reference lists as a sanity check only, not a target to optimize toward, which is
what PROGRESS.md's rules already say to do. Not implemented here.

## 2. Decisiveness is the sparsest input and the biggest lever H3 found

**What it is.** `decisive_win_rate` only counts a win as "decisive" if its `decisiveness` label is
Strategic or Rout. 41 of 1,887 pre-H4 rows (2.2%) carry one of those two labels (H2). A general
with one or two labeled wins gets a near-binary z-score against peers sitting at 0.

**Evidence.** H3: `decisiveness alone` is the worst-performing single-input variant measured,
-0.614 mean Spearman versus the default-weighted baseline, driven by 96 of 330 generals tied at
the same "no data" default z=0.0 (and, as a side finding, that tied group's exact order is not
reproducible between runs — Python's hash-randomized set iteration, not a ranking bug, but a
reproducibility one; see item 9). Dropping decisiveness from the default weights costs -0.026 mean
Spearman (removing it hurts slightly, so it is not simply overweighted) — but shrinking its raw
value toward 0.5 with a pseudo-count of 5 rather than dropping it outright is the single biggest
improvement of any of H3's 16 variants: +0.032. The input is useful in principle and actively
harmful in its current, un-shrunk form.

**Classification.** Data-thinness issue with a cheap, tested statistical fix (shrinkage), not a
parsing bug.

**Proposed fix, cost, risk.** Apply H3's shrinkage directly: average `decisive_win_rate` toward
0.5 with a pseudo-count (H3 used 5, reusing `MIN_BATTLES_FOR_HEADLINE_RANKING`'s existing
convention) before z-scoring. Cost: one function in `war/metrics/rate.py` or `composite.py`, a few
tests, no new data. Risk: low — H3 already measured the direction and size of the effect on the
real roster; the only open call is the pseudo-count's exact value, which PROGRESS.md's rules say
is the user's call, not this run's.

## 3. Longevity rewards tiny careers by construction, not by any data bug

**What it is.** `longevity_adjusted_value` sums (not averages) up-to-1.0 outcome scores across a
career and divides by career years, not battle count. A general who wins several battles inside
one calendar year scores above the ceiling a bounded rate metric should have.

**Evidence.** H8: 70 of 343 ranked generals (20%) have `longevity_adjusted_value` > 1.0, which is
mechanically impossible for a [0,1] rate like `win_rate`. Every one of the top 10 generals by this
metric has a 1- or 2-year career and under 20 battles. Swapping `win_rate` in for
`longevity_adjusted_value` as the fourth input (same weight, same z-scoring) drops every one of
them hard: Allenby 1 -> 8, Abdul Fatah Younis 13 -> 50, Rochejaquelein 31 -> 135, Adlercreutz
11 -> 38. H1's date-parsing fix changed *which* years a career spans; it never touched this
sum-over-years shape, which predates and is independent of that bug.

**Classification.** Method bug — the metric's formula produces values outside the range a rate
metric is supposed to have. H3's `drop longevity` delta against the reference lists is only -0.007
(small), so this bug is not costing much *reference-list* agreement today, but it is the clearest
case in this whole diagnosis of a composite input producing a logically impossible number, and it
is why several of H2's thin-record top-30 surprises (Allenby, Adlercreutz) are there.

**Proposed fix, cost, risk.** Divide by battle count instead of career years (effectively
`win_rate`, already shipped in `rate.py`), or cap the per-year sum at some ceiling, or switch to
average-outcome-per-year with the same [0,1] bound as every other input. Cost: low, H8 already
built and ran the `win_rate`-swap variant as a correctness check. Risk: this does change the
composite's ranking (H8 measured +0.983 Spearman vs. the shipped ranking, not identity), so it is
a real behavior change for the user to approve, not a no-op cleanup.

## 4. Missing head-to-head anchors leave some comparisons entirely method-dependent

**What it is.** `war/rules.py`'s side-matching stems the adjective before "victory" (e.g. "Roman
victory" -> "Rome") and looks for that stem as a literal word in each side's combatant text.
Generic coalition names ("Coalition victory," "Allied victory," "Axis victory") have no such
literal match on either side, so the row is dropped as unresolved rather than mis-assigned.

**Evidence.** H4: this is the sole, literal reason Waterloo produces zero rows for either Napoleon
or Wellington, and the same mechanism accounts for most of Rommel's missing North Africa battles
(Tobruk, Gazala, El Alamein). H6 measured the downstream cost for the one pair this matters most
for: Napoleon and Wellington share zero opponents anywhere in the dataset, so their OAR gap is
purely a function of each one's disjoint opponent pool, and it swings from +173 Elo (baseline
roster-only OAR) to +231 (full-universe OAR) to +116 (confidence-weighted OAR) across three
reasonable rating methods — about 115 Elo points of pure method choice on a comparison with no
data to anchor it. H7 confirmed this shows up in the composite ranking itself, not just the raw
Elo number: Napoleon 14 -> 2, Wellington 6 -> 17, opposite directions, switching only from gold to
auto data (same population, same era cohort).

**Classification.** Scope limit, documented in the code (`war.rules.outcome_from_result`'s
demonym-stemming approach has no way to resolve a coalition name without per-conflict historical
knowledge), not a parsing bug to patch generically.

**Proposed fix, cost, risk.** A hand-built lookup table of which named coalition/alliance fought
which side in which conflict (Napoleonic Coalition -> Britain/Prussia/Austria/Russia/etc., Allied
-> the obvious WWII roster, Axis -> the obvious WWII roster). Cost: a few dozen entries would
likely cover most of the corpus's recurring alliance names, a bounded one-time lookup rather than
per-battle research. Risk: this is exactly the kind of per-battle historical judgment call
PROGRESS.md's rules have kept out of the pipeline so far — a per-*conflict* lookup table is a
narrower, more defensible version of that, but the user should decide whether it crosses the line
PROGRESS.md draws, since the distinction (conflict-level vs. battle-level judgment) is a real one
but not a sharp one.

## 5. The first-listed-commander rule drops most of the corpus's named co-commanders

**What it is.** `primary_commander` credits a side's result entirely to whichever name Wikipedia's
infobox lists first in the `commander1`/`commander2` field. Every other named commander on that
side gets zero rows for that battle, and the first name gets the whole side's strength and outcome
as though they alone commanded.

**Evidence.** H4, corpus-wide: 7,510 of 15,364 battle sides (49%) name more than one commander;
summing every side's extra names gives 18,278 named co-commanders who get zero credit under the
current rule. This is the documented reason Patton and Bradley never make the roster (Montgomery
is listed first on both men's headline battles) and a contributing reason for Rommel's thin
record. H5 found the sharpest concrete example of the flip side — full, undivided credit: the
hand-curated Eisenhower row for the Rhine crossing assigns him the entire 4.5-million-man Allied
force across four separate army groups, because he is the (hand-entered) sole name on that side,
not because the pipeline mis-measured anything.

**Classification.** Method/scope limit, already partially documented in
`war.commanders.primary_commander`'s own docstring, not a bug this diagnosis phase fixes.

**Proposed fix, cost, risk.** Two different directions depending on what the user wants the
roster to mean: (a) split credit among named commanders on a side (e.g. each gets a fractional
row, or a separate row with a shared-command flag), which directly addresses campaign-scale
over/under-crediting but requires a roster-design decision about what a "battle" belongs to when
several people jointly commanded it; (b) leave first-listed-only as the rule but add commanders
beyond the first to the roster as their own candidates when they appear often enough across
battles, which would recover Patton/Bradley without changing how any individual battle is scored.
Cost: (a) is a real pipeline change (`war/commanders.py`, `invert_to_general_battles`, new tests);
(b) is smaller but still touches roster selection. Risk: (a) changes every multi-commander
battle's row count and strength numbers at once — a large, hard-to-fully-verify diff; H4 flagged
this as a roster-design decision for the user rather than deciding it here.

## 6. OAR's weight is mildly overrated relative to the reference lists, specifically because of thin, lucky records

**What it is.** A short, undefeated streak against a roster where most opponents sit at a flat
1500 Elo (see item 8) inflates OAR quickly. H2 found this is the single most common reason a
surprising name sits in the top 30.

**Evidence.** H2: 11 of the top 30 (37%) owe their place to one component outweighing the other
three combined — 8 of those 11 to OAR, 0 to WAR-residual or longevity under that same test. H3
confirms the direction at the aggregate level: dropping OAR from the default weights is the only
component-drop that *helps* mean reference-list Spearman (+0.026), while dropping WAR-residual or
decisiveness both hurt (-0.022, -0.026). `oar alone` also correlates worse with the baseline
ranking (+0.934) than `war_residual alone` does (+0.932 is close, but its reference-list numbers
are better: mean +0.457 vs. OAR-alone's +0.355).

**Classification.** Weighting/roster-composition issue — not a bug in OAR's math, a consequence
of combining it with a thin-opponent-pool rating graph (item 8) and no sample-size weighting
(item 7).

**Proposed fix, cost, risk.** PROGRESS.md's rules keep this run from changing `war/config.py`'s
weights, so no fix is implemented. If the user later decides to act on this: lowering OAR's
weight, or making OAR itself sample-size-aware (e.g. shrinking an Elo rating with few rated games
toward some prior, the same shrinkage principle H3 already validated for decisiveness), are the
two most directly supported directions. Cost: low for a reweight, moderate for an OAR-level
shrinkage change (touches `war/metrics/oar.py`). Risk: low, this is the best-evidenced reweighting
candidate in the whole diagnosis.

## 7. No sample-size weighting anywhere in the composite — already a known limitation, now with a size

**What it is.** A general with 1-4 battles is z-scored exactly like one with 50+. This is already
in the README's known-limitations section; H2 puts a number on how often it actually matters.

**Evidence.** H2: 11 of the top 30 (37%) have fewer than 5 battles — below the headline HTML
table's own display floor, so they are invisible there but still drive the raw ranking and the
full CSVs. This is the root mechanism behind items 2, 3, and 6 all showing up concretely in the
top 30 at once, not a separate, fourth cause — a thin sample lets one lucky Strategic win (item 2),
one short high-win-rate year (item 3), or one undefeated streak against weak opposition (item 6)
each swing a small-cohort z-score further than a larger sample would allow.

**Classification.** Already documented. No new classification needed; this entry exists to record
that H2-H8 collectively measured its size rather than just asserting it.

**Proposed fix, cost, risk.** Unchanged from the README's existing text: the display-only
min-battles floor already mitigates the *visible* ranking; a weighting fix for the underlying
composite score itself was out of scope for this diagnosis phase by PROGRESS.md's own rules (no
reweighting this run).

## 8. Off-roster opponents default to a flat 1500 Elo, but this barely moves the ranking

**What it is.** 81% of distinct opponents (59% of opponent-rows) never appear as a roster general,
so OAR treats them as an average, untested 1500-rated player.

**Evidence.** H6 built two alternatives — rating off-roster opponents from the full battle
universe, and confidence-weighting by how well-attested each opponent's own record is — and found
both move the ranking only slightly (Spearman +0.997 and +0.995 against the shipped baseline, 3 of
the top 30 swap under each). The reason: 655 of 999 off-roster opponents (66%) have only 1-2
identifiable battles anywhere in the whole cached universe, not just against the roster — the
bottleneck is Wikipedia's own coverage of these people, not which slice of the graph this project
chooses to rate them from. The one place this method choice clearly matters is item 4's
Napoleon-Wellington gap, where there is no shared battle to anchor the comparison at all.

**Classification.** Measured, mostly a non-issue. Worth keeping on record precisely because
PROGRESS.md's "what is already known" section opened this diagnosis phase assuming a bigger,
more fixable problem here than H6 actually found.

**Proposed fix, cost, risk.** Not worth the cost generally, per H6's own numbers — building the
full-universe graph only to move 3 of 30 top ranks is a lot of new plumbing for little gained
agreement. Worth revisiting narrowly for item 4's head-to-head cases specifically, where it is the
only lever available at all (no shared battle exists to fix instead).

## 9. Three small, cheap-to-fix items left over from earlier tasks

- **Row-granularity mixing of units in the force-ratio input** (H5): when an infobox gives a
  strength field as a division/brigade breakdown instead of one headline troop number,
  `war/infobox_numbers.py`'s sum-every-segment fallback adds bare division counts as if they were
  soldiers (`_UNIT_MULTIPLIER` has no entry for "division"/"brigade"). Confirmed on 2 real pipeline
  rows (Montgomery's Operation Cobra and Battle for Caen), and corpus-wide: 16 of 289
  campaign/siege-operation rows with a recorded strength have an own or enemy figure <=200, an
  implausible headcount at any battle's scale. Data/parsing bug. Fix: either add
  division/brigade/battalion multipliers with a documented approximate headcount (a judgment call
  about what number a "division" should mean, since real division sizes vary by era and army) or
  null the field when the only available text is a unit-composition breakdown rather than guessing
  a number. Cost: low, contained to `war/infobox_numbers.py` plus tests. Risk: low.

- **Generic rank-word identity collapse** (H1/H4, still open): `general_id`s like `captain`,
  `brigadier-general`, `general-officer` collapse several real people into one identity when an
  infobox lists only a generic rank, not a name. 2 rows still flagged by `suspicious_year_rows`
  after H1 and H4's fixes. Identity-resolution bug, not a date bug. Fix: closest existing precedent
  is H4's funnel-tracing approach — find where `war/identity.py` falls back to a rank word and
  either drop that row or require a real name. Cost: unscoped (not sized by this diagnosis), small
  row count suggests it is a narrow fix.

- **Non-reproducible tie order inside the decisiveness-default tied group** (H3): 96 of 330
  generals share the same z=0.0 default decisiveness value, and `composite_ranking`'s internal
  `set(...) & set(...)` intersection means their exact relative order is not reproducible across
  process runs (confirmed by rerunning under several `PYTHONHASHSEED` values). Does not affect any
  general with real decisiveness data, and the population-level findings in H2/H3/H6/H7/H8 are
  unaffected since none of them depend on ordering within that tied group — but it does mean two
  runs of the exact same code and data can print a different exact top-N list past the handful of
  generals with real decisiveness signal. Correctness/reproducibility bug. Fix: sort the tied group
  by a stable secondary key (e.g. `general_id`) before intersecting, or iterate a sorted list
  instead of a set. Cost: very low, contained to `war/metrics/composite.py`. Risk: essentially
  none — this is a pure determinism fix, not a ranking-quality change.

- **Stale docstring in `war/metrics/composite.py`**: the zero-variance-cohort paragraph still
  describes "this 8-general roster has four singleton-era generals" as a live concern. H8 measured
  zero singleton or two-person era cohorts in the real 343-general roster (smallest is Modern at
  12). Documentation-only; updated as part of this task (see below) rather than left for later,
  since it is a direct textual correction with no behavior change.

## Recommended order of work

1. Decisiveness shrinkage (item 2) and the longevity formula fix (item 3) first — both are small,
   both have a fix already built and measured in H3/H8's scripts, and both are unambiguous
   (one is a statistics fix for sparse data, the other corrects a value that is logically
   impossible for a rate metric).
2. The three small fixes in item 9 (force-ratio unit mixing, the tie-break determinism bug, the
   rank-word identity collapse) — each is narrow and self-contained, worth batching together.
3. Decide on item 1 (what the composite is for) before spending more effort chasing reference-list
   agreement through data fixes — H7 shows the ceiling is low enough that items 4-6 below will not
   close most of the gap even if all three are fixed.
4. Items 4 and 5 (coalition-name lookup table, co-commander credit) are the largest remaining
   levers but also the most expensive and the most likely to need the user's judgment call on
   where "deterministic pipeline" ends and "historical research" begins — not a blind "just build
   it" call.
5. Item 6 (OAR reweighting) only after 1-5, since its effect is partly a symptom of items 2/3/7
   rather than independent of them.
6. Item 8 (opponent-rating method) is not worth general-purpose work; revisit only inside a fix for
   item 4, where it is the only lever available.

## Open decisions for the user

- Does the composite stay a statistical-performance ranking (accept H7's ceiling, stop optimizing
  against the reference lists), or does it move toward reputation-weighted (new input, new
  circularity risk)?
- Is a per-conflict alliance/coalition lookup table (item 4) an acceptable, bounded exception to
  "no per-battle historical research," or does it cross a line PROGRESS.md meant to hold?
- Should co-commander credit (item 5) be split, or should the roster simply gain commanders who
  are never first-listed through a separate inclusion rule? These produce different rosters and
  different battle counts for existing generals (Montgomery's, in particular).
- Is a hand-picked division/brigade-size approximation (item 9's force-ratio fix) acceptable, or
  should those rows just be nulled instead of guessed?
- What pseudo-count should decisiveness shrinkage (item 2) use in production — H3 reused
  `MIN_BATTLES_FOR_HEADLINE_RANKING`'s existing convention (5) as a reasonable default, not a
  tuned answer.
