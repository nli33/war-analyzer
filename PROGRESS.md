# Progress

## Phase 1: Scaffold
- [x] Repo structure + CSV schema matching PLAN.md Section 2 — `war/schema.py` is the authoritative definition; `data/battles.csv` and `data/generals.csv` written with headers generated from it
- [x] pytest harness runs (0 tests is fine at this point) — `pyproject.toml` configures pytest (repo root on `pythonpath`, doctests collected from `war/`); `tests/test_schema.py` holds 16 scaffold checks, 17 passing with the `parse_year` doctest

## Phase 2: Data curation (8 generals, see SCOPE.md roster)
- [x] Data validation script (required fields, valid enums, non-negative numerics, citation present) — `war/validate.py` walks every row against the `Column` specs already in `war/schema.py` (so "valid enums"/"non-negative numerics" fall out of the existing `choices`/`min_value` metadata for free) plus two invariants the schema docstrings claim but a single column can't check alone: `battle_id`/`general_id` uniqueness and that every battle's `general_id` exists in `generals.csv`. `scripts/validate_data.py` is the CLI entry (`python scripts/validate_data.py`, exit 0/1). Verified: 12 new tests in `tests/test_validate.py` (per-column checks + whole-file checks on synthetic tmp CSVs) plus a check that the current header-only `data/*.csv` validates clean — 32/32 tests pass.
- [x] Julius Caesar battles — 11 rows (Bibracte, Sabis, Gergovia, Alesia, Ilerda, Dyrrhachium,
      Pharsalus, Zela, Ruspina, Thapsus, Munda) in `data/battles.csv` plus a `generals.csv` row;
      all tagged `source_confidence=Low` per the ancient-sourcing caveat. `tech_era_tier=1` for
      every Ancient-era row (a convention to hold consistent across Caesar and Alexander).
      Web-researched per-battle to cross-check Caesar's own *Commentarii* figures against modern
      historian estimates (Delbrück-range); several rows deviate materially from Caesar's own
      numbers (e.g. Bibracte enemy dead, Pharsalus own casualties) with the discrepancy and the
      chosen modern estimate recorded in each row's `notes`. Alesia's `enemy_troop_strength`
      combines the besieged garrison and relief army (documented in its notes) since the schema
      has one enemy-strength field per row. `python scripts/validate_data.py` passes; full test
      suite (32 tests) still green.
- [x] Alexander the Great battles — 9 rows (Granicus, Halicarnassus, Issus, Tyre, Gaza,
      Gaugamela, Cyropolis, Jaxartes, Hydaspes) in `data/battles.csv` plus a `generals.csv` row;
      all `source_confidence=Low`, `tech_era_tier=1`, web-researched per-battle against modern
      estimates the same way as the Caesar rows. Deviation: dropped the Battle of the Persian
      Gate (330 BC) after research turned up no casualty figure at all for either side, not even
      a disputed one (Wikipedia itself says "unknown, but moderate to heavy") — every numeric
      field is required by the schema, so a battle with no attested number doesn't get a row
      rather than a fabricated one. Every row is a Win: Alexander is universally regarded as
      undefeated in pitched battle, unlike Caesar's mixed record, so that's a legitimate feature
      of the data, not a coverage gap. Gaza's own_casualties (10,000, from Wikipedia's infobox)
      is flagged as unusually high with no primary-source breakdown found, rather than silently
      accepted or silently replaced with an uncited "corrected" figure. `python
      scripts/validate_data.py` passes; full test suite (32 tests) still green.
- [x] Genghis Khan battles — 8 rows (Chakirmaut, Siege of Zhongxing, Yehuling, Siege of Otrar,
      Siege of Bukhara, Siege of Samarkand, Battle of the Indus, Battle of the Yellow River) in
      `data/battles.csv` plus a `generals.csv` row; `era=Medieval`, `source_confidence=Low`,
      `tech_era_tier=2` for every row (one tier above the Ancient generals' tier 1 — stirrup
      cavalry and siege engineering, still pre-gunpowder — fixed now so it stays comparable with
      Saladin, the next Medieval general). Dropped Thirteen Sides/Koyiten (1201), Khalakhaljid
      Sands (1203, Genghis's one clear personal defeat), and the 1213-1215 Siege of Zhongdu for
      having no troop/casualty figures in any source, same no-fabrication bar as Alexander's
      Persian Gate; also excluded battles led by subordinates without Genghis personally
      present/directing (Irtysh River, Parwan, the 1221 sieges of Merv/Nishapur/Gurganj).
      Deviation/judgment call: unlike the Roman/Greek sources behind the Caesar/Alexander rows,
      Mongol-era sources (Secret History, Juvaini, Rashid al-Din, Yuan Shi) essentially never
      quantify Mongol-side losses at all, even qualitatively, for several of these battles
      (Bukhara, Samarkand, Indus, Yellow River). Rather than dropping otherwise well-documented,
      historically pivotal sieges over one unattested field, `own_casualties` in those rows is an
      explicitly-flagged order-of-magnitude placeholder (not a source-derived figure) — a
      materially weaker standard than the rest of the dataset, but the alternative (cutting
      Bukhara/Samarkand/Indus) would have lost more real signal than it preserved integrity;
      every affected row's `notes` and the `generals.csv` note call this out by name so it reads
      honestly rather than as false precision, and Phase 4's Monte Carlo resampling is exactly
      the mechanism built to absorb this kind of soft figure. `python scripts/validate_data.py`
      passes; full test suite (32 tests) still green.
- [x] Saladin battles — 8 rows (Horns of Hama, Montgisard, Hattin, Siege of Jerusalem, Siege of
      Tyre, Siege of Acre, Arsuf, Jaffa) in `data/battles.csv` plus a `generals.csv` row;
      `era=Medieval`, `source_confidence=Low`, `tech_era_tier=2` (matching Genghis Khan, the other
      Medieval-era general). Web-researched per-battle the same way as the other three generals so
      far. Deviation/judgment call: dropped five candidate battles (Battle of Hama 1178, Marj Ayyun
      1179, the Siege of Jacob's Ford 1179, al-Fule 1183, Belvoir/Le Forbelet 1182) for having no
      quantifiable troop-strength or casualty figure for Saladin's own side in any source found —
      same no-fabrication bar as Alexander's Persian Gate and Genghis's Khalakhaljid Sands. Also
      dropped the 1167 Battle of al-Babein since Shirkuh, not Saladin, held overall command there
      (Saladin was his senior lieutenant) — same "personally/supreme commanded" bar used to exclude
      subordinate-led battles from Genghis's roster. Three rows (Horns of Hama, Siege of Jerusalem,
      Siege of Tyre) have only qualitative casualty language ("minimal", "light"/"heavy") rather
      than a source-given count and use flagged order-of-magnitude placeholders, per the precedent
      set by several Genghis rows. Two multi-year/multi-force sieges (Siege of Acre combining
      Saladin's relief army with the besieged garrison, matching how Caesar's Alesia combines
      garrison and relief force) needed a chronicle-inflated figure rejected in favor of a more
      conservative modern-plausible estimate (Acre's "up to 60,000" Ayyubid losses; Arsuf's
      chronicle claim of 7,000+ dead, itself hedged by the source as possibly too high) — same
      treatment as Genghis's rejection of Juvaini's inflated Samarkand death toll. Net record is 3
      wins / 5 losses, all 5 losses in the back half of the career (Montgisard 1177, then every
      Third Crusade battle against Richard I from 1189 on) — this matches historian consensus that
      Saladin was Richard's tactical inferior in the field even while winning the war for
      Jerusalem, not a data-entry red flag; noted here in case Phase 7's sanity pass flags the
      losing streak as suspicious. `python scripts/validate_data.py` passes; full test suite (32
      tests) still green.
- [x] Frederick the Great battles — 12 rows (Mollwitz, Chotusitz, Hohenfriedberg, Soor, Lobositz,
      Prague, Kolin, Rossbach, Leuthen, Zorndorf, Kunersdorf, Torgau) in `data/battles.csv` plus a
      `generals.csv` row; `era=Early Modern`, `tech_era_tier=3` (one above the Medieval generals'
      tier 2 — linear gunpowder warfare, still pre-industrial logistics). Deviation:
      `source_confidence=Medium` rather than the ancient/medieval rosters' `Low` — 18th-century
      Prussian/Austrian muster-roll figures are meaningfully better corroborated across sources,
      though real disagreement of a few thousand troops still turns up per battle (e.g. Mollwitz's
      Prussian strength is quoted 16,000-23,000), so `High` isn't claimed either. `resource_backing_tier`
      is set per-row rather than fixed for the whole career (3 during the Silesian Wars, dropping to
      2 then 1 as the Seven Years' War coalition and Prussia's manpower/treasury crisis deepen) —
      reasoning recorded in `generals.csv`'s note. Excluded Kesselsdorf (1745) since it was fought
      and won by Leopold I of Anhalt-Dessau while Frederick's own army was elsewhere, same
      personal-command bar used for Genghis Khan and Saladin. Net record is 9 wins (2 Rout-level:
      Rossbach, Leuthen; 2 Pyrrhic: Prague, Torgau) / 2 losses (Kolin, and Kunersdorf — his one
      Rout-level defeat, the only Loss-with-Rout in the dataset so far) / 1 Draw (Zorndorf, held
      per modern historiography over 18th-century Prussian claims of outright victory). `python
      scripts/validate_data.py` passes; full test suite (32 tests) still green.
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
