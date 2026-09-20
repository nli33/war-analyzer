# Dev log: overnight war-analyzer build

This covers one unattended overnight run through SCOPE.md's seven phases, built directly
on PLAN.md's design. It's a narrative of how the work actually went — the decisions PLAN.md
and SCOPE.md left open, the places the plan changed shape on contact with real sources, and
the dead ends. The blow-by-blow judgment calls for each phase already live in PROGRESS.md's
per-task notes and the module docstrings; this document is the higher-level story connecting
them, plus anything that didn't fit neatly under a single checklist line.

A note on this file's own existence: CLAUDE.md calls for this log to be written "via the
project-notes skill" and for prose documentation to run through an "ai-writing" skill.
Neither skill is installed in this sandbox — `~/.claude/skills/` has no `project-notes` or
`ai-writing` entry. Per the run's own standing instruction (don't stop for missing pieces,
make the reasonable call and note it), this log was written by hand instead, aiming for the
same content a notes-focused skill would produce: decisions, deviations, tradeoffs, and the
rough shape of how the work went. Recorded as a decision in PROGRESS.md's Notes section too.

## Phase 1–2: scaffold and data curation

The schema (`war/schema.py`) ended up as the single source of truth a few different ways:
CSV headers, the validator's per-column rules, and the doctest-covered `parse_year` helper all
read off the same `Column` definitions rather than duplicating the field list. That wasn't
called for explicitly in PLAN.md, but building the validator against hand-copied field names
felt like the kind of duplication that drifts out of sync after the third data-entry session,
so the schema module grew slightly to prevent it.

Data curation for the locked 8-general roster (SCOPE.md's one-per-era set, not PLAN.md's full
15–25) is where most of the actual judgment calls landed, and where the real dead ends showed
up:

- **The no-fabrication bar.** Several well-known battles got dropped outright rather than
  filled in with a plausible-sounding number: Alexander's Battle of the Persian Gate (no
  casualty figure in any source, not even a disputed one), Genghis's Khalakhaljid Sands and
  Thirteen Sides, Saladin's Battle of Hama and four others. The schema requires every numeric
  field, so "no attested number" became "no row" rather than "invented row." This rule held
  for all eight generals and is the most-repeated judgment call in the whole curation phase.
- **Personal-command bar.** A battle only counts if the roster general held direct, personal
  command — not just influence or coordination. This is what excludes Zhukov's Stalingrad,
  Kursk, and Bagration (he was a Stavka coordinator over named front commanders there), and
  what shrinks his roster to 6 battles against everyone else's 8–15. It's a structural
  consequence of the Red Army's command system, confirmed by cross-checking Glantz/House
  against the named front commanders for each operation, not a research shortfall. The same
  bar dropped Frederick's Kesselsdorf, Grant's Corinth, and Saladin's al-Babein.
- **Mongol-source silence.** Several pivotal Genghis Khan sieges (Bukhara, Samarkand, the
  Indus, the Yellow River) are historically undisputed but have no source — not even a
  qualitative one — for Mongol-side losses. Dropping them would have cost more real signal
  than keeping an honestly-flagged placeholder figure preserves, so those rows carry an
  explicit "order-of-magnitude placeholder, not source-derived" note instead. This is the one
  place the no-fabrication bar bent rather than broke, and it's called out by name in both
  `generals.csv` and the row notes so it doesn't read as false precision later.
- **Self-serving sources.** Where a general's own chronicle numbers looked inflated or
  self-serving against modern historian estimates (Caesar's *Commentarii* on Bibracte and
  Pharsalus casualties, Krivosheev's official Soviet figure for Operation Mars vs. Glantz's
  revised count), the modern corrective was used, with the discrepancy logged in `notes`
  rather than silently picking one number.
- **`resource_backing_tier` as a per-row field.** PLAN.md defines it as one field per battle,
  which turned out to matter once Frederick's and Napoleon's careers were in the data —
  Frederick's material position drops from tier 3 to tier 1 across the Seven Years' War,
  Napoleon's swings from 2 (Italy) up to 5 (imperial peak) and back to 1 (Waterloo's isolated
  Hundred Days army). Treating it as a fixed per-general value would have erased exactly the
  kind of career-arc signal PLAN.md's later metrics (WAR-residual, clutch rating) are built to
  pick up.

## Phase 3: metrics pipeline

PLAN.md names each metric by concept ("opponent-adjusted rating," "clutch rating," "squander
index") but not always by formula, so this phase is where most of the pipeline's actual math
got decided. A few worth calling out because they weren't obvious going in:

- **OAR needed a decaying step size, not a surprise until it was tried.** A constant-K
  iterative Elo solver doesn't converge for a general with a perfect record (Alexander) or a
  winless one — nothing in the dataset offsets the one-sided expected-score math, so the
  rating gap grows without bound every epoch. Confirmed by hand-simulating a single repeated
  one-sided matchup past 200k epochs without convergence, before switching to
  `k_factor * decay**epoch`, which guarantees the remaining rating movement is a bounded
  geometric series.
- **Casualty exchange ratio is a totals ratio, not an average of per-battle ratios.** Averaging
  per-battle ratios lets one freak lopsided skirmish outweigh a battle 100x its size, and
  breaks outright on any single zero-casualty row. Summing career totals first sidesteps both,
  at the cost of `None` on a general with zero career casualties — a reachable case (the schema
  allows `own_casualties=0`), handled rather than assumed away.
- **Squander Index reuses the `decisiveness` enum rather than re-deriving "converted a win"
  from troop numbers.** The enum's own definitions (`Tactical`, `Pyrrhic` vs. `Strategic`,
  `Rout`) already answer the question PLAN.md is asking; re-deriving it from casualty ratios
  would just be a noisier version of a signal already in the data.

## Phase 4: uncertainty

The Monte Carlo resampler only touches the metrics whose formulas actually read the resampled
troop/casualty fields — win-rate-derived stats, OAR, squander index, and longevity are
untouched by design, so re-running them would just reproduce the same point estimate N times
under a different random seed. Deciding *not* to fake confidence intervals on those was as
much a design choice as building the resampler itself, and it directly shaped what the Phase 6
ranking table could honestly show (see below).

## Phase 5: composite ranking

The era-normalization step (z-score within era cohort before combining across eras) is where
this run's biggest known limitation was born, and it wasn't visible until real data went
through it. With the locked 8-general, one-per-era roster, four eras end up with exactly one
member (Frederick, Napoleon, Grant, Zhukov) — a z-score population of one is undefined
variance, so those four tie at composite 0.0 regardless of how good their underlying record is.
The two 2-member eras (Caesar/Alexander, Genghis/Saladin) are worse in a subtler way: with n=2,
the two z-scores per metric are mechanically forced into exact mirror images. For Genghis vs.
Saladin that happens to match a real quality gap. For Caesar vs. Alexander it doesn't — Caesar
gets pulled toward the negative of Alexander's score simply because Alexander is a historical
outlier (undefeated), not because Caesar's own record is weak by any individual metric. This
surfaced in Phase 7's sanity pass (Caesar ranks dead last despite leading or near-leading four
of the six category tables) and is discussed there rather than patched, per SCOPE.md's explicit
"don't hand-tune weights to force an order."

## Phase 6: visualization

Nothing in this phase deviated much from PLAN.md, but it's worth recording the dead end that
did happen: `matplotlib` was listed in `requirements.txt` but wasn't actually present in
`.venv` when this phase started — every one of its dependencies was installed, suggesting the
original `pip install` got interrupted partway through. Caught and fixed with a straight
reinstall before the scatter-plot work began; would have failed cold otherwise given the
no-display sandbox (OVERNIGHT.md's constraint meant there was no way to notice via casually
opening a chart — the PNG-plus-CSV verification convention this phase settled on catches
exactly this kind of thing).

The ranking table's confidence-interval columns are deliberately incomplete: PLAN.md's own
example format ("Caesar: OAR 82 +/- 15") implies every ranking number should carry a band, but
Phase 4's resampler only produces real ones for WAR-residual and Clutch Rating. Attaching a
fabricated interval to OAR or Longevity-Adjusted Value would look more rigorous than it is;
leaving those columns as plain point estimates is the more honest reading of "confidence
intervals for low-confidence battles," even though it means the table doesn't uniformly match
PLAN.md's illustrative format.

## Phase 7: sanity pass

Two things came out clean: the top of the ranking (Alexander, then Genghis Khan) and the
back-half-losing-streak signal on Saladin and Frederick's squander-index both match
historian-consensus reputations, which is some confirmation the pipeline is measuring
something real rather than noise. The one flagged issue — Julius Caesar ranking last overall
despite a strong category profile — traced back cleanly to the n=2 z-scoring problem described
in Phase 5, not to a data error or a formula bug. Per SCOPE.md's instruction for this phase,
it's recorded as a methodology limitation rather than something to reweight away.

## Open items for anyone picking this up

- The n=2/n=1 era-cohort z-scoring problem (Phase 5) would most likely resolve itself under
  PLAN.md's full 15–25 general roster, where each era cohort has enough members for the
  z-score to mean something. It isn't worth a special-case fix at 8 generals.
- The `project-notes` and `ai-writing` skills referenced in CLAUDE.md aren't present in this
  environment; this log and its prose were produced without them.
- Everything else this run intentionally left out of scope (5 more eras' worth of generals, the
  full 15–25 roster, deeper primary-source verification beyond Wikipedia/standard references)
  is PLAN.md's stated future work, not a gap introduced during this run.
