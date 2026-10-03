# H3: ablation harness

Ranked population (baseline): 330 generals. 16 variants, compared against the baseline and against 4 reference-list sources (gallup_1991, grunge, thecollector, watchmojo) from `data/reference/top_n_lists.csv`.

## Spearman correlation per variant

| Variant | Population | vs. baseline rank | vs. gallup_1991 | vs. grunge | vs. thecollector | vs. watchmojo | mean vs. sources | delta vs. baseline mean | largest tied-score group |
|---|---|---|---|---|---|---|---|---|
| Baseline (default weights) | 330 | +1.000 | +0.496 | +0.142 | +0.484 | +0.651 | +0.443 | +0.000 | 1 |
| oar alone | 330 | +0.934 | +0.481 | +0.100 | +0.279 | +0.560 | +0.355 | -0.088 | 5 |
| war_residual alone | 330 | +0.932 | +0.624 | +0.105 | +0.435 | +0.663 | +0.457 | +0.014 | 1 |
| decisiveness alone | 330 | -0.125 | +0.030 | -0.256 | -0.137 | -0.322 | -0.171 | -0.614 | 96 |
| longevity alone | 330 | +0.591 | -0.314 | +0.414 | +0.265 | +0.648 | +0.253 | -0.190 | 12 |
| drop oar | 330 | +0.966 | +0.473 | +0.227 | +0.501 | +0.677 | +0.470 | +0.026 | 1 |
| drop war_residual | 330 | +0.962 | +0.410 | +0.161 | +0.478 | +0.637 | +0.421 | -0.022 | 2 |
| drop decisiveness | 330 | +0.987 | +0.456 | +0.151 | +0.437 | +0.624 | +0.417 | -0.026 | 1 |
| drop longevity | 330 | +0.985 | +0.576 | +0.083 | +0.424 | +0.663 | +0.436 | -0.007 | 1 |
| equal weights | 330 | +0.986 | +0.423 | +0.172 | +0.476 | +0.651 | +0.430 | -0.013 | 1 |
| min battles >= 1 | 330 | +1.000 | +0.496 | +0.142 | +0.484 | +0.651 | +0.443 | +0.000 | 1 |
| min battles >= 3 | 271 | +1.000 | +0.496 | +0.142 | +0.484 | +0.690 | +0.453 | +0.010 | 1 |
| min battles >= 5 | 161 | +1.000 | +0.496 | +0.051 | +0.453 | +0.238 | +0.310 | -0.133 | 1 |
| min battles >= 10 | 42 | +1.000 | -0.643 | +0.471 | +0.452 | +0.364 | +0.161 | -0.282 | 1 |
| min battles >= 20 | 7 | +1.000 | n/a | +1.000 | +1.000 | -1.000 | +0.333 | -0.110 | 1 |
| decisiveness shrunk toward 0.5 (pseudo_count=5) | 330 | +0.981 | +0.534 | +0.196 | +0.562 | +0.608 | +0.475 | +0.032 | 1 |

Every `min battles >= N` variant's "vs. baseline rank" is +1.000 by construction: it filters the baseline ranking down to generals meeting the floor and keeps each survivor's original full-population rank rather than re-ranking the smaller pool (same "filter what's shown, never re-rank" convention `war/viz/ranking_tables.py`'s own `min_battles` display floor uses) -- a rank-preserving subset always correlates perfectly with itself. Its reference-source correlations get noisy at small populations: `min battles >= 20` is only 7 generals, one source has too few overlapping entries to compute at all (n/a), and the other three swing between +1.000 and -1.000.

`decisiveness alone`'s largest tied-score group (96 of 330 generals, all stuck at the "no rated wins" default `z=0.0`) means `composite_ranking`'s exact rank order *within* that group is not reproducible between runs -- it comes from Python's hash-randomized set iteration order (`war/metrics/composite.py`'s `ranked_ids = set(...) & set(...)`), confirmed by recomputing this variant under several `PYTHONHASHSEED` values while writing this script (different runs printed different names in positions past the handful with real decisiveness data). The `decisiveness alone` and `drop decisiveness` rows above therefore carry run-to-run noise on top of the sampling noise already flagged; every other variant's largest tied group is small enough (see the table's last column) that this does not meaningfully affect its numbers. Not a bug this task fixes (`war/metrics/composite.py` is untouched) -- flagged for H9.

## Which variant moves reference agreement most

- Biggest **improvement** in mean reference-source Spearman: **decisiveness shrunk toward 0.5 (pseudo_count=5)** (+0.032 vs. baseline's +0.443).
- Biggest **worsening**: **decisiveness alone** (-0.614).

## Top 20 per variant

**Baseline (default weights)**: Dwight D. Eisenhower, Charles X Gustav, Hōjō Ujiyasu, Edmund Allenby, Nelson A. Miles, Khalid ibn al-Walid, Samuel Ryan Curtis, Han Xin, Douglas MacArthur, Carl Johan Adlercreutz, José de Urrea, Alexander the Great, Abdul Fatah Younis, Peter Wittgenstein, Charles XII, Hashiba Hideyoshi, Scipio Africanus, Bernard Montgomery, Oda Nobunaga, Claude de Villars

**oar alone**: Douglas MacArthur, Dwight D. Eisenhower, Bernard Montgomery, Duke of Alba, Charles XII, Hōjō Ujiyasu, Claude de Villars, Alexander the Great, Charles John, Alexander I, Peter Wittgenstein, Edmund Allenby, Khalid ibn al-Walid, Crown Prince Constantine, Joseph Souham, Samuel Ryan Curtis, Napoleon I, Stanisław Koniecpolski, Simón Bolívar, Alexander Suvorov

**war_residual alone**: Douglas MacArthur, Bernardo de Gálvez, Claude de Villars, Maurice de Saxe, Duke of Marlborough, Fyodor Ushakov, Adam Ludwig Lewenhaupt, Mikhail Kutuzov, Jean Houchard, Alexander I, Charles Dumouriez, Carl Johan Adlercreutz, Louis-Nicolas Davout, Friedrich Wilhelm von Bülow, Guillaume Brune, Jean Lannes, Joseph Souham, Horatio Nelson, Aurangzeb, Charles V

**decisiveness alone**: Manuel Belgrano, Nelson A. Miles, Hayreddin Pasha, Oda Nobunaga, Hōjō Ujiyasu, Hashiba Hideyoshi, Georgy Zhukov, Dwight D. Eisenhower, Han Xin, Subutai, Frederick II, Abdul Fatah Younis, Scipio Africanus, Hannibal, Pierre Augereau, John S. Marmaduke, Aleksey Kuropatkin, Richard Taylor, Michelangelo Colli-Marchi, Günther von Kluge

**longevity alone**: Charles X Gustav, Rochejaquelein, Khalid ibn al-Walid, Edmund Allenby, Carl Johan Adlercreutz, Banastre Tarleton, José de Urrea, Chief Joseph, Samuel Ryan Curtis, Thomas Sumter, Antonio Ricardos, Abdul Fatah Younis, Pietro Badoglio, Charles Edward Stuart, Guy Carleton, Count of Estaing, Han Xin, Alexander the Great, Peter Wittgenstein, Jacques Dugommier

**drop oar**: Nelson A. Miles, Charles X Gustav, Han Xin, Abdul Fatah Younis, Carl Johan Adlercreutz, Dwight D. Eisenhower, Hayreddin Pasha, Edmund Allenby, Manuel Belgrano, Hōjō Ujiyasu, Khalid ibn al-Walid, Samuel Ryan Curtis, José de Urrea, Scipio Africanus, Subutai, Rochejaquelein, Hashiba Hideyoshi, Georgy Zhukov, Oda Nobunaga, Alexander the Great

**drop war_residual**: Dwight D. Eisenhower, Khalid ibn al-Walid, Edmund Allenby, Charles X Gustav, Nelson A. Miles, Hōjō Ujiyasu, Oda Nobunaga, Samuel Ryan Curtis, Abdul Fatah Younis, Han Xin, Hashiba Hideyoshi, José de Urrea, Hayreddin Pasha, Manuel Belgrano, Peter Wittgenstein, Alexander the Great, Rochejaquelein, Carl Johan Adlercreutz, Georgy Zhukov, Charles XII

**drop decisiveness**: Charles X Gustav, Edmund Allenby, Khalid ibn al-Walid, Samuel Ryan Curtis, Douglas MacArthur, Alexander the Great, Carl Johan Adlercreutz, José de Urrea, Peter Wittgenstein, Dwight D. Eisenhower, Charles XII, Bernard Montgomery, Hōjō Ujiyasu, Claude de Villars, Duke of Alba, Alexander I, Jean Houchard, Napoleon I, Pietro Badoglio, Lucius Cornelius Sulla

**drop longevity**: Hōjō Ujiyasu, Dwight D. Eisenhower, Nelson A. Miles, Douglas MacArthur, Claude de Villars, Duke of Alba, Hashiba Hideyoshi, Alexander I, Charles XII, Hayreddin Pasha, Han Xin, Subutai, Bernard Montgomery, Oda Nobunaga, Georgy Zhukov, Scipio Africanus, Alexander the Great, Peter Wittgenstein, Joseph Souham, Edmund Allenby

**equal weights**: Nelson A. Miles, Charles X Gustav, Dwight D. Eisenhower, Han Xin, Edmund Allenby, Abdul Fatah Younis, Khalid ibn al-Walid, Hōjō Ujiyasu, Manuel Belgrano, Hayreddin Pasha, Samuel Ryan Curtis, Carl Johan Adlercreutz, Oda Nobunaga, José de Urrea, Hashiba Hideyoshi, Rochejaquelein, Georgy Zhukov, Subutai, Peter Wittgenstein, Scipio Africanus

**min battles >= 1**: Dwight D. Eisenhower, Charles X Gustav, Hōjō Ujiyasu, Edmund Allenby, Nelson A. Miles, Khalid ibn al-Walid, Samuel Ryan Curtis, Han Xin, Douglas MacArthur, Carl Johan Adlercreutz, José de Urrea, Alexander the Great, Abdul Fatah Younis, Peter Wittgenstein, Charles XII, Hashiba Hideyoshi, Scipio Africanus, Bernard Montgomery, Oda Nobunaga, Claude de Villars

**min battles >= 3**: Dwight D. Eisenhower, Charles X Gustav, Hōjō Ujiyasu, Edmund Allenby, Khalid ibn al-Walid, Samuel Ryan Curtis, Han Xin, Douglas MacArthur, Carl Johan Adlercreutz, José de Urrea, Alexander the Great, Abdul Fatah Younis, Peter Wittgenstein, Charles XII, Hashiba Hideyoshi, Scipio Africanus, Bernard Montgomery, Oda Nobunaga, Claude de Villars, Duke of Alba

**min battles >= 5**: Dwight D. Eisenhower, Charles X Gustav, Hōjō Ujiyasu, Edmund Allenby, Khalid ibn al-Walid, Douglas MacArthur, Carl Johan Adlercreutz, Alexander the Great, Abdul Fatah Younis, Peter Wittgenstein, Charles XII, Hashiba Hideyoshi, Scipio Africanus, Oda Nobunaga, Duke of Alba, Georgy Zhukov, Subutai, Napoleon I, Lucius Cornelius Sulla, Rochejaquelein

**min battles >= 10**: Edmund Allenby, Khalid ibn al-Walid, Alexander the Great, Charles XII, Oda Nobunaga, Napoleon I, Ulysses S. Grant, Jean Moreau, Hugh Gough, Alexander Suvorov, Takeda Shingen, Douglas Haig, Frederick the Great, Julius Caesar, Nader, Arthur Wellesley, Maurice of Nassau, Hannibal, Mustafa Kemal, Col

**min battles >= 20**: Khalid ibn al-Walid, Napoleon I, Takeda Shingen, Arthur Wellesley, Maurice of Nassau, Hannibal, Archduke Charles

**decisiveness shrunk toward 0.5 (pseudo_count=5)**: Dwight D. Eisenhower, Charles X Gustav, Khalid ibn al-Walid, Edmund Allenby, Samuel Ryan Curtis, Carl Johan Adlercreutz, Peter Wittgenstein, Hōjō Ujiyasu, Douglas MacArthur, José de Urrea, Han Xin, Alexander the Great, Alexander I, Subutai, Bernard Montgomery, Claude de Villars, Jean Houchard, Abdul Fatah Younis, Duke of Alba, Nelson A. Miles

## Answer: which component is overrated and which is underrated?

Dropping each component from the default weights moves mean reference-source Spearman by: OAR +0.026, WAR-residual -0.022, decisiveness -0.026, longevity -0.007 (baseline mean +0.443). A positive delta means the ranking agrees with the published lists *more* once that component is removed -- i.e. that component is currently overrated relative to its weight; a negative delta means removing it hurts agreement, i.e. it is underrated or at least correctly weighted. Each component alone (no other input) moves mean correlation by: OAR -0.088, WAR-residual +0.014, decisiveness -0.614, longevity -0.190, showing how much reference agreement each input can explain in isolation. Equal weights (0.25 each, versus the default 0.35/0.35/0.15/0.15) moves mean correlation by -0.013 -- this reweighting does not help agreement with the published lists. Shrinking decisiveness toward the 0.5 prior (pseudo_count=5) moves mean correlation by +0.032 relative to the default-weighted baseline.

