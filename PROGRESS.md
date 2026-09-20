# Progress

## Phase 1: Scaffold
- [x] Repo structure + CSV schema matching PLAN.md Section 2 — `war/schema.py` is the authoritative definition; `data/battles.csv` and `data/generals.csv` written with headers generated from it
- [x] pytest harness runs (0 tests is fine at this point) — `pyproject.toml` configures pytest (repo root on `pythonpath`, doctests collected from `war/`); `tests/test_schema.py` holds 16 scaffold checks, 17 passing with the `parse_year` doctest

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

## Phase 7: Sanity pass and dev log
- [ ] Review composite ranking top/bottom against historian-consensus expectations, log findings (bug vs. legitimate surprise) in Notes below — do not hand-tune weights to force an order
- [ ] `notes/` dev log via the project-notes skill (SCOPE.md deliverable 6), written from the Notes section below and the commit history

## Notes / deviations
- Schema additions beyond PLAN.md Section 2: `battle_id` (stable row key), `notes` (free text
  for source disagreements), and a second file `data/generals.csv` (display name, era, career
  years) — all needed to make rows traceable and to compute longevity. Low complexity, no new
  research burden per row.
- Date format decision: `YYYY[-MM[-DD]]` with a leading minus for BC (`-0052` = 52 BC),
  astronomical-style with no year-zero correction. `schema.parse_year` is the one place that
  reads a year back out. A one-year offset is far below the resolution of anything computed here.
- `decisiveness` is required for a Win but optional for Loss/Draw, where the outcome often says
  everything (PLAN.md's four levels are phrased from the winner's side). For a Loss, `Rout` means
  this general's own army broke.
- The harness landed with 16 real tests rather than the zero the task allowed: header-vs-schema
  agreement and the date/bool parsing helpers were cheap to cover and prove the harness actually
  imports the package. `--doctest-modules` is on so the worked examples in `war/schema.py` stay true.
- `matplotlib` was listed in requirements.txt but missing from `.venv` (all of its dependencies were
  installed, so the original install was interrupted). Reinstalled during this task; Phase 6 would
  otherwise have hit it cold.
- `opponent_general_id` may point at a commander with no row in generals.csv; off-roster
  opponents get a default rating in the OAR solver rather than forcing 100+ extra curated rows.
