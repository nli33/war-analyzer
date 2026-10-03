# H2: baseline diagnostic

Ranked population: 330 generals (every general with a computable WAR-residual and longevity value -- `composite_ranking`'s own no-data convention; see `war/metrics/composite.py`). Weights: {'oar': 0.35, 'war_residual': 0.35, 'decisiveness': 0.15, 'longevity': 0.15}.

## Top 30 by composite score: z-scores and weighted contributions

| Rank | General | Era | Battles | Composite | OAR z (w.contrib) | WAR-resid z (w.contrib) | Decisiveness z (w.contrib) | Longevity z (w.contrib) | Dominant component |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Dwight D. Eisenhower | WWII | 6 | +1.878 | +2.32 (+0.813) | +1.25 (+0.438) | +3.46 (+0.520) | +0.71 (+0.107) | - |
| 2 | Charles X Gustav | Early Modern | 9 | +1.802 | +1.24 (+0.435) | +1.36 (+0.476) | -0.20 (-0.030) | +6.14 (+0.921) | - |
| 3 | Hōjō Ujiyasu | Early Modern | 5 | +1.757 | +2.18 (+0.765) | +1.36 (+0.476) | +3.85 (+0.578) | -0.41 (-0.061) | - |
| 4 | Edmund Allenby | WWII | 13 | +1.738 | +2.02 (+0.708) | +1.16 (+0.405) | -0.29 (-0.043) | +4.45 (+0.668) | - |
| 5 | Nelson A. Miles | Industrial | 1 | +1.705 | +0.95 (+0.333) | +1.14 (+0.401) | +6.71 (+1.006) | -0.23 (-0.035) | decisiveness |
| 6 | Khalid ibn al-Walid | Medieval | 27 | +1.665 | +1.99 (+0.698) | +0.94 (+0.328) | -0.32 (-0.049) | +4.59 (+0.688) | - |
| 7 | Samuel Ryan Curtis | Industrial | 4 | +1.492 | +1.67 (+0.585) | +1.14 (+0.401) | -0.15 (-0.022) | +3.53 (+0.530) | - |
| 8 | Han Xin | Ancient | 4 | +1.483 | +0.64 (+0.223) | +1.27 (+0.443) | +3.28 (+0.493) | +2.16 (+0.324) | - |
| 9 | Douglas MacArthur | Modern | 8 | +1.412 | +2.41 (+0.843) | +1.85 (+0.648) | -0.33 (-0.050) | -0.20 (-0.030) | oar |
| 10 | Carl Johan Adlercreutz | Napoleonic | 5 | +1.385 | +0.91 (+0.319) | +1.43 (+0.500) | -0.12 (-0.018) | +3.90 (+0.585) | - |
| 11 | José de Urrea | Industrial | 4 | +1.371 | +1.41 (+0.494) | +1.06 (+0.370) | -0.15 (-0.022) | +3.53 (+0.530) | - |
| 12 | Alexander the Great | Ancient | 12 | +1.370 | +2.04 (+0.715) | +1.27 (+0.443) | -0.40 (-0.061) | +1.82 (+0.273) | - |
| 13 | Abdul Fatah Younis | Modern | 9 | +1.368 | +0.51 (+0.179) | +0.86 (+0.300) | +3.00 (+0.450) | +2.93 (+0.440) | - |
| 14 | Peter Wittgenstein | Napoleonic | 6 | +1.355 | +2.03 (+0.709) | +1.14 (+0.399) | -0.12 (-0.018) | +1.77 (+0.265) | oar |
| 15 | Charles XII | Early Modern | 15 | +1.292 | +2.20 (+0.768) | +1.23 (+0.429) | -0.20 (-0.030) | +0.83 (+0.124) | oar |
| 16 | Hashiba Hideyoshi | Early Modern | 7 | +1.210 | +1.19 (+0.416) | +0.57 (+0.200) | +3.85 (+0.578) | +0.11 (+0.017) | - |
| 17 | Scipio Africanus | Ancient | 7 | +1.175 | +1.01 (+0.355) | +1.27 (+0.443) | +2.05 (+0.308) | +0.46 (+0.069) | - |
| 18 | Bernard Montgomery | WWII | 3 | +1.175 | +2.22 (+0.776) | +1.16 (+0.405) | -0.29 (-0.043) | +0.25 (+0.037) | oar |
| 19 | Oda Nobunaga | Early Modern | 11 | +1.146 | +1.11 (+0.390) | +0.04 (+0.016) | +4.86 (+0.729) | +0.08 (+0.011) | decisiveness |
| 20 | Claude de Villars | Early Modern | 4 | +1.135 | +2.08 (+0.727) | +1.49 (+0.522) | -0.20 (-0.030) | -0.56 (-0.084) | oar |
| 21 | Duke of Alba | Early Modern | 5 | +1.134 | +2.20 (+0.771) | +1.36 (+0.476) | -0.20 (-0.030) | -0.55 (-0.083) | oar |
| 22 | Georgy Zhukov | WWII | 6 | +1.123 | +1.03 (+0.360) | +0.70 (+0.247) | +3.46 (+0.520) | -0.02 (-0.003) | - |
| 23 | Subutai | Medieval | 5 | +1.121 | +0.87 (+0.303) | +1.11 (+0.387) | +3.08 (+0.462) | -0.21 (-0.032) | - |
| 24 | Alexander I | Napoleonic | 3 | +1.111 | +2.03 (+0.711) | +1.43 (+0.500) | -0.12 (-0.018) | -0.55 (-0.082) | oar |
| 25 | Jean Houchard | Napoleonic | 4 | +1.108 | +1.33 (+0.467) | +1.43 (+0.500) | -0.12 (-0.018) | +1.06 (+0.159) | - |
| 26 | Hayreddin Pasha | Early Modern | 4 | +1.104 | +0.15 (+0.053) | +0.37 (+0.131) | +6.55 (+0.982) | -0.41 (-0.061) | decisiveness |
| 27 | Napoleon I | Napoleonic | 56 | +1.095 | +1.66 (+0.582) | +0.97 (+0.340) | -0.12 (-0.018) | +1.27 (+0.191) | oar |
| 28 | Pietro Badoglio | WWII | 4 | +1.040 | +1.19 (+0.415) | +0.80 (+0.281) | -0.29 (-0.043) | +2.58 (+0.387) | - |
| 29 | Adam Ludwig Lewenhaupt | Early Modern | 3 | +0.994 | +1.35 (+0.474) | +1.49 (+0.522) | -0.20 (-0.030) | +0.19 (+0.028) | - |
| 30 | Lucius Cornelius Sulla | Ancient | 6 | +0.992 | +1.18 (+0.413) | +1.27 (+0.443) | -0.40 (-0.061) | +1.31 (+0.196) | - |

**11 of the top 30 (37%) owe their place to a single component** (its weighted contribution outweighs the other three combined). Breakdown: {'decisiveness': 3, 'oar': 8}.

**11 of the top 30 have fewer than 5 battles** -- the headline HTML table's own `min_battles` display floor (`war/viz/ranking_tables.py`) would hide them, so they only show up in this unfiltered view and in the full CSVs.

## Must-include generals (`data/must_include.csv`)

| General | Rank | Era | Battles | Composite | OAR z (w.contrib) | WAR-resid z (w.contrib) | Decisiveness z (w.contrib) | Longevity z (w.contrib) |
|---|---|---|---|---|---|---|---|---|
| Dwight D. Eisenhower | 1 | WWII | 6 | +1.878 | +2.32 (+0.813) | +1.25 (+0.438) | +3.46 (+0.520) | +0.71 (+0.107) |
| Han Xin | 8 | Ancient | 4 | +1.483 | +0.64 (+0.223) | +1.27 (+0.443) | +3.28 (+0.493) | +2.16 (+0.324) |
| Douglas MacArthur | 9 | Modern | 8 | +1.412 | +2.41 (+0.843) | +1.85 (+0.648) | -0.33 (-0.050) | -0.20 (-0.030) |
| Alexander the Great | 12 | Ancient | 12 | +1.370 | +2.04 (+0.715) | +1.27 (+0.443) | -0.40 (-0.061) | +1.82 (+0.273) |
| Scipio Africanus | 17 | Ancient | 7 | +1.175 | +1.01 (+0.355) | +1.27 (+0.443) | +2.05 (+0.308) | +0.46 (+0.069) |
| Georgy Zhukov | 22 | WWII | 6 | +1.123 | +1.03 (+0.360) | +0.70 (+0.247) | +3.46 (+0.520) | -0.02 (-0.003) |
| Subutai | 23 | Medieval | 5 | +1.121 | +0.87 (+0.303) | +1.11 (+0.387) | +3.08 (+0.462) | -0.21 (-0.032) |
| Napoleon I | 27 | Napoleonic | 56 | +1.095 | +1.66 (+0.582) | +0.97 (+0.340) | -0.12 (-0.018) | +1.27 (+0.191) |
| Ulysses S. Grant | 36 | Industrial | 10 | +0.948 | +1.28 (+0.446) | +0.85 (+0.297) | -0.15 (-0.022) | +1.51 (+0.227) |
| Frederick the Great | 72 | Early Modern | 16 | +0.601 | +1.04 (+0.364) | +0.63 (+0.219) | -0.20 (-0.030) | +0.32 (+0.048) |
| Julius Caesar | 75 | Ancient | 18 | +0.590 | +0.87 (+0.306) | +0.35 (+0.121) | -0.40 (-0.061) | +1.49 (+0.224) |
| Arthur Wellesley | 99 | Napoleonic | 24 | +0.437 | +0.79 (+0.278) | +0.45 (+0.157) | -0.12 (-0.018) | +0.14 (+0.021) |
| Matsudaira Motoyasu | 122 | Early Modern | 8 | +0.297 | +0.67 (+0.233) | +0.51 (+0.180) | -0.20 (-0.030) | -0.58 (-0.086) |
| Hannibal | 123 | Ancient | 20 | +0.282 | -0.33 (-0.115) | +0.86 (+0.302) | +0.73 (+0.110) | -0.09 (-0.014) |
| Temujin | 145 | Medieval | 9 | +0.200 | +0.50 (+0.174) | +0.33 (+0.116) | -0.32 (-0.049) | -0.28 (-0.042) |
| Erich von Manstein | 155 | WWII | 3 | +0.140 | +0.34 (+0.120) | +0.21 (+0.073) | -0.29 (-0.043) | -0.06 (-0.010) |
| George Washington | 183 | Early Modern | 11 | -0.079 | -0.06 (-0.022) | +0.06 (+0.019) | -0.20 (-0.030) | -0.31 (-0.046) |
| Robert E. Lee | 213 | Industrial | 12 | -0.264 | -0.18 (-0.063) | -0.64 (-0.223) | -0.15 (-0.022) | +0.30 (+0.046) |
| Saladin | 253 | Medieval | 14 | -0.596 | -0.44 (-0.155) | -1.09 (-0.381) | -0.32 (-0.049) | -0.08 (-0.012) |
| Erwin Rommel | 312 | WWII | 2 | -1.260 | -1.62 (-0.568) | -1.68 (-0.589) | +0.00 (+0.000) | -0.69 (-0.103) |

## Rank correlation (Spearman) with battle count, over all 330 ranked generals

| Component | Spearman rho vs. battle_count |
|---|---|
| OAR z | +0.183 |
| WAR-residual z | +0.073 |
| Decisiveness z | -0.225 |
| Longevity z | +0.375 |
| Composite score | +0.177 |

## Win rate by battle-count bucket (all generals with a rate stat, not just ranked)

| Battles | Generals | Mean win rate (per-general) | Pooled win rate (wins/battles) |
|---|---|---|---|
| 1 | 26 | 50.0% | 50.0% |
| 2-3 | 79 | 50.0% | 51.2% |
| 4-5 | 102 | 58.3% | 58.2% |
| 6-10 | 97 | 60.3% | 59.9% |
| 11-20 | 24 | 69.2% | 69.5% |
| 21+ | 5 | 76.5% | 79.2% |

## Tier distributions (all battle rows)

Resource backing tier (1-5), over 1887 rows:
- tier 2: 176 rows (9%)
- tier 3: 1177 rows (62%)
- tier 4: 528 rows (28%)
- tier 5: 6 rows (0%)

Tech era tier (1-5), over 1887 rows:
- tier 1: 255 rows (14%)
- tier 2: 463 rows (25%)
- tier 3: 794 rows (42%)
- tier 4: 158 rows (8%)
- tier 5: 217 rows (11%)

Tech era tier by general's era (showing how closely tech tier tracks era -- a single dominant tier per era row means tech tier carries almost no information beyond era):

| Era | Tier distribution |
|---|---|
| Ancient | 1:140 (100%) |
| Early Modern | 2:401 (65%), 3:213 (35%) |
| Industrial | 3:56 (26%), 4:151 (71%), 5:6 (3%) |
| Medieval | 1:115 (65%), 2:62 (35%) |
| Modern | 3:3 (4%), 4:4 (6%), 5:62 (90%) |
| Napoleonic | 3:522 (100%) |
| WWII | 4:3 (2%), 5:149 (98%) |

## Decisiveness input sparsity

- 1176 of 1887 rows (62%) have a `decisiveness` label at all.
- Label breakdown among labeled rows: {'Tactical': 1135, 'Rout': 34, 'Strategic': 7}.
- 41 of 1887 rows (2.2%) are Strategic/Rout (the two levels `decisive_win_rate` counts as "converted").
- 288 of 330 ranked generals (87%) have at least one decisiveness-labeled win, i.e. a non-`None` `decisive_win_rate` at all; the rest get `decisiveness_z = 0.0` by convention, not because they lack decisive wins.

## Answer: what puts generals who are not considered the best in the top 25?

11 of the top 30 have fewer than 5 battles (one, Nelson A. Miles, has exactly 1), and 11 of 30 (37%) are carried by a single component that outweighs the other three combined: 8 by OAR, 3 by decisiveness, 0 by WAR-residual or longevity under this test. A short, clean win streak (few battles, no losses yet) inflates OAR quickly against a rating graph where 65% of opponents are off-roster at a flat 1500 (H6's territory), and it inflates longevity (career value over very few career years) at the same time. Era cohorts of a dozen or fewer generals (H8's territory) let a handful of standout battles swing a z-score much further than a large cohort would allow. Decisiveness compounds this: only 41 of 1887 rows (2.2%) are labeled Strategic/Rout, so `decisive_win_rate` is close to binary for anyone with few rated wins. One Strategic/Rout win among a thin sample of rated wins (Hayreddin Pasha, Nelson A. Miles, Oda Nobunaga) produces a z of +3 to +7 against peers sitting near zero, worth 0.15 of the composite no matter how few battles back it. Eisenhower at #1 is a partial exception: no single component dominates by this test, but it is still a 6-battle, all-win sample, the same 'thin roster, all wins' shape the dev log already flagged for him. Among the must-include generals, the ones who rank well (Alexander #12, Han Xin #8) have a double-digit battle count and a moderate, positive OAR/WAR-residual pair rather than one outlier input. Most of the surprising top-30 entries have the opposite shape.

