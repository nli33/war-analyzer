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
- [x] Napoleon Bonaparte battles — 14 rows (Montenotte, Lodi, Arcole, Rivoli, Pyramids, Marengo,
      Austerlitz, Jena, Friedland, Eylau, Wagram, Borodino, Leipzig, Waterloo) in `data/battles.csv`
      plus a `generals.csv` row; `era=Napoleonic`, `source_confidence=Medium` (matching Frederick),
      downgraded to `Low` for two rows (Eylau, Borodino) whose own-side casualty figures disagree by
      nearly 2x across historians. Web-researched per-battle via a delegated research pass
      cross-checking Wikipedia infoboxes against standard references (Chandler, Digby Smith,
      Esposito & Elting). Deviation/judgment call: `tech_era_tier=4`, one above Frederick's 3 to
      keep the tier sequence monotonic with era order, even though Napoleonic weapons/logistics/
      comms technology (flintlock muskets, smoothbore cannon, no rail/telegraph) is arguably
      identical to Frederick's era on the schema's own axis — the real Napoleonic innovation was
      organizational (corps system), not covered by this field; full reasoning in `generals.csv`'s
      note in case Phase 7's sanity pass questions the tier gap. `resource_backing_tier` set per-row
      (2 during the resource-starved Italian/Egyptian campaigns, rising to 5 at the imperial peak,
      falling back to 2 by Leipzig and 1 for the isolated Hundred Days army at Waterloo), same
      per-row approach as Frederick. The Jena row covers only Napoleon's own engagement against
      Hohenlohe, excluding the simultaneous Davout-commanded Battle of Auerstedt — same
      personal-command bar as Genghis/Saladin/Frederick's Kesselsdorf exclusion. Borodino is
      recorded as a Win (French held the field) but with `decisiveness=Pyrrhic` and
      `objective_secured=false`, since the Russian army escaped intact and the campaign ended in
      disaster — the clearest tactical-win-no-strategic-payoff case in the dataset so far. Net
      record is 11 wins / 2 losses (both Rout: Leipzig, Waterloo) / 1 Draw (Eylau, held over French
      claims of victory, same treatment as Frederick's Zorndorf). `python scripts/validate_data.py`
      passes; full test suite (32 tests) still green.
- [x] Ulysses S. Grant battles — 15 rows (Belmont, Fort Henry, Fort Donelson, Shiloh, Champion Hill,
      Siege of Vicksburg, Chattanooga/Missionary Ridge, the Wilderness, Spotsylvania Court House, Cold
      Harbor, and four separately-documented phases of the Siege of Petersburg: Second Battle of
      Petersburg, the Crater, Globe Tavern, Third Battle of Petersburg, plus Appomattox Court House) in
      `data/battles.csv` plus a `generals.csv` row; `era=Industrial`, `source_confidence` mixed
      High/Medium/Low per-row reflecting real, well-documented cross-source (Wikipedia vs. American
      Battlefield Trust) disagreement on several 1863-64 troop-strength figures (e.g. Spotsylvania and
      Cold Harbor differ 40,000-55,000+ between sources, most likely ABT citing total army strength vs.
      troops actually engaged). Web-researched via a delegated research pass across Wikipedia infoboxes
      and American Battlefield Trust, cross-checked with follow-up searches for figures the first pass
      didn't cover (the four Petersburg-siege phase battles' troop strengths). Deviation/judgment call:
      `tech_era_tier=4`, the same tier as Napoleon rather than a new value, since the schema's 1-5 scale
      cannot give a distinct tier to all 6 ERAS and its own tier-5 definition ("mechanised warfare with
      radio and rail") is a closer match to the still-to-come WWII general than to the Civil War (rail
      and telegraph, but no radio/mechanization) — full reasoning in `generals.csv`'s note in case Phase
      7's sanity pass questions the flat tier. `resource_backing_tier` set per-row, rising from 2 at
      Belmont (1861) to 5 from the 1864 Overland Campaign onward as Union industrial mobilization
      matured, matching the per-row approach used for Frederick and Napoleon. Excludes four Vicksburg-
      campaign battles (Port Gibson, Raymond, Jackson, Big Black River Bridge) fought primarily by
      subordinate corps commanders, and the Battle of Corinth (Grant not present) — same personal-
      command bar as prior generals' exclusions. The 1864 Overland Campaign battles (Wilderness,
      Spotsylvania, Cold Harbor) and the Petersburg-siege rows are treated as Grant's own despite George
      Meade holding the Army of the Potomac's formal tactical command, since Grant as general-in-chief
      personally directed overall strategy — the same "personally supreme-commanded" standard already
      used for Genghis Khan and Saladin, documented here since it's a closer call than most of this
      dataset's command-attribution decisions. Fort Henry is flagged (not excluded) as fought mostly by
      the Navy with minimal infantry combat, since Grant was present and in overall command throughout.
      Net record is 9 wins (4 Rout-level: Fort Donelson, Vicksburg, Chattanooga, Appomattox) / 3 losses
      (Cold Harbor, Second Petersburg, the Crater — none Rout-level, Grant's own army was checked but
      never broke) / 3 draws (Belmont, the Wilderness, Spotsylvania). `python scripts/validate_data.py`
      passes; full test suite (32 tests) still green.
- [x] Georgy Zhukov battles — 6 rows (Battle of Khalkhin Gol, Yelnya Offensive, Battle of Moscow,
      Operation Mars, Vistula-Oder Offensive, Battle of Seelow Heights) in `data/battles.csv` plus a
      `generals.csv` row; `era=WWII`, `tech_era_tier=5` for every row (first general in the dataset to
      reach the schema's top tier — mechanised warfare with radio and rail — a deliberate step up from
      Napoleon/Grant's tier 4, reasoning in `generals.csv`'s note). Web-researched via a delegated
      research pass plus several of my own follow-up searches for gaps it flagged, cross-checking
      Wikipedia infoboxes against Glantz & House, Krivosheev, Beevor, Hastings, and Isaev.
      Deviation/judgment call, the big one for this general: applied the existing "personally
      supreme-commanded" bar (used for Genghis/Saladin/Frederick/Grant) strictly, which excludes the
      Battle of Stalingrad, the Battle of Kursk, and Operation Bagration — Zhukov coordinated these as
      a Stavka representative/Deputy Supreme Commander while named front commanders (Yeremenko/
      Rokossovsky/Vatutin at Stalingrad and Kursk; Rokossovsky at 1st Belorussian Front for all of
      Bagration) held direct command. This is a materially stricter cut than any prior general's roster
      and drops three of Zhukov's most famous battles. Also excluded, for the opposite reason (no
      fabrication, same bar as Alexander's Persian Gate/Genghis's Khalakhaljid Sands): the Leningrad
      Front command (Sept-Oct 1941, a genuine personal command but the single worst-sourced gap in the
      whole dataset — no quantifiable troop or casualty figure found for that specific five-week window
      despite a dedicated search) and the First Rzhev-Vyazma Offensive (Jan-Apr 1942, personally
      commanded, but no German-side troop-strength or casualty figure isolated to that specific
      operation as opposed to the broader multi-year Rzhev campaign total). The Battle of Berlin
      (April-May 1945 city assault) is excluded as a separate row from Seelow Heights specifically to
      avoid double-counting: Seelow was the opening battle of the same operation on Zhukov's own front,
      and Berlin's only available figures are an undifferentiated three-marshal (Zhukov+Konev+
      Rokossovsky) combined total for the same window — unlike Alesia/Vistula-Oder's "combine
      multi-force figures into one field and document it" treatment, this is a direct overlap with an
      already-included row. Net result is 6 rows (5 wins, 2 Rout-level: Khalkhin Gol, Vistula-Oder;
      1 loss: Operation Mars, well-documented via Glantz's "Zhukov's Greatest Defeat") — smaller than
      every other general in this roster (range 8-15), a structural consequence of the Red Army's
      Stavka system putting multiple named front commanders under one coordinating deputy for exactly
      the largest, best-quantified operations, not a research shortfall; full reasoning in
      `generals.csv`'s note in case Phase 7's sanity pass questions the thin roster. Operation Mars's
      own_casualties uses Glantz's revised 335,000 over the official Krivosheev figure of 215,674 (a
      ~55% gap, the most contested figure in this dataset), following the same "prefer the modern
      historian's corrective over the self-serving/official lower figure" precedent already used for
      Caesar and Genghis Khan. `python scripts/validate_data.py` passes; full test suite (32 tests)
      still green.

## Phase 3: Metrics pipeline
- [x] Raw/counting stats — `war/records.py` adds typed `Battle`/`General` dataclasses plus
      `load_battles`/`load_generals` (the CSV-loading layer every metrics module from here on
      builds on; validation stays a separate pre-check in `scripts/validate_data.py`, loading
      does not re-validate). `war/metrics/raw.py` adds `raw_stats_by_general`, rolling up
      `battles_commanded`, `wins`/`losses`/`draws`, `total_own_troops` (career volume),
      `total_enemy_casualties_inflicted`, `total_own_casualties_taken` per general. Deviation:
      PLAN.md Section 4 lists "battles commanded" and "campaigns commanded" as two separate
      counts, but PLAN.md Section 1 defines this project's atomic unit as "individual
      battle/campaign commanded" — one row is a battle *or* a campaign, never both distinctly —
      so the two counts are always identical; only `battles_commanded` is exposed rather than a
      duplicate field under a second name. Verified per SCOPE.md Phase 3 method: hand-computed
      expected values on synthetic battle sets in `tests/test_metrics_raw.py` (4 new tests), plus
      a manual run against the real 83-row dataset to eyeball the per-general totals look
      sane (e.g. Zhukov's ~2.07M own-casualties total is dominated by Battle of Moscow's
      1,029,234 row — checked against the CSV directly, not a rollup bug). Full suite: 36/36
      passing (32 prior + 4 new).
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
