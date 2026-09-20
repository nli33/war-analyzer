# Progress

## Phase 1: Scaffold
- [ ] Repo structure + CSV schema matching PLAN.md Section 2
- [ ] pytest harness runs (0 tests is fine at this point)

## Phase 2: Data curation (8 generals, see SCOPE.md roster)
- [ ] Data validation script (required fields, valid enums, non-negative numerics, citation present)
- [ ] Julius Caesar battles
- [ ] Alexander the Great battles
- [ ] Genghis Khan battles
- [ ] Saladin battles
- [ ] Frederick the Great battles
- [ ] Napoleon Bonaparte battles
- [ ] Ulysses S. Grant battles
- [ ] Georgy Zhukov battles

## Phase 3: Metrics pipeline
- [ ] Raw/counting stats
- [ ] Rate stats
- [ ] OAR (iterative Elo solver) + unit tests
- [ ] WAR-residual (regression) + unit tests
- [ ] Clutch rating + unit tests
- [ ] Squander index + unit tests
- [ ] Longevity-adjusted value + unit tests

## Phase 4: Uncertainty
- [ ] Monte Carlo resampling (N>=1000) for Low/Medium confidence battles
- [ ] Test: High-confidence general has near-zero interval width
- [ ] Test: Low-confidence general has visibly wider interval

## Phase 5: Composite ranking
- [ ] Configurable weights (single config location)
- [ ] Composite ranking output
- [ ] Category rankings output
- [ ] Test: changing a weight changes the order

## Phase 6: Visualization
- [ ] Scatter: Volume vs Efficiency
- [ ] Scatter: Tactical vs Strategic rating
- [ ] Scatter: OAR vs Resource Backing
- [ ] Ranking tables rendered

## Phase 7: Sanity pass
- [ ] Review composite ranking top/bottom against historian-consensus expectations, log findings (bug vs. legitimate surprise) in Notes below — do not hand-tune weights to force an order

## Notes / deviations
(none yet)
