# Project Scope: Statistical Ranking of Military Generals

## Goal

Produce explicit, quantitative rankings of historical military generals — treating them like NBA players with career stats, advanced/adjusted metrics (a "WAR" analog), and scatter-plot style comparisons (e.g. offense vs. defense, volume vs. efficiency, tactical vs. strategic). Comparisons span eras (ancient to WWII) despite the inherent haziness of that — this is embraced, not hedged around. Uncertainty is handled via confidence bands/intervals on the stats themselves, not by refusing to rank.

Final deliverables:
- A composite "power ranking" (single ordered list)
- Multiple sub-rankings by stat category (see Section 4)
- Scatter plots comparing generals on two axes at a time (e.g. Win Rate vs. Force Ratio Overcome, Volume vs. Efficiency)
- A structured dataset (CSV/DB) of battles/campaigns underlying everything, so rankings are traceable and re-weightable

## Roster (initial, expandable)

Napoleon Bonaparte, Julius Caesar, Georgy Zhukov, George Washington, Robert E. Lee, Dwight D. Eisenhower, Alexander the Great, Hannibal Barca, Genghis Khan, Erwin Rommel, Ulysses S. Grant, Frederick the Great, Wellington, Subutai, Scipio Africanus, Erich von Manstein, Douglas MacArthur, Sun Tzu (if enough battle data exists), Saladin, Tokugawa Ieyasu.

Target: 15–25 generals. Prioritize those with enough sourced battle-level data over completeness.

## 1. Unit of Analysis

**Atomic unit = individual battle/campaign commanded.** Roll up to career-level stats per general (like game logs → season → career in sports). This lets us:
- Track a general's performance trajectory over time (early vs. late Napoleon)
- Weight recent/large-scale campaigns differently from minor skirmishes
- Compute rate stats (per-battle) and counting stats (career totals) separately, same as sports

## 2. Data Schema (per battle/campaign row)

| Field | Description |
|---|---|
| general_id | Foreign key |
| battle_name, date, era | Identification/normalization key |
| own_troop_strength | Numeric estimate |
| enemy_troop_strength | Numeric estimate |
| own_casualties, enemy_casualties | Numeric estimate |
| outcome | Win / Loss / Draw |
| decisiveness | Tactical win only / Strategic win / Pyrrhic / Rout |
| objective_secured | Bool — was the stated goal (territory, siege, destruction of enemy force) achieved |
| opponent_general_id | For opponent-adjustment / Elo chaining |
| resource_backing_tier | 1–5 scale: manpower reserves, treasury, industrial capacity available at the time |
| tech_era_tier | Normalizes weapons/logistics/comms technology by period |
| political_constraint_flag | Was the general operating under significant political interference |
| source_confidence | High / Medium / Low — tags how reliable the strength/casualty figures are |
| source_citation | Where the numbers came from |

## 3. Data Gathering Methods

1. **Hand-curated core dataset** (primary method) — spreadsheet built battle-by-battle with cited sources. Given the target size (15–25 generals, maybe 300–600 battles), scraping-at-scale is not worth the noise; manual curation with citations is more defensible and easier to audit/correct.
2. **Primary reference sources**:
   - Clodfelter, *Warfare and Armed Conflicts* — casualty/strength reference spanning ancient to modern
   - Correlates of War project — structured interstate conflict data (modern era)
   - Osprey Publishing campaign series — battle-level strength/casualty estimates with historiographic notes
   - Wikipedia battle infoboxes — usable as a scaffold/cross-check, not a sole source (infobox numbers often disagree with academic sources; flag discrepancies)
3. **Scraping**: build a lightweight scraper for Wikipedia infoboxes to generate a first-pass draft dataset (troop strength, casualties, outcome), then manually verify/correct against academic sources before finalizing. Scraper output should never be used unverified.
4. **Ancient/medieval sourcing caveat**: treat ancient figures (Caesar, Hannibal, Alexander) as inherently low-confidence — ancient sources are often self-serving (Caesar's *Commentarii*) or centuries-removed. Tag `source_confidence = Low` and let this propagate into wider confidence intervals rather than excluding these generals.

## 4. Metrics

### Raw / counting stats (career totals)
- Battles commanded, campaigns commanded
- Total wins / losses / draws
- Total troops commanded (career volume)
- Total enemy casualties inflicted, total own casualties taken

### Rate stats (per-battle)
- Win rate
- Casualty exchange ratio (enemy:own)
- Average force ratio faced (how often outnumbered vs. numerically superior)
- Decisive win rate (wins converted to strategic gain vs. tactical-only)

### Adjusted / advanced stats (the "WAR" layer)
- **Opponent-Adjusted Rating (OAR)**: Elo-style iterative rating. Beating a highly-rated opponent general boosts rating more than beating a weak one; ratings for all generals are solved simultaneously/iteratively until convergent (same approach chess/Elo systems use to bootstrap ratings with no fixed baseline).
- **Expected-Outcome Residual ("General WAR")**: regress battle outcome (or margin of victory/casualty ratio) against force ratio, resource_backing_tier, and tech_era_tier. The general's stat is the residual — performance above/below what those inputs alone predict. Positive residual = outperformed expectations given what they had to work with.
- **Clutch Rating**: performance specifically in battles where own force was outnumbered or resource-disadvantaged (the "playing from behind" stat).
- **Squander Index**: rate at which tactical wins failed to convert into strategic/political gains (captures the Lee-style "brilliant on the field, lost the war" pattern).
- **Longevity-Adjusted Value**: career value normalized for number of years/campaigns active, to separate volume compilers from short, dominant peaks (e.g. Alexander's short career vs. Eisenhower's).

### Era normalization
All rate stats are z-scored within era-cohort (Ancient / Medieval / Early Modern / Napoleonic / Industrial / WWII) before being combined into any cross-era composite, so "beating expectations for your era" is the comparable unit, not raw numbers.

## 5. Uncertainty Handling

- Every battle-level input carries a `source_confidence` tag.
- For Low-confidence battles, sample troop/casualty figures from a plausible range (Monte Carlo) rather than using a single point estimate; run the full pipeline N times to produce a **distribution** of each general's rating, not a single number.
- Report rankings with confidence intervals (e.g., "Caesar: OAR 82 ± 15" vs. "Zhukov: OAR 79 ± 4") — wide bars for ancient generals are a feature of the output, not something to suppress. The point ranking still gets produced regardless.

## 6. Output Deliverables

1. **Composite Power Ranking** — single weighted ordered list (weights on OAR, WAR-residual, decisiveness, longevity — documented and tunable)
2. **Category Rankings** — separate ordered lists for: Win Rate, Casualty Efficiency, Opponent-Adjusted Rating, Clutch Rating, Squander Index, Longevity-Adjusted Value
3. **Scatter Plots** (2D comparisons, sports-reference-style):
   - Volume (battles/troops commanded) vs. Efficiency (win rate or casualty ratio)
   - Tactical rating vs. Strategic rating (identifies "brilliant tactician / poor strategist" outliers)
   - Opponent-Adjusted Rating vs. Resource Backing (identifies over/underperformance relative to what they were given)
4. **Underlying dataset** (CSV) — battle-level rows, fully traceable, re-weightable, and extensible to add more generals later

## 7. Build Plan (suggested phasing)

1. Build the schema + hand-curate data for 5–8 generals first (one per era) to validate the pipeline end-to-end
2. Build the Wikipedia infobox scraper as a draft-data generator, verify against academic sources
3. Implement Elo/OAR iterative solver
4. Implement expected-outcome regression + residual ("WAR") calculation
5. Expand dataset to full roster (15–25 generals)
6. Build visualization layer (rankings tables + scatter plots)
7. Tune composite ranking weights, sanity-check against qualitative historical consensus (not to overwrite the stats, just as a gut-check for bugs)
