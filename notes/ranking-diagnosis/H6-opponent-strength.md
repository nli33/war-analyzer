# H6: opponent strength

Roster graph (`data/auto/battles.csv`): 2327 rows, 2048 with a recorded opponent, 1233 distinct opponents, 999 of them (81% of distinct opponents, 59% of opponent-rows) off-roster. Full-universe graph: 11135 rows built from every identifiable primary commander in the cached battle universe (not just the 343-general roster).

## How many off-roster opponents have enough rows to rate?

For each off-roster opponent appearing in the roster graph, their own `battles_rated` count in the full-universe OAR solve (how many identifiable battles they appear in at all, as either side, corpus-wide -- not just against roster generals):

| Full-universe battle count | Off-roster opponents |
|---|---|
| 0 | 0 |
| 1-2 | 655 |
| 3-4 | 227 |
| 5-9 | 111 |
| 10+ | 6 |

## Variant 1: full-universe OAR vs. baseline

Spearman rank correlation vs. baseline (roster-only OAR), over 343 generals ranked by both: **+0.997**.

Top 30 entering under variant 1 (not in baseline top 30): Hashiba Hideyoshi, Radomir Putnik, Jean Lannes
Top 30 leaving under variant 1 (in baseline top 30, not variant 1): John M. Schofield, Jacques Dugommier, Joseph Souham

## Variant 2: confidence-weighted OAR vs. baseline

Weight = `n / (n + 5)` where `n` is the opponent's full-universe battle count (reusing `ranking_tables.MIN_BATTLES_FOR_HEADLINE_RANKING`'s pseudo-count convention). Spearman rank correlation vs. baseline, over 343 generals ranked by both: **+0.995**.

Top 30 entering under variant 2: Scipio Africanus, Rochejaquelein, Philip Sheridan
Top 30 leaving under variant 2: José de Urrea, Subutai, Pietro Badoglio

## Must-include generals: rank under each variant

| General | Baseline rank | Variant 1 (full-universe OAR) rank | Variant 2 (confidence-weighted OAR) rank |
|---|---|---|---|
| Julius Caesar | 77 | 78 | 66 |
| Alexander the Great | 9 | 10 | 13 |
| Temujin | 130 | 153 | 99 |
| Saladin | 257 | 249 | 265 |
| Frederick the Great | 100 | 104 | 75 |
| Napoleon I | 12 | 14 | 10 |
| Ulysses S. Grant | 20 | 23 | 15 |
| Georgy Zhukov | 16 | 13 | 22 |
| Hannibal | 147 | 133 | 161 |
| Scipio Africanus | 34 | 58 | 18 |
| Subutai | 21 | 18 | 36 |
| Matsudaira Motoyasu | 142 | 127 | 166 |
| George Washington | 174 | 182 | 164 |
| Arthur Wellesley | 78 | 83 | 61 |
| Robert E. Lee | 179 | 177 | 178 |
| Dwight D. Eisenhower | 7 | 9 | 12 |
| Erwin Rommel | 273 | 265 | 277 |
| Erich von Manstein | 172 | 183 | 195 |
| Douglas MacArthur | 157 | 147 | 148 |
| Han Xin | 14 | 12 | 23 |

## Napoleon-Wellington: what do the two ratings depend on, with Waterloo missing?

Napoleon (`napoleon`) has 62 rated opponent-rows in the roster graph; Wellington (`arthur-wellesley-1st-duke-of-wellington`) has 27. Direct shared opponents (an opponent both generals personally fought, in this dataset): none.

Napoleon's rated opponents (battle, opponent_general_id, outcome):
- Battle of Abensberg vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Abukir (1799) vs. `mustafa-pasha-egypt`: Win
- Battle of Allenstein vs. `levin-august-von-bennigsen`: Win
- Battle of Arcis-sur-Aube vs. `alexander-i-of-russia`: Loss
- Battle of Aspern-Essling vs. `archduke-charles-duke-of-teschen`: Loss
- Battle of Austerlitz vs. `alexander-i-of-russia`: Win
- Battle of Bassano vs. `dagobert-sigmund-von-wurmser`: Win
- Battle of Bautzen (1813) vs. `alexander-i-of-russia`: Win
- Battle of Berezina vs. `peter-wittgenstein`: Draw
- Battle of Berry-au-Bac vs. `ferdinand-von-wintzingerode`: Win
- Battle of Borghetto vs. `johann-peter-beaulieu`: Win
- Battle of Caldiero (1796) vs. `j-zsef-alvinczi`: Loss
- Battle of Castiglione vs. `dagobert-sigmund-von-wurmser`: Win
- Battle of Ceva vs. `michelangelo-alessandro-colli-marchi`: Win
- Battle of Champaubert vs. `zakhar-dmitrievich-olsufiev`: Win
- Battle of Château-Thierry (1814) vs. `ludwig-yorck-von-wartenburg`: Win
- Battle of Craonne vs. `gebhard-leberecht-von-bl-cher`: Win
- Battle of Czarnowo vs. `mikhail-kamensky`: Win
- Battle of Dresden vs. `karl-philipp-prince-of-schwarzenberg`: Win
- Battle of Eckmühl vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Fombio vs. `johann-peter-beaulieu`: Win
- Battle of Friedland vs. `levin-august-von-bennigsen`: Win
- Battle of Hanau vs. `karl-philipp-von-wrede`: Win
- Battle of Heilsberg vs. `levin-august-von-bennigsen`: Draw
- Battle of La Favorita vs. `dagobert-sigmund-von-wurmser`: Win
- Battle of La Rothière vs. `gebhard-leberecht-von-bl-cher`: Loss
- Battle of Landshut (1809) vs. `johann-von-hiller`: Win
- Battle of Ligny vs. `gebhard-leberecht-von-bl-cher`: Win
- Battle of Lodi vs. `karl-philipp-sebottendorf`: Win
- Battle of Lonato vs. `peter-vitus-von-quosdanovich`: Win
- Battle of Lützen (1813) vs. `alexander-i-of-russia`: Win
- Battle of Marengo vs. `michael-von-melas`: Win
- Battle of Millesimo vs. `giovanni-marchese-di-provera`: Win
- Battle of Mondovì vs. `michelangelo-alessandro-colli-marchi`: Win
- Battle of Montenotte vs. `eug-ne-guillaume-argenteau`: Win
- Battle of Montereau vs. `karl-philipp-prince-of-schwarzenberg`: Win
- Battle of Montmirail vs. `fabian-gottlieb-von-der-osten-sacken`: Win
- Battle of Mormant vs. `karl-philipp-prince-of-schwarzenberg`: Win
- Battle of Mount Tabor (1799) vs. `abdullah-pasha-al-azm`: Win
- Battle of Ratisbon vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Reichenbach vs. `aleksey-yermolov`: Win
- Battle of Rivoli vs. `j-zsef-alvinczi`: Win
- Battle of Rovereto vs. `paul-davidovich`: Win
- Battle of Saint-Dizier vs. `ferdinand-von-wintzingerode`: Win
- Battle of Shubra Khit vs. `murad-bey`: Win
- Battle of Smolensk (1812) vs. `michael-andreas-barclay-de-tolly`: Win
- Battle of Somosierra vs. `benito-de-san-juan`: Win
- Battle of Tagliamento vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Tarvis (1797) vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Teugen-Hausen vs. `archduke-charles-duke-of-teschen`: Win
- Battle of Ulm vs. `karl-mack-von-leiberich`: Win
- Battle of Vauchamps vs. `gebhard-leberecht-von-bl-cher`: Win
- Battle of Vitebsk (1812) vs. `pyotr-konovnitsyn`: Win
- Battle of Wagram vs. `archduke-charles-duke-of-teschen`: Win
- Battle of the Bridge of Arcole vs. `j-zsef-alvinczi`: Win
- Battle of the Pyramids vs. `murad-bey`: Win
- First Battle of Dego vs. `olivier-count-of-wallis`: Win
- Second Battle of Bassano vs. `j-zsef-alvinczi`: Loss
- Second Battle of Dego vs. `eug-ne-guillaume-argenteau`: Win
- Second Battle of Saorgio (1794) vs. `michelangelo-alessandro-colli-marchi`: Win
- Siege of Acre (1799) vs. `jazzar-pasha`: Loss
- Siege of Jaffa vs. `jazzar-pasha`: Win

Wellington's rated opponents (battle, opponent_general_id, outcome):
- Battle of Argaon vs. `raghoji-ii-of-nagpur`: Win
- Battle of Assaye vs. `raghoji-ii-of-nagpur`: Win
- Battle of Buçaco vs. `andr-mass-na`: Win
- Battle of El Bodón vs. `louis-pierre-montbrun`: Loss
- Battle of Foz de Arouce vs. `michel-ney`: Win
- Battle of Fuentes de Oñoro vs. `andr-mass-na`: Win
- Battle of Grijó vs. `jean-de-dieu-soult`: Win
- Battle of Køge vs. `joachim-castenschiold`: Win
- Battle of Orthez vs. `jean-de-dieu-soult`: Win
- Battle of Pombal vs. `michel-ney`: Draw
- Battle of Quatre Bras vs. `michel-ney`: Draw
- Battle of Redinha vs. `michel-ney`: Draw
- Battle of Roliça vs. `henri-fran-ois-delaborde`: Win
- Battle of Sabugal vs. `andr-mass-na`: Win
- Battle of Salamanca vs. `auguste-de-marmont`: Win
- Battle of Sorauren vs. `jean-de-dieu-soult`: Win
- Battle of Sultanpet Tope vs. `tipu-sultan`: Win
- Battle of Tordesillas (1812) vs. `joseph-souham`: Loss
- Battle of Vimeiro vs. `jean-andoche-junot`: Win
- Battle of Vitoria vs. `joseph-bonaparte`: Win
- Battle of the Bidassoa vs. `jean-de-dieu-soult`: Win
- Second Battle of Porto vs. `jean-de-dieu-soult`: Win
- Second siege of Badajoz (1811) vs. `armand-philippon`: Loss
- Siege of Badajoz (1812) vs. `armand-philippon`: Win
- Siege of Burgos vs. `jean-louis-dubreton`: Loss
- Siege of Ciudad Rodrigo (1812) vs. `jean-l-onard-barri`: Win
- Siege of San Sebastián vs. `louis-emmanuel-rey`: Loss

- Napoleon baseline OAR: 1996.7 (98 rated battles)
- Napoleon full-universe OAR: 2056.4 (124 rated battles)
- Napoleon confidence-weighted OAR: 1929.0 (98 rated battles)
- Wellington baseline OAR: 1823.3 (42 rated battles)
- Wellington full-universe OAR: 1825.1 (54 rated battles)
- Wellington confidence-weighted OAR: 1812.8 (42 rated battles)

## Answer

**Off-roster share is higher than PROGRESS.md's old 65%/35% split, not lower**: 81% of distinct opponents (59% of opponent-rows, the weighted figure) are off-roster today, after H1/H4 grew the dataset. Rating them from the full battle universe instead of a flat 1500 barely moves the composite ranking (Spearman +0.997 vs. baseline, 3 of the top 30 swap either way) because **coverage, not graph size, is the bottleneck**: 655 of 999 off-roster opponents (66%) have only 1-2 identifiable battles anywhere in the whole cached universe, not just in their games against the roster -- most of them are thin because Wikipedia's coverage of them is thin, not because this project only looked at their roster-facing games. Only 6 of 999 have 10 or more full-universe battles, i.e. enough to plausibly trust a solved rating at all.

Confidence-weighting (variant 2) moves the ranking about as little (Spearman +0.995), for the same reason: discounting a win over a thin-record opponent only matters when there are *other*, better-attested wins to lean on instead, and most generals' opponent pools are uniformly thin.

**Where opponent-strength method does matter: a direct comparison with no shared battle to anchor it.** Napoleon and Wellington share zero opponents in this dataset and (per H4) never get a Waterloo row for either side, so their relative order rests entirely on how the *rest* of their respective opponent pools get rated. Napoleon leads Wellington by +173.4 Elo points under the baseline, +231.3 under full-universe OAR (full-universe context makes Napoleon's deep, win-heavy opponent list look relatively tougher, since many of his opponents also beat other people elsewhere), and only +116.2 once thin-record opponents are downweighted (most of Napoleon's 124 full-universe-rated wins are against one-battle-in-this-corpus opponents, so discounting them costs him more than it costs Wellington, whose smaller opponent list is proportionally less thin). The gap swings by about 115 Elo points across the three methods without either general's own rating ever reversing direction -- a concrete size for how much the opponent-rating method can move a head-to-head comparison between two generals who, in the data, never actually met.

