# Overnight Autonomous Build Scope

This is the concrete, locked scope for an unattended overnight development run based on PLAN.md.
Claude should work through the phases in order, committing incrementally, and stop/flag rather
than guess if a phase's exit criteria can't be met.

## Deliverable definition of done

By morning, the repo must contain:
1. A structured battle-level dataset (CSV, `data/battles.csv`) covering the initial roster below, with citations.
2. A metrics pipeline that computes all Section 4 stats from PLAN.md, including Monte Carlo
   uncertainty bands for low-confidence battles.
3. A composite power ranking + category rankings, output as data (CSV/JSON) with confidence intervals.
4. Visualizations: the three scatter plots from PLAN.md Section 6, plus ranking tables — rendered
   as static files (HTML or PNG) viewable without a server.
5. A test suite covering: data schema validation, each metric calculation (known-input/known-output
   cases), and the Elo/OAR solver's convergence.
6. A `notes/` dev log (via project-notes skill) documenting deviations, decisions, and tradeoffs made
   along the way.

## Roster for this run (locked, not 15-25)

Start with **8 generals, one per era**, per PLAN.md Section 7 step 1 — this is the actual scope for
tonight, not the full 15-25 roster. Expanding beyond 8 is out of scope unless the 8-general pipeline
is fully working with time to spare:

- Ancient: Julius Caesar
- Ancient: Alexander the Great
- Medieval: Genghis Khan
- Medieval: Saladin
- Early Modern: Frederick the Great
- Napoleonic: Napoleon Bonaparte
- Industrial: Ulysses S. Grant
- WWII: Georgy Zhukov

## Phases

1. **Scaffold** — repo structure, Python env, CSV schema matching PLAN.md Section 2, empty test harness.
   Verify: `pytest` runs (even with 0 tests failing), schema documented in code (not just PLAN.md).
2. **Data curation** — research and hand-enter battles for the 8 generals via web research, citing
   sources per row. Target 8-15 battles per general (60-120 rows total). Tag `source_confidence`
   honestly; ancient generals default to Low unless a specific figure is well-corroborated.
   Verify: a data validation script checks required fields, valid outcome enums, non-negative
   numerics, and that every row has a `source_citation`.
3. **Metrics pipeline** — implement raw/rate stats, then OAR (iterative Elo), then WAR-residual
   (regression on force ratio + resource tier + tech tier), then clutch, squander, longevity-adjusted.
   Verify: unit tests with hand-computed expected values on small synthetic battle sets for each metric.
4. **Uncertainty** — Monte Carlo resampling of Low/Medium-confidence troop/casualty figures, N=1000+
   runs, output distributions (mean + 90% interval) per general per metric.
   Verify: test that a High-confidence-only general has a near-zero interval width; a Low-confidence
   general has a visibly wider one.
5. **Composite ranking** — documented, tunable weights combining OAR, WAR-residual, decisiveness,
   longevity into one ordered list. Weights live in one config location, not hardcoded inline.
   Verify: changing a weight and re-running produces a different order (sanity check the pipeline
   isn't silently ignoring the config).
6. **Visualization** — the 3 scatter plots + ranking tables. Use the dataviz skill's guidance if
   producing HTML/artifact output. Verify: open the output and visually confirm axes, labels, and
   confidence bands render (a screenshot or manual render check counts as verification here).
7. **Sanity pass** — compare composite ranking top/bottom against historian-consensus expectations
   (e.g., does anyone universally considered a poor commander rank #1? does that flag a bug, not a
   "surprising insight"?). This is a bug-check, not a thumb on the scale — do not hand-tune weights
   to force a specific order.

Stop and flag (don't push forward) if: source data for a roster general is too thin to compute
metrics honestly, or a metric's implementation has no way to be verified against a hand-computed
expected value.

## Deciding whether to add a new data field/feature

Before adding any field to the schema or any new metric beyond PLAN.md Section 2/4, weigh:

- **Historical accuracy / historian consensus**: Is this something military historians actually use
  to evaluate generals (not something that sounds quantifiable but has no real evaluative grounding)?
  Is there a plausible, citable way to estimate it per battle?
- **Complexity cost**: Does it require new data sourcing work, a new normalization step, or new
  uncertainty handling? Does it make the schema harder to hand-curate consistently across 8 generals?

Add the field only if consensus-relevance is clearly high AND the complexity cost is low-to-moderate.
When in doubt, leave it out of tonight's run and note it in the dev log as a candidate for later —
don't expand scope mid-run to chase a nice-to-have field.
