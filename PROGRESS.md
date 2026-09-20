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
- [x] Rate stats — `war/metrics/rate.py` adds `rate_stats_by_general`, computing PLAN.md
      Section 4's four per-battle stats: `win_rate`, `casualty_exchange_ratio`,
      `avg_force_ratio_faced`, `decisive_win_rate`. Judgment calls (PLAN.md names the four
      stats but not their exact formulas), documented in the module docstring: (1)
      `casualty_exchange_ratio` is enemy:own from **career-total** casualties (sum/sum), not an
      average of each battle's own ratio — avoids one freak-ratio skirmish outweighing a
      100x-larger battle, and avoids a divide-by-zero on any single zero-casualty row; `None`
      when the general's own-casualty total is zero (schema permits `own_casualties=0`, so this
      is a reachable case, not defensive over-engineering). (2) `avg_force_ratio_faced` is the
      mean, per battle, of `enemy_troop_strength / own_troop_strength` — this one *is* a
      per-battle average since it's about the typical fight, not a career total; >1 means
      typically outnumbered. (3) `decisive_win_rate` reuses the existing `objective_secured`
      bool (among wins only) rather than re-deriving "decisive" from the `decisiveness` enum,
      since `objective_secured` is already defined as exactly that question; `None` for a
      general with zero wins. Verified per SCOPE.md Phase 3 method: 8 new hand-computed tests in
      `tests/test_metrics_rate.py` (including one that pins down totals-ratio vs
      average-of-ratios behavior explicitly, and one each for the two `None`-producing edge
      cases). Also ran against the real 83-row dataset as a sanity check (not a substitute for
      the unit tests) — e.g. Zhukov's casualty_exchange_ratio of ~0.22 (worse than 1:1) tracks
      Operation Mars' heavy losses pulling down an otherwise-winning record, Genghis's ~21.6 is
      the highest in the roster and matches the historical reputation. `python
      scripts/validate_data.py` still passes; full suite now 44/44 (36 prior + 8 new).
- [x] OAR (iterative Elo solver) + unit tests — `war/metrics/oar.py` adds `oar_ratings`,
      a synchronous-batch iterative Elo solver over every `general_id`/`opponent_general_id`
      pair in the dataset (standard expected-score formula, Win/Draw/Loss -> 1/0.5/0 actual
      score). Judgment call not specified by PLAN.md: uses a **decaying step size**
      (`k_factor * decay**epoch`) rather than a constant K, because a constant-K iterative
      Elo never reaches a fixed point for a general with a perfect record in this dataset
      (Alexander the Great — every row a Win) or a winless one — the rating gap keeps
      growing without bound each epoch since there's no offsetting loss to balance the
      expected-score math (confirmed by hand-simulating a single repeated one-sided matchup:
      it didn't converge inside 200k epochs at constant K). Decay guarantees the sum of all
      future per-epoch deltas is a bounded geometric series, so the solver always terminates
      at a finite rating; full reasoning in the module docstring. Off-roster opponents (most
      `opponent_general_id` values — see this file's Notes section, decided before this task)
      get a real solved rating alongside the roster, not a fixed default, since they're full
      participants in the same rating graph. Battles with no `opponent_general_id` recorded
      (a handful of multi-faction sieges) are skipped for rating purposes only — they still
      count in raw/rate stats elsewhere. Verified per SCOPE.md Phase 3 method: since Elo
      iteration doesn't reduce to a hand-computable one-line fraction the way the rate stats
      did, `tests/test_metrics_oar.py` (9 new tests) instead pins down the properties the
      docstring claims on small synthetic battle sets — zero-sum conservation across a single
      matchup, winner-up/loser-down direction, equal-and-opposite records converging to equal
      ratings, the core PLAN.md-named property that beating a higher-rated opponent earns
      more than beating an average one, the no-opponent-recorded and off-roster-opponent edge
      cases, and solver determinism. Also ran against the real 83-row dataset as a sanity
      check: ratings roughly track the qualitative reputations already visible in Phase 2's
      win/loss notes (Alexander highest at ~1879, undefeated; Saladin lowest at ~1430, the
      only roster general with a losing stretch against a named opponent, Richard I) — not a
      substitute for the unit tests. `python scripts/validate_data.py` still passes; full
      suite now 53/53 (44 prior + 9 new).
- [x] WAR-residual (regression) + unit tests — `war/metrics/war_residual.py` adds
      `war_residual_by_general`, an OLS fit (`numpy.linalg.lstsq`) of battle outcome
      score (Win/Draw/Loss -> 1.0/0.5/0.0, same mapping `oar.py` already uses) against
      `force_ratio` (enemy/own troop strength), `resource_backing_tier`, and
      `tech_era_tier`, **pooled across every battle in the input** so the fit is a
      shared "expectation given the inputs" baseline, not each general graded against
      their own average. Judgment calls not specified by PLAN.md, documented in the
      module docstring: (1) regression target is outcome score rather than casualty
      ratio — PLAN.md offers both, but casualty ratio is undefined at zero own
      casualties and skew-prone, the same problem already flagged for
      `casualty_exchange_ratio` in `rate.py`; (2) the per-general stat is the **mean**
      residual across that general's battles (a rate stat, like
      `avg_force_ratio_faced`), not a summed total, so battle count alone doesn't move
      it. Verified per SCOPE.md Phase 3 method: `tests/test_metrics_war_residual.py`
      (6 new tests) leans on two facts that make OLS genuinely hand-computable here,
      unlike OAR's iterative solver — when every row shares identical predictors the
      design matrix collapses to the all-ones vector and `predicted = mean(actual)`
      for every row (used for an exact hand-computed case: one general's lone Win
      against seven Losses from two other generals resolves to residual +0.875 for
      the winner and exactly -0.125 for each loser); and OLS-with-intercept always
      makes residuals sum to exactly zero, checked as an invariant on a separately
      varied dataset. Plus a perfect-linear-fit-gives-zero-residual case, and the
      empty-input/general-absent edge cases matching `raw_stats_by_general`'s
      convention. Also ran against the real 83-row dataset as a sanity check (not a
      substitute for the unit tests): Alexander the Great ranks highest (+0.21,
      undefeated) and Saladin lowest (-0.41, the back-half losing streak against
      Richard I already noted in Phase 2), tracking the qualitative picture from the
      Phase 2 notes; the pooled weighted-residual sum is ~0 on real data too. `python
      scripts/validate_data.py` still passes; full suite now 59/59 (53 prior + 6 new).
- [x] Clutch rating + unit tests — `war/metrics/clutch.py` adds
      `clutch_rating_by_general`, PLAN.md's "playing from behind" stat.
      Judgment calls not specified by PLAN.md, documented in the module
      docstring: (1) a battle counts as "playing from behind" if
      `enemy_troop_strength > own_troop_strength` (outnumbered, break-even at
      exactly equal strength does not count) **or**
      `resource_backing_tier <= 2` (bottom two of the schema's 1-5 tiers) —
      the tier is read as an absolute standard rather than relative to the
      opponent, since the schema only records `resource_backing_tier` for
      the roster general's own side, nothing to compare it against
      per-battle; (2) the stat is the **mean outcome score**
      (Win/Draw/Loss -> 1.0/0.5/0.0, same mapping `oar.py`/`war_residual.py`
      use) across only the qualifying battles — raw performance under
      adversity, not a residual-against-expectation (that framing is already
      covered separately by `war_residual.py`); (3) `None` with
      `battles_used=0` for a general with zero qualifying battles, same
      no-data convention as `rate.py`'s `casualty_exchange_ratio`/
      `decisive_win_rate`. Verified per SCOPE.md Phase 3 method: 7 new
      hand-computed tests in `tests/test_metrics_clutch.py` covering the
      outnumbered condition, the equal-strength boundary (not outnumbered),
      the resource-tier condition and its tier-3 boundary (not
      disadvantaged), a mixed-battle mean-of-qualifying-only case, per-general
      separation, and the empty-input edge case. Also ran against the real
      83-row dataset as a sanity check: Alexander/Genghis/Zhukov sit at a
      perfect 1.0 (consistent with their undefeated-or-near-undefeated
      records from Phase 2), Saladin's single qualifying battle is a loss
      (0.0), consistent with the back-half losing streak already noted.
      `python scripts/validate_data.py` still passes; full suite now 66/66
      (59 prior + 7 new).
- [x] Squander index + unit tests — `war/metrics/squander.py` adds
      `squander_index_by_general`, PLAN.md's "brilliant on the field, lost
      the war" stat (rate at which wins fail to convert into
      strategic/political gains). Judgment calls not specified by PLAN.md,
      documented in the module docstring: (1) reuses the existing
      `decisiveness` enum rather than re-deriving conversion from troop/
      casualty numbers, since the enum's own definitions already answer the
      question directly — `Tactical` ("won the field, but it bought no
      lasting strategic gain") and `Pyrrhic` ("nominally the winner, but the
      cost gutted the force") count as squandered; `Strategic` and `Rout`
      count as converted — same reuse-over-re-derive reasoning `rate.py`
      gives for `decisive_win_rate`/`objective_secured`; (2) `decisiveness`
      is schema-required for a Win but `validate.py` only checks the
      column's unconditional `required` flag (`False`, to allow empty on
      Loss/Draw), so a Win with no `decisiveness` recorded is reachable data,
      not hypothetical — such rows are excluded from both numerator and
      denominator rather than assumed either way, with `wins_used` reporting
      the denominator actually used; (3) `None`/`wins_used=0` for a general
      with no decisiveness-labeled wins, same no-data convention as
      `rate.py`/`clutch.py`. Verified per SCOPE.md Phase 3 method: 10 new
      hand-computed tests in `tests/test_metrics_squander.py` covering each
      of the four `decisiveness` values in isolation, Losses/Draws being
      excluded regardless of their `decisiveness`, the unlabeled-Win
      exclusion case, a mixed-wins fraction case, per-general separation, and
      both `None`-producing edge cases (wins but no labels; no wins at all).
      Also ran against the real 83-row dataset as a sanity check (not a
      substitute for the unit tests): Frederick the Great comes out highest
      (0.44 — matches the historical picture of tactically sharp Prussian
      wins that repeatedly failed to end the wars decisively) and Napoleon
      second (0.27), while Caesar/Genghis/Grant/Zhukov sit at 0.0 (their
      decisiveness labels in this dataset are Strategic/Rout only). `python
      scripts/validate_data.py` still passes; full suite now 76/76 (66 prior
      + 10 new).
- [x] Longevity-adjusted value + unit tests — `war/metrics/longevity.py` adds
      `longevity_adjusted_value_by_general`, PLAN.md's "career value normalized
      for years active" stat. Judgment calls not specified by PLAN.md,
      documented in the module docstring: (1) "career value" reuses the
      Win/Draw/Loss -> 1.0/0.5/0.0 outcome-score mapping `oar.py`/
      `war_residual.py`/`clutch.py` already use, summed across a general's
      career; (2) "longevity" is read as calendar years
      (`generals.csv`'s `career_end_year - career_start_year + 1`, inclusive),
      not battle/campaign count — PLAN.md offers both, but campaign count is
      already `raw_stats.battles_commanded` and every existing rate stat
      already normalizes by battle count, so years is the only reading that
      adds a genuinely new axis (and matches PLAN.md's own
      Alexander-vs-Eisenhower, i.e. calendar-time, framing); (3) this is the
      first metric to need both `battles.csv` and `generals.csv` as input,
      since career span lives only in the latter. Verified per SCOPE.md Phase
      3 method: 5 new hand-computed tests in `tests/test_metrics_longevity.py`
      covering a single-battle one-year career, a mixed Win/Draw/Loss sum, an
      explicit case pinning down that equal career value with a shorter span
      scores higher (the "short dominant peak" property PLAN.md names), a
      career spanning the BC/AD boundary to confirm the no-year-zero
      arithmetic from `schema.py`'s docstring holds, and the no-battles
      absent-general edge case. Also ran against the real dataset as a sanity
      check (not a substitute for the unit tests): Grant (5-year career) and
      Alexander (9-year, undefeated) top the list, Genghis Khan and Saladin
      (23- and 20-year careers with comparatively few high-value wins) sit at
      the bottom — matches the intended volume-vs-peak distinction. `python
      scripts/validate_data.py` still passes; full suite now 81/81 (76 prior
      + 5 new).

## Phase 4: Uncertainty
- [x] Monte Carlo resampling (N>=1000) for Low/Medium confidence battles — `war/metrics/uncertainty.py`
      adds `monte_carlo_uncertainty`, resampling every Low/Medium-confidence battle's four numeric
      fields (own/enemy troop strength, own/enemy casualties) each run via an independent
      multiplicative factor (High=0% noise, Medium=±10%, Low=±40% — the two figures approximating
      the real cross-source spreads already logged in Phase 2, e.g. Frederick's Mollwitz vs. Zhukov's
      Operation Mars) and re-running only the metrics whose formulas actually read those fields:
      `raw.py`'s three troop/casualty totals, `rate.py`'s `casualty_exchange_ratio`/
      `avg_force_ratio_faced`, `war_residual.py`'s `war_residual`, and `clutch.py`'s `clutch_rating`.
      Deviation/judgment call: `win_rate`, `decisive_win_rate`, OAR, Squander Index, and
      Longevity-Adjusted Value are deliberately *not* re-run — they're functions of `outcome`/
      `objective_secured`/`decisiveness`/career years, none of which this resampling touches, so
      Monte Carlo-ing them would just reproduce the same point estimate N times. `DEFAULT_N_RUNS=1000`.
      Output is `result[general_id][metric_name] -> MetricDistribution(mean, ci_low, ci_high,
      runs_used)` using the empirical 5th/95th percentile as the 90% interval. Resampled troop-strength
      fields floor at 1 (not the schema's own `min_value=0`) to preserve the never-divide-by-zero
      invariant `rate.py`/`war_residual.py` already rely on; casualties floor at the schema's actual 0.
      Noted in the module docstring: `war_residual` is pooled across every battle passed in (by
      `war_residual.py`'s own design), so it's the one metric here that is not purely general-local —
      resampling another, less-certain general's rows can widen a High-confidence general's own
      war_residual interval too, a faithful re-run of "the full pipeline" rather than a bug.
- [x] Test: High-confidence general has near-zero interval width — `tests/test_metrics_uncertainty.py`,
      an all-High two-battle synthetic general gets exactly zero width on every general-local metric
      across 300 runs.
- [x] Test: Low-confidence general has visibly wider interval — same file, a matched pair of
      otherwise-identical High vs. Low-confidence generals resampled in the same call: the High
      general's `total_own_troops`/`avg_force_ratio_faced` width is exactly 0, the Low general's is
      not. Also sanity-checked against the real 83-row dataset (not a substitute for the unit tests):
      the all-Low generals (Caesar, Alexander) show a visibly wider `avg_force_ratio_faced` 90% band
      (width ~0.62-0.63) than Medium-heavy Frederick (~0.10) or mixed-confidence Grant (~0.07).
      11 new tests total (noise-bound compliance, the troop-strength zero-division floor, the
      never-qualifies-so-stays-None edge case, per-general separation, determinism for a fixed seed,
      the empty-input edge case, and `DEFAULT_N_RUNS >= 1000`). `python scripts/validate_data.py`
      still passes; full suite now 92/92 (81 prior + 11 new).

## Phase 5: Composite ranking
- [x] Configurable weights (single config location) — `war/config.py` adds a frozen
      `CompositeWeights` dataclass (`oar`, `war_residual`, `decisiveness`, `longevity` fields)
      plus `DEFAULT_COMPOSITE_WEIGHTS`, the one place composite-ranking weights live per
      SCOPE.md Phase 5 ("not hardcoded inline"). Judgment calls, documented in the module
      docstring: (1) `decisiveness` maps to `rate.py`'s existing `decisive_win_rate` and
      `longevity` maps to `longevity.py`'s existing `longevity_adjusted_value` — both already
      literal matches for the PLAN.md-named concept, no new metric needed; (2) default weights
      are an even split within two tiers (OAR/WAR-residual at 0.35 each as the two
      opponent/context-adjusted "true skill" estimates, decisiveness/longevity at 0.15 each as
      narrower career-shape slices) rather than a flat 25/25/25/25 — a placeholder to revisit at
      Phase 7's sanity pass, not a historically validated weighting; (3) added `total()`/
      `is_normalized()`/`normalized()` helpers since nothing yet enforces weights sum to 1, and
      the not-yet-built composite-ranking code (next task) will need to decide whether to
      normalize automatically or trust the config as given. This task is config only — no
      composite-ranking computation wired up yet, that's the next unchecked item. Verified: 6 new
      tests in `tests/test_config.py` (default sums to 1, covers all four PLAN.md inputs,
      overridable, `normalized()` rescales correctly, zero-total raises, an unnormalized set
      correctly reports `is_normalized()=False`). `python scripts/validate_data.py` still
      passes; full suite now 98/98 (92 prior + 6 new).
- [x] Composite ranking output — `war/metrics/composite.py` adds `composite_ranking`,
      combining `oar.py`/`war_residual.py`/`rate.py`'s `decisive_win_rate`/`longevity.py` into
      one score-sorted list via `war/config.py`'s `CompositeWeights`. Implements PLAN.md Section
      4's "Era normalization" requirement (z-score each input within era-cohort before combining
      cross-era) — the first module to actually need it, since no earlier metric compares
      generals against each other. Judgment calls, documented in the module docstring: (1)
      population std (`ddof=0`) per era cohort, since a cohort is this roster's full population
      for that era, not a sample; (2) a zero-variance cohort (`std==0`) gets `z=0.0` for every
      member rather than dividing by zero; (3) a general with no wins (`decisive_win_rate=None`)
      is excluded from that one metric's cohort and falls back to `z=0.0`, independent of the
      other three metrics. Deviation/limitation surfaced by running this against the real
      83-row dataset: this run's locked 8-general/one-per-era roster (SCOPE.md) puts 4 of the 8
      generals (Frederick, Napoleon, Grant, Zhukov) alone in their era, so every one of their
      z-scores — and therefore their composite score — is exactly 0.0 by the zero-variance
      convention above; they tie for the middle of the ranking regardless of weights. This is a
      structural consequence of a real-population z-score with n=1, not a bug in the formula, and
      the two-per-era cohorts (Caesar/Alexander, Genghis/Saladin) show the intended behavior
      cleanly (Alexander/Genghis rank 1-2, Caesar/Saladin rank 7-8, matching Phase 2's
      undefeated-vs-losing-streak notes on those four). Flagging for Phase 7's sanity pass rather
      than reweighting or hand-fixing now, per SCOPE.md's "don't hand-tune to force an order."
      Verified per SCOPE.md Phase 3 method (composite ranking has no dedicated Phase 5 method
      beyond "changing a weight changes the order," reused Phase 3's hand-computed style since
      it's the tighter check): 8 new hand-computed tests in `tests/test_metrics_composite.py`
      covering the empty-input case, the singleton-cohort zero-z-score case, exact 2-member
      population z-scores (±1.0) across all four inputs, the configured-weighted-sum formula,
      sort order, the no-wins/None-exclusion case, off-roster-opponent exclusion, and a
      weight-change producing a different composite score. `python scripts/validate_data.py`
      still passes; full suite now 106/106 (98 prior + 8 new). This task is the composite-scoring
      function only — no CSV/JSON output file yet (SCOPE.md's deliverable #3), matching how every
      Phase 3/4 metric so far has been a library function verified by unit tests, not a file-
      writing script; a results-to-file step is still open, likely alongside Phase 6's
      visualization output.
- [x] Category rankings output — `war/metrics/category.py` adds `category_rankings`,
      PLAN.md Section 6.2's six separate ordered lists (Win Rate, Casualty Efficiency,
      Opponent-Adjusted Rating, Clutch Rating, Squander Index, Longevity-Adjusted Value),
      each sorted independently by its own already-computed metric value rather than any
      combined score. Judgment calls not specified by PLAN.md, documented in the module
      docstring: (1) unlike `composite.py`, no z-scoring/era-cohorting — PLAN.md's era-
      normalization rule is scoped to cross-era *combinations*, and a single-stat list
      combines nothing; (2) sort direction is metric-specific — five categories are
      descending (higher is better) but Squander Index sorts ascending, since PLAN.md
      defines it as a failure rate where lower is the better outcome; (3) each category
      independently drops generals whose value is `None` for that one metric (e.g.
      zero-career-casualties excluded from Casualty Efficiency, zero-qualifying-battles
      excluded from Clutch Rating) rather than assigning a placeholder or excluding them
      from every other category too; (4) "roster" (eligible for any category) is every
      `general_id` that commands at least one row, `rate_stats_by_general`'s keys — this
      excludes off-roster `opponent_general_id`s from Opponent-Adjusted Rating even though
      `oar_ratings` solves a rating for them, same reasoning `composite.py` already gives.
      Verified per SCOPE.md Phase 3 method: 7 new hand-computed tests in
      `tests/test_metrics_category.py` covering the empty-input case (all six categories
      present as empty lists), win-rate descending order with rank starting at 1,
      casualty-efficiency's zero-casualty exclusion, the off-roster-opponent exclusion,
      clutch-rating's no-qualifying-battle exclusion, squander-index's ascending sort plus
      its unlabeled-win exclusion, and longevity being present for every roster general.
      Also ran against the real 83-row dataset as a sanity check (not a substitute for the
      unit tests): Alexander/Genghis top most categories, Saladin bottom most (0.0 clutch
      rating, lowest OAR) — matches the Phase 2 notes on the back-half losing streak.
      `python scripts/validate_data.py` still passes; full suite now 113/113 (106 prior + 7
      new). Output is a library function returning typed lists, same "no CSV/JSON file yet"
      convention `composite.py` left for this same reason — deferred to a combined
      results-to-file step alongside Phase 6's visualization output.
- [x] Test: changing a weight changes the order — `tests/test_metrics_composite.py` already had
      a test confirming a weight change moves a general's raw composite *score*, but SCOPE.md
      Phase 5's verification method is specifically "produces a different order," which a score
      change alone doesn't guarantee (e.g. two generals whose scores both move but stay in the
      same relative sequence). Added `test_changing_weights_changes_the_ranking_order` with a new
      two-general fixture (`_crossed_signals_cohort`) deliberately split 2-vs-2 across the four
      inputs — alice leads on OAR/war_residual (better win/loss record), bob leads on
      decisiveness/longevity (his one win is objective_secured, his 1-year career isn't diluted
      the way alice's 21-year career is) — unlike every prior fixture in that file where one
      general sweeps all four z-scores. Verified the default weights rank `[alice, bob]` and an
      alternate weighting concentrated on decisiveness+longevity (0.05/0.05/0.45/0.45) flips the
      output list to `[bob, alice]`, hand-checked against the actual computed z-scores before
      writing the assertion. `python scripts/validate_data.py` still passes; full suite now
      114/114 (113 prior + 1 new). This closes out Phase 5.

## Phase 6: Visualization
- [x] Scatter: Volume vs Efficiency — `war/viz/volume_efficiency.py` adds
      `volume_efficiency_points` (pure data: one `(battles_commanded, win_rate)`
      point per general, joining `raw.py`/`rate.py`) and
      `render_volume_efficiency_figure` (a plain matplotlib `Figure`, no file I/O,
      so tests can inspect scatter points/labels directly rather than decoding a
      PNG) plus `plot_volume_vs_efficiency`, which renders and saves both a PNG
      and a same-named CSV of the exact plotted values. Uses the `Agg` backend
      (headless, matches the no-display overnight sandbox per OVERNIGHT.md).
      Judgment calls (PLAN.md names two options per axis, not one formula),
      documented in the module docstring: (1) Volume = `battles_commanded`
      rather than total troops commanded — troop totals span orders of
      magnitude across this roster's eras (thousands for Caesar/Alexander vs.
      low millions for Zhukov) and would force a log axis that compresses the
      comparison; battles commanded (6-15 across this roster) reads cleanly on
      a linear axis. (2) Efficiency = `win_rate` rather than casualty exchange
      ratio — the latter is `None`-able and unbounded (`rate.py`'s own
      docstring), `win_rate` is always defined and bounded to [0, 1], and is
      literally PLAN.md's own first-listed option. (3) Per the dataviz skill:
      with only 8 points, every point is directly labeled by name rather than
      color-coded/legend'd by era — "a single series needs no legend box" — and
      all markers use one hue (palette.md's categorical slot 1), since an
      8-color categorical palette can't pass this chart form's all-pairs CVD
      check past 3 slots per the skill's own palette notes anyway; era-color
      coding would also just re-state identity the label already gives with
      only 1-2 generals per era (SCOPE.md's locked 8-general/one-per-era
      roster). Verified per SCOPE.md Phase 6's no-display method: 7 new tests
      in `tests/test_viz_volume_efficiency.py` — hand-computed points, sorted
      output, the empty-input case, the figure's scatter-point count/
      coordinates and text-label count/content read directly off the returned
      `Axes` (no pixel decoding), an empty-input render not erroring, and the
      saved-PNG test asserting file non-emptiness plus the actual PNG magic
      bytes and a matching CSV. `scripts/render_scatter_volume_efficiency.py`
      is the CLI entry, run once against the real 83-row dataset to produce
      `output/viz/volume_vs_efficiency.png`/`.csv`, committed as the actual
      deliverable (SCOPE.md's "rendered as static files" requirement) — visual
      review deferred to the user off-sandbox, but the CSV's own numbers
      already track Phase 2/3's notes (Alexander/Genghis win_rate 1.0
      undefeated, Saladin lowest at 0.375, matching the back-half losing
      streak). `python scripts/validate_data.py` still passes; full suite now
      121/121 (114 prior + 7 new).
- [x] Scatter: Tactical vs Strategic rating — `war/viz/tactical_strategic.py` adds
      `tactical_strategic_points` (pure data, one `(win_rate, decisive_win_rate)`
      point per general via `rate.py`) and `render_tactical_strategic_figure` (a
      plain matplotlib `Figure`, same test-without-a-display shape as
      `volume_efficiency.py`) plus `plot_tactical_vs_strategic`, saving both a PNG
      and matching CSV. PLAN.md names this plot's purpose ("brilliant tactician /
      poor strategist" outliers) but not a formula for either axis — judgment call,
      documented in the module docstring: Tactical rating = `win_rate` (raw
      battlefield win-getting), Strategic rating = `decisive_win_rate`, which
      PLAN.md Section 4 already defines as "wins converted to strategic gain vs.
      tactical-only" — literally this axis, so reused rather than re-derived from
      `decisiveness` the way `squander.py` does for a different stat. Generals
      with zero wins (`decisive_win_rate is None`) are excluded from points, same
      no-data-no-point convention as `squander.py`/`clutch.py`; not reachable on
      this roster (all 8 have wins) but handled for later roster expansion. Both
      axes are already bounded [0, 1], so no log-axis judgment call was needed
      here the way `volume_efficiency.py` had for its axes. Verified per SCOPE.md
      Phase 6's no-display method: 8 new tests in `tests/test_viz_tactical_strategic.py`
      — hand-computed points, the no-wins exclusion, sorted output, the empty-input
      case, figure scatter-point count/coordinates and text-label count/content
      read off the returned `Axes`, an empty-input render not erroring, and the
      saved-PNG test asserting file non-emptiness plus PNG magic bytes and a
      matching CSV. `scripts/render_scatter_tactical_strategic.py` is the CLI
      entry, run once against the real 83-row dataset to produce
      `output/viz/tactical_vs_strategic.png`/`.csv`, committed as the deliverable —
      no general in this roster lands in the "brilliant tactician, poor
      strategist" bottom-right outlier zone (lowest strategic rating is Napoleon
      at 0.91, still high), which reads as expected rather than a bug: this
      8-general roster is all top-tier historically-consensus commanders, not a
      sample built to contain that pattern. `python scripts/validate_data.py`
      still passes; full suite now 129/129 (121 prior + 8 new).
- [x] Scatter: OAR vs Resource Backing — `war/viz/oar_resource_backing.py` adds
      `oar_resource_backing_points` (pure data, one `(oar_rating, avg_resource_backing_tier)`
      point per general) and `render_oar_resource_backing_figure` (a plain matplotlib `Figure`,
      same test-without-a-display shape as the other two scatters) plus
      `plot_oar_vs_resource_backing`, saving both a PNG and matching CSV. PLAN.md names both axes
      directly here (unlike the other two scatters) — x = `oar_ratings(battles)[gid].rating`
      (`oar.py`), reused as-is, roster generals only (same exclusion of off-roster
      `opponent_general_id`s that `composite.py` already applies, for the same reason: this
      ranks the roster, not everyone who ever opposed it). Judgment call: y = mean
      `resource_backing_tier` across a general's own battles — the schema records this field
      per-battle (already read that way by `war_residual.py`/`clutch.py`), so a single
      per-general axis value needs an aggregation no existing metric computes yet; mean was
      chosen over latest/max so a career-spanning point reflects the whole career's typical
      material position (Frederick's tier drops 3→1 across the Seven Years' War per this file's
      earlier notes; Napoleon's rises 2→5→1) — small enough to compute directly in the viz module
      rather than adding a new `rate.py` stat nothing else needs. Y-axis gets a fixed `[0.5, 5.5]`
      limit (the schema's known `[1, 5]` tier range) since, unlike the other two scatters, OAR
      itself is an open-ended Elo-style number with no natural axis bound. Verified per SCOPE.md
      Phase 6's no-display method: 8 new tests in `tests/test_viz_oar_resource_backing.py` — the
      resource-backing mean hand-computed, the OAR value cross-checked against an independent
      `oar_ratings` call (not hand-derivable as a one-line fraction, same caveat `oar.py`'s own
      tests note), sorted output, the empty-input case, figure scatter-point count/coordinates and
      text-label count/content read off the returned `Axes`, an empty-input render not erroring,
      and the saved-PNG test asserting file non-emptiness plus PNG magic bytes and a matching CSV.
      `scripts/render_scatter_oar_resource_backing.py` is the CLI entry, run once against the real
      83-row dataset to produce `output/viz/oar_vs_resource_backing.png`/`.csv`, committed as the
      deliverable — sanity-checked against Phase 3's OAR notes (Alexander highest at ~1878,
      Saladin lowest at ~1430), consistent with the earlier two scatters' checks. `python
      scripts/validate_data.py` still passes; full suite now 137/137 (129 prior + 8 new). This
      closes out the three PLAN.md Section 6 scatter plots; ranking tables (the next unchecked
      Phase 6 item) are still open.
- [x] Ranking tables rendered — `war/viz/ranking_tables.py` adds
      `composite_ranking_rows`/`category_ranking_rows` (pure data, joining
      `composite.py`/`category.py`'s already-computed rankings with the raw
      per-general values they're built from — `oar.py`, `rate.py`,
      `longevity.py`, `war_residual.py` — plus display names/era from
      `generals.csv`) and `render_ranking_tables_html`/`save_ranking_tables`,
      producing one static HTML page (Composite Power Ranking + all six
      PLAN.md Section 6.2 category tables) with two matching CSVs. Per the
      dataviz skill's own form guidance ("more than ~7 meaningful classes ->
      a table," `choosing-a-form.md`), this is a plain HTML table, not a
      chart — no categorical palette to validate, light-mode only, matching
      the other three Phase 6 modules' light-only treatment for consistency.
      Judgment call, the substantive one: SCOPE.md's deliverable 3 and
      PLAN.md Section 5's own example ("Caesar: OAR 82 +/- 15") ask for
      rankings with confidence intervals, but `uncertainty.py`'s Monte Carlo
      resampling deliberately never re-runs OAR, decisive_win_rate, or
      Longevity-Adjusted Value (Phase 4's own documented reasoning — they're
      pure functions of outcome/objective_secured/career years, untouched by
      the resampled troop/casualty fields, so "resampling" them would just
      repeat the same point estimate). Rather than fabricate a band for
      those, this table attaches a genuine 90% Monte Carlo interval only
      where the pipeline actually produces one: WAR-residual (one of the
      composite's four inputs) and Clutch Rating (one of the six category
      lists) — every other column is an honest point estimate with no
      invented uncertainty. `mc` (the Monte Carlo result dict) is an
      optional injected parameter rather than computed inside the module, so
      tests can hand-build a two-entry `MetricDistribution` fixture instead
      of paying for a real 1000-run resample just to check the CI columns
      wire to the right cells. Verified per SCOPE.md Phase 6's no-display
      method: 9 new tests in `tests/test_viz_ranking_tables.py` — hand-joined
      row values cross-checked against independent calls to
      `composite_ranking`/`oar_ratings`/`rate_stats_by_general`/
      `longevity_adjusted_value_by_general`/`war_residual_by_general`, the
      CI-attached-only-when-`mc`-given case (both present and
      runs_used=0/absent), the category-CI-only-on-clutch-rating case, the
      empty-input case for both row-builders, HTML content checks (all 7
      table captions and both test generals' names present) without
      decoding pixels, and the saved-file test asserting the HTML starts
      with `<!DOCTYPE html>` plus both CSVs' header rows and row counts.
      `scripts/render_ranking_tables.py` is the CLI entry (fixed
      `MC_SEED=20260920` so the committed CSVs/HTML are reproducible run to
      run), run once against the real 83-row dataset to produce
      `output/viz/ranking_tables.html`/`_composite.csv`/`_categories.csv` —
      sanity-checked against every prior phase's notes (Alexander/Genghis
      top the composite ranking at 0.85/0.70, Saladin near the bottom at
      -0.70, matching the back-half-losing-streak notes already logged
      repeatedly). `python scripts/validate_data.py` still passes; full
      suite now 146/146 (137 prior + 9 new). This closes out Phase 6 — all
      three scatter plots plus the ranking tables are rendered.

## Phase 7: Sanity pass and dev log
- [x] Review composite ranking top/bottom against historian-consensus expectations, log findings (bug vs. legitimate surprise) in Notes below — do not hand-tune weights to force an order — reviewed `output/viz/ranking_tables_composite.csv`/`_categories.csv` against Phase 2's historian-consensus notes; top (Alexander/Genghis) and the Saladin/Frederick squander findings check out, but Julius Caesar ranking dead last (below Saladin) despite mid-pack-or-better standing in every individual category is a methodology artifact of n=2 era-cohort z-scoring, not a real finding — documented below, not hand-tuned.
- [x] `notes/` dev log via the project-notes skill (SCOPE.md deliverable 6), written from the Notes section below and the commit history — deviation: the `project-notes` skill named in CLAUDE.md isn't installed in this sandbox (checked `~/.claude/skills/`, not present), and neither is the `ai-writing` skill CLAUDE.md calls for on prose docs. Per this run's "don't stop, make the call, note it" instruction, wrote `notes/dev-log.md` by hand instead, covering the same ground a notes skill would (deviations, decisions, tradeoffs, narrative including dead ends) sourced from this file's per-task notes, the module docstrings, and `git log`. This closes out Phase 7 and every phase in SCOPE.md.

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
- Phase 7 sanity pass on `output/viz/ranking_tables_composite.csv`/`_categories.csv` against
  Phase 2's historian-consensus notes:
  - **Checks out, no action**: Alexander #1 (0.85) and Genghis Khan #2 (0.70) at the top match
    their undefeated/near-undefeated reputations. Saladin's #7 (-0.70) and last-place category
    finishes (win_rate 0.375, clutch_rating 0.0, OAR lowest at 1430) track the documented
    back-half losing streak against Richard I. Frederick topping the squander_index category
    (0.44, worst) matches the "tactically brilliant, strategically indecisive" consensus
    already noted in Phase 3. None of this looks like a bug.
  - **Already-known, re-confirmed**: Frederick/Zhukov/Napoleon/Grant tie at composite 0.0 — this
    is Phase 5's documented singleton-era-cohort z=0 convention (SCOPE.md's locked 8-general,
    one-or-two-per-era roster puts these four alone in their era, so their z-score, and
    therefore composite score, is exactly 0 regardless of underlying quality). Not new, not a
    bug, still flagged here per this task's instructions.
  - **New finding, methodology limitation not a data/code bug**: Julius Caesar ranks *last*
    overall (composite -0.85, below Saladin) despite `decisive_win_rate`=1.0 (every recorded
    win rated Strategic/Rout), `squander_index`=0.0 (tied-best, no squandered wins),
    `casualty_efficiency` 3rd of 8, `win_rate` 6th of 8 (0.73, well above Saladin's 0.375), and
    `clutch_rating` 4th of 8 — nowhere near a last-place profile, and starkly inconsistent with
    the historian-consensus view of Caesar as a top-tier commander (routinely named alongside
    Alexander and Napoleon in "greatest generals" lists). Root cause, confirmed by hand: Ancient
    era has exactly 2 members (Caesar, Alexander), so `composite.py`'s within-era z-scoring
    z-scores Caesar purely against Alexander with n=2 — a population of 2 forces the two
    z-scores per metric to be exact mirror images (+1.0/-1.0), so Caesar's composite is
    mechanically pulled toward -(Alexander's score) simply because Alexander is undefeated, not
    because Caesar's underlying record is weak. The same z-scoring formula that correctly
    separates Genghis/Saladin (a real quality gap, per Phase 5's notes) produces a misleading
    result here because the *other* member of the pair happens to be a historical outlier
    (undefeated) rather than a "typical" peer. This is a structural limitation of z-scoring
    within tiny (n=2) cohorts on this locked 8-general roster, not a bug in the composite
    formula or the underlying data — per SCOPE.md Phase 7 ("do not hand-tune weights to force a
    specific order") and the "don't expand scope" guidance, left as-is and flagged here rather
    than patched; would likely resolve itself with PLAN.md's fuller 15-25 general roster (more
    members per era cohort) if this project is extended past the locked-8 scope.
- The `project-notes` and `ai-writing` skills CLAUDE.md names for this repo aren't installed in
  this sandbox. `notes/dev-log.md` was written directly instead of via the skill, covering the
  same ground (deviations/decisions/tradeoffs/narrative) using this file's notes, module
  docstrings, and `git log` as source material.

## Phase 2b: Roster expansion (11 new generals, per PLAN.md's original 15-25 target)

Phase 1-7 above covered the locked 8-general validation roster only. That pipeline works
end-to-end now, so per PLAN.md Section 7 step 5 ("expand dataset to full roster") this phase adds
the rest of PLAN.md's originally-listed roster (dropping only Sun Tzu — flagged there as
conditional on "enough battle data," and there isn't any at battle-row granularity). Same rules
as Phase 2: one checkbox per general, `data/generals.csv` row + 8-15 cited `data/battles.csv` rows
each, same personal-command/no-fabrication bars already established and documented in this file's
Phase 2 notes, `source_confidence` tagged honestly per source era. New for this phase: first run
`python scripts/scrape_wikipedia_infobox.py "<battle name>"` per battle for a draft
strength/casualties scaffold (unverified — cross-check every number against an academic source
before writing the row, same as always; see scripts/overnight.sh's amended prompt for the exact
instruction).

- [x] Hannibal Barca battles (Ancient) — 7 rows (Ticinus, Trebia, Lake Trasimene, Cannae,
      Battle of Capua 212bc, Battle of Petelia 208bc, Zama) in `data/battles.csv` plus a
      `generals.csv` row; `era=Ancient`, `source_confidence=Low`, `tech_era_tier=1` for every
      row, matching Caesar and Alexander (the existing Ancient-era rows). Web-researched via a
      delegated research pass cross-checking Wikipedia infoboxes and the primary ancient sources
      (Polybius, Livy, Appian) against named modern historians (Goldsworthy, Lazenby, Daly,
      Clodfelter, Bagnall). `resource_backing_tier` set per-row (2 for the 218-217bc invasion
      force, 3 at Cannae and Zama, 1 at Petelia's shrinking 208bc Bruttium foothold), same
      per-row approach as Frederick/Napoleon/Grant. Deviation/judgment call: roster came in at 7
      battles, short of the dataset's usual 8-15 range, and is documented rather than padded —
      a real historiographical pattern turned up where Roman chroniclers meticulously recorded
      their own dead for the long 212-207bc stalemate-years battles (Herdonia I/II, Canusium,
      Silarus, Grumentum) but never gave a usable troop-strength figure for Hannibal's own side
      in any of them, so those rows were dropped under the same no-fabrication bar as Alexander's
      Persian Gate/Genghis's Khalakhaljid Sands, rather than lowering the bar to hit a row count
      — the same kind of documented shortfall as Zhukov's 6-battle roster. Also dropped the 219bc
      Siege of Saguntum, the 220bc Battle of the Tagus, the three Battles of Nola, and the Battle
      of Numistro for the same reason. Two included rows (Ticinus, Capua) still have one flagged
      order-of-magnitude placeholder field each (Ticinus's casualties are only ever described
      qualitatively as "Light"/"Heavy"; Capua's own_casualties has no figure at all in any
      source) — same treatment as several Genghis Khan/Saladin rows. Modern-corrective judgment
      calls, documented per-row: Cannae's enemy_casualties (~50,000) uses a modern mid-range
      estimate (Goldsworthy/Daly) over Polybius's 70,000/Livy's 48,200, which Clodfelter himself
      calls implausible for a 50,000-man Carthaginian army to inflict; Trebia's own/enemy
      casualties use Lazenby's modern estimates over the ancient sources' vaguer figures — same
      "prefer the modern historian's corrective" precedent as Caesar/Genghis/Zhukov. Net record
      is 6 wins / 1 loss: undefeated in every included Italian battle, with the sole loss being
      Zama itself (`political_constraint_flag=true`: rushed recall from Italy, collapsed peace
      talks, Masinissa's Numidian cavalry defection) — matches historian consensus of Hannibal as
      tactically undefeated in Italy but strategically unable to force Rome to terms, losing only
      the one battle that decided the war. `python scripts/validate_data.py` passes; full test
      suite (150 tests) still green.
- [x] Scipio Africanus battles (Ancient) — 5 rows (Siege of New Carthage, Baecula, Ilipa, Battle
      of the Camps/Utica, Zama) in `data/battles.csv` plus a `generals.csv` row; `era=Ancient`,
      `source_confidence=Low`, `tech_era_tier=1`, matching Caesar/Alexander/Hannibal. First ran
      `scripts/scrape_wikipedia_infobox.py` per battle for a draft scaffold, then cross-checked
      every figure against Polybius/Livy chapter citations and named modern historians
      (Goldsworthy, Lazenby, Scullard, Bagnall, Hoyos) via web research; `source_citation` cites
      the primary ancient sources plus the modern historian, never "Wikipedia" alone, matching
      this dataset's established citation convention. Deviation/judgment call: dropped the Battle
      of the Great Plains (203 BC) despite it being well-attested tactically in both Polybius and
      Livy — neither source gives any casualty figure for either side, same no-fabrication bar as
      Alexander's Persian Gate/Genghis's Khalakhaljid Sands/Hannibal's dropped Nola battles. Also
      dropped the Battle of Cirta (fought by legate Gaius Laelius and Masinissa) and the battle
      against Vermina (fought by Gnaeus Octavius after Zama) for the same subordinate-command bar
      used elsewhere in this dataset, and excluded Scipio's presence at Ticinus/Cannae as a junior
      officer under his father's/others' command (Ticinus is already a Hannibal-roster row with
      his father as opponent). Net roster is 5 rows — thinner than the usual 8-15 range but a
      documented structural consequence (short 7-year independent-command career, several famous
      battles failing the no-fabrication or personal-command bar), the same kind of shortfall
      already logged for Zhukov (6) and Hannibal (7). The Battle of the Camps (203 BC, night
      assault on the Carthaginian/Numidian winter camps, Wikipedia's actual page title is "Battle
      of Utica (203 BC)") is a distinct row from the separate, inconclusive multi-year Siege of
      Utica, which is excluded for having no attached casualty/outcome figures of its own; its
      `opponent_general_id` is left blank since command was genuinely split between two co-equal
      allied kings (Hasdrubal Gisco for Carthage, Syphax for Numidia), same treatment as Petelia's
      blank field. Baecula is recorded as a Win with `decisiveness=Tactical`/
      `objective_secured=false` since Hasdrubal Barca escaped with his veteran core intact and
      marched to Italy the following year — the same tactical-win-no-strategic-payoff pattern as
      Napoleon's Borodino elsewhere in this dataset. The Zama row is the mirror of the existing
      `hannibal-zama-202bc` row (troop/casualty figures swapped so both rows agree on the same
      battle) with an independently-justified `resource_backing_tier=2` one tier below Hannibal's
      3, reflecting Scipio's chronically under-resourced, politically constrained African
      expedition (fought largely with the stigmatized Cannae-legion volunteers over Fabius
      Maximus's Senate opposition) versus Hannibal's freely-mobilized home-soil levy — flagged
      `political_constraint_flag=true` on both the Camps and Zama rows for this reason,
      independent of Hannibal's own flag on his side. `python scripts/validate_data.py` passes;
      full test suite (150 tests) still green — data curation doesn't add new tests.
- [x] Subutai battles (Medieval) — 5 rows (Battle of Khunan, Battle of Khankala, Battle of the
      Kalka River, Battle of Mohi, Siege of Kaifeng) in `data/battles.csv` plus a `generals.csv`
      row; `era=Medieval`, `source_confidence=Low`, `tech_era_tier=2` for every row, matching
      Genghis Khan/Saladin. Delegated a research pass first (candidate battles across Subutai's
      full career), then cross-checked command attribution and numbers by hand via
      `scripts/scrape_wikipedia_infobox.py` plus targeted web research against named academic/
      primary sources (Sverdrup's *The Mongol Conquests*, Gabriel's *Subotai the Valiant*, Timothy
      May, plus primary chronicles per row) before writing each row, per this run's amended
      instruction. Deviation/judgment call, the big one: applied the existing "personally
      supreme-commanded" bar unusually strictly, which cuts this roster down to 5 rows (tied with
      Scipio Africanus for thinnest in the dataset) — most of Subutai's famous campaigns turned out
      to be either subordinate-led (Kolomna's own Wikipedia infobox names Burundai/Kulkan as
      commander, not Subutai, despite secondary summaries placing him with the invasion force; also
      Sit River, Legnica, Nishapur, the 1216-19 Merkit campaign) or genuinely disputed between
      sources on whether Subutai or Tolui held tactical command (Sanfengshan, Daohuigu) — dropped
      both disputed-attribution cases rather than pick a side, the same strict standard already
      used for Zhukov's Stavka-coordinator exclusions. Also dropped 4 battles for the usual
      no-fabrication bar (Irghiz River, Sagim, Samara Bend, the Rayy/Qazvin pursuit) — no
      quantifiable casualty figure for one or both sides in any source found. Net effect: Daohuigu
      was Subutai's one credible documented personal defeat, and it's exactly the one dropped for
      attribution ambiguity, so this 5-battle roster reads as undefeated (5 wins, 0 losses) despite
      that not being a claim about his real career — flagged explicitly in `generals.csv`'s note so
      Phase 2b's eventual re-run of Phase 7's sanity pass doesn't mistake it for a data error.
      `resource_backing_tier` set per-row (2 for the 1222-23 Caucasus/Kalka reconnaissance-in-force,
      4 for Mohi's empire-scale western campaign, 5 for Kaifeng's converged main imperial siege
      army), same per-row approach as Frederick/Napoleon/Grant. `political_constraint_flag=true`
      for Mohi specifically (Yuan Shi credits Subutai as the real tactical author while Batu held
      only nominal supreme command — a documented, genuine constraint on his formal authority, not
      just normal hierarchy). `python scripts/validate_data.py` passes; full test suite (150 tests,
      unchanged — data curation doesn't add tests) still green.
- [x] Tokugawa Ieyasu battles (Medieval) -- 6 rows (Anegawa, Mikatagahara, Siege of Takatenjin,
      Nagakute, Sekigahara, Tennoji/Summer Siege of Osaka) in `data/battles.csv` plus a
      `generals.csv` row; `era=Medieval` (per SCOPE.md's roster bucketing) but `tech_era_tier=3`
      for every row rather than the 2 used for this dataset's other Medieval generals -- a
      deliberate divergence since tech_era_tier tracks actual battlefield technology
      (gunpowder-era Sengoku Japan) independent of the era-cohort label. Delegated a research
      agent first to survey candidate battles and command attribution, then independently
      cross-checked troop/casualty figures via web research against named sources (Turnbull's
      Osprey titles, Sadler's *The Maker of Modern Japan*, Bryant's *Sekigahara 1600*, Sansom's
      *A History of Japan*). Deviation/judgment call, the big one: excluded the Battle of
      Nagashino (1575) despite Tokugawa being a named commander -- sources state Nobunaga "took
      command of the entire army," the same personal-command bar already used for Saladin's
      al-Babein and Zhukov's Stalingrad/Kursk. Also excluded the Komaki standoff (no single
      quantifiable pitched-battle casualty figure; Nagakute, the one attributable clash within
      that campaign, is included separately), the Winter Campaign of the Siege of Osaka (troop
      strength known, no campaign casualty figure found), and three personally-commanded battles
      with no quantifiable casualties in any source found (Azukizaka, Wakamiko/Tensho-Jingo,
      First Ueda). Sekigahara's casualty figures have no clean modern-historian corrective
      available (Bryant's own modern figure sits *above* the Edo-period chronicle range rather
      than revising it downward) -- used a documented midpoint of the primary chronicle range
      instead and flagged the unresolved disagreement rather than implying false consensus.
      `python scripts/validate_data.py` passes; full test suite (150 tests, unchanged -- data
      curation doesn't add tests) still green.
- [x] George Washington battles (Early Modern) — 12 rows (Jumonville Glen, Fort Necessity,
      Harlem Heights, White Plains, Trenton, Assunpink Creek, Princeton, Brandywine, Germantown,
      Whitemarsh, Monmouth, Siege of Yorktown) in `data/battles.csv` plus a `generals.csv` row;
      `era=Early Modern` (matching Frederick the Great's SCOPE.md bucket), `tech_era_tier=3` for
      every row (same contemporaneous linear-gunpowder tier as Frederick — the French and Indian
      War and the Seven Years' War are the same global conflict). Two delegated research passes:
      one to survey candidate battles/command attribution across both the French and Indian War
      (1754) and the Revolution (1776-81), a second specifically to cross-check every figure
      against a named academic source (Fred Anderson, David Hackett Fischer's *Washington's
      Crossing*, Thomas McGuire's *Philadelphia Campaign* volumes, Henry P. Johnston's 1897
      Harlem Heights monograph, Lender & Stone's *Fatal Sunday*, Harris & Ecelbarger's 2021
      *Journal of the American Revolution* muster-record reconstruction) per this run's amended
      instruction, rather than trusting Wikipedia/American Battlefield Trust's first-pass figures
      directly — this caught two real errors (Princeton's American strength was off by ~25% at
      the first pass; Trenton's enemy-casualty figure double-counted wounded that Fischer's own
      prose nests inside the captured total). Deviation/judgment call, the big one: applied the
      existing personal-command bar strictly, excluding Monongahela (Washington was an aide to
      Braddock with no command authority), Long Island/Kip's Bay/Fort Washington-Fort Lee
      (Putnam/Stirling/Sullivan/Greene/Magaw ran the fighting), and Stony Point/Springfield
      (Wayne/Greene) — but included White Plains and Monmouth as qualified cases (Washington
      personally directed the overall army-level plan even though a subordinate ran one specific
      phase: Chatterton's Hill at White Plains, Charles Lee's opening vanguard at Monmouth before
      Washington relieved him mid-battle), applying the same "personally directed the overall
      plan" standard already used for Grant's Overland Campaign rows. Yorktown combines American
      and French troop/casualty figures into one field under Washington's protocol-supreme
      command (confirmed by Rochambeau's own memoir), the same friendly-multi-force treatment
      already used for Zhukov's Vistula-Oder Offensive — its French-casualty component (254) is
      flagged as the weakest-sourced figure in this roster, traceable only to tertiary web sources
      rather than a named academic historian. Roster has a genuine 22-year gap (1754-1776) with no
      personally-commanded battle in the middle of the career, not at either end — unlike any
      prior general in this dataset; `career_start_year`/`career_end_year` (1754/1781) will read
      as a long 28-year career for only 12 battles once Phase 2b's pipeline re-run happens, flagged
      in `generals.csv`'s note now so it doesn't look like a longevity-metric bug later. Net record
      is 5 wins (2 Rout-level: Trenton, Princeton; Jumonville Glen and Yorktown also Rout) / 3
      losses (Fort Necessity, Brandywine, Germantown) / 2 draws (Assunpink Creek, Monmouth) / 1
      additional loss (White Plains, a withdrawal) / 1 minor defensive win (Whitemarsh). `python
      scripts/validate_data.py` passes; full test suite (150 tests, unchanged — data curation
      doesn't add tests) still green. Dev log written to `~/notes/war-analyzer/dev-log.md` per
      CLAUDE.md (this repo's `notes/dev-log.md` remains superseded).
- [x] Wellington battles (Napoleonic) — 19 rows (Assaye, Argaon, Roliça, Vimeiro, Talavera,
      Bussaco, Fuentes de Oñoro, Ciudad Rodrigo, Badajoz, Salamanca, Burgos, Vitoria, Sorauren,
      Nivelle, Nive, Orthez, Toulouse, Quatre Bras, Waterloo) in `data/battles.csv` plus a
      `generals.csv` row (`general_id=wellington`, matching the `opponent_general_id=wellington`
      already used by the pre-existing `napoleon-waterloo-1815` row); `era=Napoleonic`,
      `tech_era_tier=4` (matching Napoleon/Grant), `source_confidence` mostly Medium, downgraded
      to Low on three rows with genuine cross-source casualty disagreement (Assaye/Argaon's
      Maratha irregular-cavalry counts, Toulouse's disputed enemy_casualties). Delegated a research
      pass first (candidate battles across the full 1803-1815 career, command attribution, draft
      figures via `scripts/scrape_wikipedia_infobox.py` plus web research), then cross-checked its
      citations and numbers by hand before writing rows — sources are Oman's 7-volume *A History of
      the Peninsular War*, Napier, Esdaile, Weller, Fletcher's Osprey titles, and Chandler for
      Waterloo, never "Wikipedia" alone. Deviation/judgment call, the big one: 19 rows is above
      this dataset's usual 8-15 target — documented as a deliberate choice rather than an arbitrary
      cut, since Wellington's career turned out to be the most comprehensively and consistently
      sourced in the dataset so far (virtually no candidate battle failed the no-fabrication bar,
      the opposite problem from Hannibal/Scipio/Subutai/Zhukov's under-target rosters), and cutting
      bar-clearing rows purely to hit a round number would repeat, in reverse, the padding mistake
      this dataset's Phase 2 notes already flagged as wrong; full reasoning in `generals.csv`'s
      note. Includes the 1803 India campaign (Assaye, Argaon, fought under the Wellesley name years
      before the Peninsular War) as a scope call matching Napoleon's Montenotte precedent for an
      early independent command. Talavera isolates Wellesley's own British force from Cuesta's
      separate, non-subordinate Spanish command; Vitoria by contrast combines the full multinational
      Allied total since Spanish divisions were genuinely integrated into his order of battle by
      1813 — two similar-looking situations resolved oppositely based on the actual command
      relationship, not a fixed rule. Waterloo isolates Wellington's Anglo-allied force from
      Blücher's Prussians (no protocol-supreme-command relationship existed, unlike Washington's
      Yorktown), with enemy_troop_strength/enemy_casualties set to match `napoleon-waterloo-1815`'s
      own-side figures exactly (72,000/34,500) — that existing Napoleon row's enemy figures remain
      the combined Anglo+Prussian total, a documented, intentional asymmetry between the two rows
      for the same battle. San Sebastián (run independently by Thomas Graham while Wellington fought
      Sorauren simultaneously) is excluded under the same personal-command bar as Napoleon's
      Auerstedt exclusion from Jena; the week-long "Battle of the Pyrenees" is narrowed to Sorauren,
      the one action within it Wellington personally commanded. Net record is 18 wins (5
      Rout-level) / 1 loss (Burgos, his clearest field failure, included for an honest record rather
      than a highlight reel). `python scripts/validate_data.py` passes; full test suite (150 tests,
      unchanged — data curation doesn't add tests) still green.
- [x] Robert E. Lee battles (Industrial) — 14 rows (Gaines's Mill, Malvern Hill, Second Bull Run,
      Antietam, Fredericksburg, Chancellorsville, Gettysburg, Wilderness, Spotsylvania, Cold Harbor,
      the Crater, Globe Tavern, Third Petersburg, Appomattox) in `data/battles.csv` plus a
      `generals.csv` row (`general_id=robert-e-lee`, matching the `opponent_general_id=robert-e-lee`
      already used by several existing Grant rows); `era=Industrial`, `tech_era_tier=4` matching
      Grant, `source_confidence` mostly High/Medium, Low only on Gettysburg (genuine 23,000-28,000
      Confederate-casualty range across sources) and Spotsylvania (mirrors Grant's own Low, same
      Wikipedia-vs-ABT troop-strength spread). Ran `scripts/scrape_wikipedia_infobox.py` per battle
      for a draft scaffold (hit Wikipedia API rate-limiting mid-run — spaced calls out rather than
      retry-looping), cross-checked every figure against named academic sources (Clodfelter's
      *Warfare and Armed Conflicts*, Sears' single-volume campaign histories, Hennessy, O'Reilly,
      Busey & Martin for Gettysburg, Rhea and Trudeau for the Overland Campaign/Petersburg rows,
      Freeman's *R. E. Lee* biography) before writing rows; `source_citation` cites those named
      historians, not "Wikipedia" alone, per this session's tightened citation instruction (a
      stricter standard than the original Grant rows used, noted here rather than retroactively
      edited). Deviation/judgment call, the big one: 7 of the 14 rows (Wilderness, Spotsylvania,
      Cold Harbor, the Crater, Globe Tavern, Third Petersburg, Appomattox) mirror existing
      `grant-*-1864`/`grant-*-1865` rows with own/enemy strength and casualty fields swapped, the
      same treatment already established for the Napoleon/Wellington Waterloo pair and the
      Hannibal/Scipio Zama pair — outcomes are not always symmetric (e.g. Grant's Cold Harbor Loss
      mirrors to a Lee Win) but Draw rows (Wilderness, Spotsylvania) are Draw on both sides. The
      Second Battle of Petersburg (June 1864) is deliberately excluded from that mirrored set even
      though it falls inside the date range, since Grant's own row for that battle documents
      P.G.T. Beauregard as the sole defending commander with Lee's army arriving only as the
      assaults were ending — the same subordinate-command exclusion bar used elsewhere in this
      dataset, not an oversight. Antietam is coded Loss rather than Draw (a real, actively-debated
      historiographical call, documented in the row's notes) since Lee's invasion failed its own
      stated objective and ended in full withdrawal from Maryland, even though neither army broke
      on the field itself on September 17. `resource_backing_tier` is set per-row on a declining
      3→2→1 curve (Army of Northern Virginia's real shrinking, irreplaceable manpower position),
      the intentional mirror-image of Grant's own rising 2→5 curve on the same roster since the two
      sides' wartime mobilization trajectories moved in opposite directions — full reasoning in
      `generals.csv`'s note. `political_constraint_flag` is true for Antietam/Gettysburg (both
      invasions had explicit political rationales) and true for every 1864-through-Third-Petersburg
      row (Davis's standing order to hold the capital, a different and longer-lived constraint than
      the US-election-cycle pressure driving Grant's own flag on the same mirrored rows — a
      documented asymmetry, same pattern as the Waterloo/Wellington pair); false again at
      Appomattox once the Confederate government had already fled and the surrender decision was
      Lee's own judgment. Net record is 6 wins (2 Rout-level: Second Bull Run, the Crater) / 6
      losses (1 Rout-level: Appomattox) / 2 draws (Wilderness, Spotsylvania) — deliberately not
      hand-tuned, and it happens to land close to even, matching Lee's historian-consensus
      reputation as tactically dominant for most of his tenure while still losing the war (the
      "brilliant on the field, lost the war" pattern PLAN.md's Squander Index targets). `python
      scripts/validate_data.py` passes; full test suite (150 tests, unchanged — data curation
      doesn't add tests) still green.
- [x] Dwight D. Eisenhower battles (WWII) — 6 rows (Operation Torch, Tunisian Campaign, Operation
      Husky, Operation Overlord/Normandy Campaign, Battle of the Bulge, the Rhine crossing/final
      drive into Germany) in `data/battles.csv` plus a `generals.csv` row; `era=WWII`,
      `tech_era_tier=5` matching Zhukov, `resource_backing_tier` rising 4→5 across 1942-45 (real
      landing-craft/amphibious-lift shortages through 1943, per Ambrose/D'Este, easing once full
      Allied mobilization matured), `source_confidence` Medium except the Rhine row (Low, see
      below). Delegated a research pass first (candidate operations, command-structure evidence,
      draft figures via `scripts/scrape_wikipedia_infobox.py` plus web research), then
      independently re-ran the scraper myself and cross-checked casualty figures against named
      academic sources (Atkinson's Liberation Trilogy, Ambrose, D'Este, Beevor, MacDonald,
      Clodfelter) via further web research before writing rows — `source_citation` names those
      historians, never "Wikipedia" alone. Deviation/judgment call, the central one: as Supreme
      Allied Commander, Eisenhower ran every campaign from a headquarters through subordinate
      army-group commanders (Alexander, Montgomery, Bradley, Patton, Devers), a genuinely harder
      "personally commanded" case than Zhukov's Front-command or Grant's Meade-as-tactical-
      commander precedent — resolved by applying the same "singular top of the chain, personally
      made a documented top-level decision" standard, with Normandy flagged as this general's
      single biggest stretch of that standard (Eisenhower delegated ground command of the *entire*
      Allied force, both army groups, to Montgomery until 1 Sept 1944, a bigger delegation than
      Grant/Meade). Kasserine Pass is folded into the Tunisian Campaign row rather than excluded or
      split out, since Eisenhower's own decisive response (relieving Fredendall, installing
      Alexander) followed within days. Falaise Gap, Operation Market Garden, and Operation Plunder
      are excluded on the same Stalingrad-style no-documented-Eisenhower-decision basis used for
      Zhukov's Stavka-coordinator exclusions; Falaise's dates also sit entirely inside the Overlord
      row's window and would double-count. The Rhine-crossing row's enemy_casualties uses the Ruhr
      Pocket's ~317,000 POWs (the largest well-documented West-front-specific capture event in the
      window) as a flagged lower bound rather than the infobox's own casualty range, which is
      explicitly scoped to "all fronts" and not usable — the one Low-confidence row in this roster,
      for that reason. Roster size (6) is below the dataset's usual 8-15 range, the same structural
      shortfall as Zhukov's 6-battle roster and for the same reason (few operations clear the
      singular-command bar once subordinate-army-group-led actions are excluded), documented rather
      than padded. Net record is 6 wins / 0 losses / 0 draws — a real, structurally different shape
      from every other general in this dataset, flagged explicitly in `generals.csv`'s note for
      Phase 7's eventual sanity-pass re-run so a perfect record isn't mistaken for a metrics bug.
      `python scripts/validate_data.py` passes; full test suite (150 tests, unchanged — data
      curation doesn't add tests) still green.
- [x] Erwin Rommel battles (WWII) — 9 rows (Battle of Arras 1940, Siege of Tobruk 1941/first siege,
      Operation Battleaxe, Operation Crusader, Battle of Gazala incl. fall of Tobruk, First Battle of
      El Alamein, Alam el Halfa, Second Battle of El Alamein, Battle of Kasserine Pass) in
      `data/battles.csv` plus a `generals.csv` row; `era=WWII`, `tech_era_tier=5` matching Zhukov/
      Eisenhower, `resource_backing_tier` set per-row on a 4→2→3→2→1→1→2 arc (full 1940 Wehrmacht
      backing down to the chronically fuel/supply-starved Panzer Army Africa of late 1942, ticking back
      up slightly for Kasserine's fresher Tunisia reinforcements) — full reasoning in `generals.csv`'s
      note. Delegated a research pass first (candidate battles across the full 1940-43 career, command
      attribution, draft figures via Wikipedia infoboxes), then independently re-ran
      `scripts/scrape_wikipedia_infobox.py` on every candidate myself and cross-checked contested
      figures via further web research against named academic sources (Fraser's *Knight's Cross*,
      Frieser's *The Blitzkrieg Legend*, Ellis's UK official history, Playfair's *The Mediterranean and
      Middle East*, Barnett's *The Desert Generals*, Barr's *Pendulum of War*, Kitchen's *Rommel's
      Desert War*, Atkinson's *An Army at Dawn*, Bungay's *Alamein*) before writing rows —
      `source_citation` names those historians, never "Wikipedia" alone. Deviation/judgment call, the
      central one: dropped two of Rommel's most famous engagements for the no-fabrication bar —
      Operation Sonnenblume (Feb-May 1941, his legendary opening Cyrenaica counteroffensive) has no
      Axis personnel-casualty figure in any source found despite extensive searching, and the Battle of
      Medenine (6 March 1943, his last African battle) has no Axis troop-strength headcount in any
      source found (only tank counts and unit names) — same bar as Alexander's Persian Gate/Genghis's
      Khalakhaljid Sands, both documented as real losses to the roster's narrative rather than silently
      worked around with a constructed estimate. Also dropped the 1940 Meuse crossing at Dinant/Houx and
      the Saint-Valery-en-Caux surrender (numbers not isolated to those specific actions apart from the
      whole 1940-campaign total already folded into the Arras row) and excluded Normandy 1944/Army Group
      B entirely on personal-command grounds (Rommel was absent for D-Day itself, and tactical command
      of the Caen sector sat with Panzer Group West/Seventh Army's own commanders throughout, the same
      standard as Zhukov's Stalingrad/Kursk/Bagration and Eisenhower's Market Garden/Plunder exclusions).
      Kasserine Pass is a genuine mirrored pair with the existing `eisenhower-tunisia-1943` row (that
      row's own notes already name Rommel as the opposing commander there) but at different granularity —
      Eisenhower's row is the whole campaign-spanning aggregate with von Arnim as opponent, this new row
      is the narrow 19-22 Feb battle Rommel personally commanded, opponent Fredendall — documented as
      deliberately not a duplicate. Second Alamein's own_casualties (41,800, Playfair's low end of a
      41,800-73,000 cited range) is this roster's most contested figure, on the same scale as Zhukov's
      Operation Mars dispute — Niall Barr's own detailed breakdown sums to roughly 30,500, a third source
      cites 36,939 — documented rather than resolved, hence the one `source_confidence=Low` row in this
      roster. Net record is 3 wins (1 Rout: Gazala) / 5 losses (1 Rout: Second Alamein) / 1 draw (First
      Alamein, coded Draw per the existing Zorndorf/Eylau "modern historiography over contemporary claims"
      precedent) — a strong 1940-42 start giving way to a losing back half from Alam el Halfa onward,
      matching historian consensus rather than reading as a data artifact. `python
      scripts/validate_data.py` passes; full test suite (150 tests, unchanged — data curation doesn't add
      tests) still green.
- [x] Erich von Manstein battles (WWII) — 5 rows (Operation Trappenjagd/Kerch Peninsula, Siege of
      Sevastopol/Operation Stoerfang, Third Battle of Kharkov, Zhitomir-Berdichev Offensive,
      Korsun-Cherkassy Pocket) in `data/battles.csv` plus a `generals.csv` row; `era=WWII`,
      `tech_era_tier=5` matching Zhukov/Eisenhower/Rommel, `resource_backing_tier` declining 3→4→3→2→1
      tracking Germany's real 1942-44 collapse. Delegated a research pass first (candidate battles
      across the full 1939-44 career, command attribution, casualty-sourcing gaps flagged), then
      independently re-ran `scripts/scrape_wikipedia_infobox.py` on every candidate myself plus several
      further web searches to cross-check every figure against named academic sources (Forczyk's
      *Where the Iron Crosses Grow*/*Sevastopol 1942*, Glantz's *From the Don to the Dnepr* and his
      translated Soviet General Staff Study *The Battle for the Ukraine*, Citino's *The Wehrmacht
      Retreats*, Barratt's *Zhitomir-Berdichev*, Nash's *Hell's Gate*, Zetterling & Frankson's *The
      Korsun Pocket*) before writing rows — `source_citation` names those historians, never
      "Wikipedia" alone. Deviation/judgment call, the central one: 5 rows is this dataset's thinnest
      roster (tied with Scipio Africanus/Subutai), a documented consequence of the no-fabrication bar
      cutting unusually hard here — dropped Operation Citadel's southern pincer (Kursk, Army Group
      South sector) despite Manstein clearing the personal-command bar *more* cleanly than Zhukov's
      excluded Stavka-coordinator role at the same battle, purely because no source gives a casualty
      figure isolated to Army Group South's push (only whole-Kursk or single-corps-subset totals
      exist) — flagged in `generals.csv`'s note as the biggest omission for Phase 7's eventual
      sanity-pass re-run. Also dropped Operation Winter Storm (German casualties known, no Soviet
      figure found) and the Fourth Battle of Kharkov (the commonly-cited casualty figure turned out on
      checking to be Soviet losses for a broader offensive, not this battle specifically) under the
      same rule, plus the 1939 Polish campaign (chief-of-staff, not command) and the 1940 France
      campaign (authored the Manstein Plan but his own corps command is undocumented at
      engagement-level) on command-attribution/no-fabrication grounds. Third Kharkov's own_casualties
      (11,500) is itself flagged as a known-partial SS-Panzer-Corps-only figure, not a full
      Army-Group-South total — same "documented floor, not a full count" treatment already used for
      several Genghis Khan/Saladin rows. Korsun-Cherkassy's enemy_casualties (80,188, the Soviet
      General Staff Study's own figure) is flagged as disputed/likely-inflated by Zetterling &
      Frankson's modern statistical study, with no clean replacement figure found — same "document the
      disagreement, don't silently resolve it" precedent as Zhukov's Operation Mars/Rommel's Second
      Alamein. Net record is 3 wins (2 Rout-level: Kerch, Sevastopol) / 2 losses (Zhitomir-Berdichev,
      Korsun-Cherkassy, both in the 1943-44 Ukraine retreat) — matches historian consensus of Manstein
      as operationally brilliant through early 1943 followed by a losing fighting withdrawal that got
      him dismissed by Hitler in March 1944. `python scripts/validate_data.py` passes; full test suite
      (150 tests, unchanged — data curation doesn't add tests) still green.
- [x] Douglas MacArthur battles (WWII) — 6 rows (Philippines Campaign 1941-42, Buna-Gona, Salamaua-Lae,
      Hollandia, Leyte, Manila) in `data/battles.csv` plus a `generals.csv` row; `era=WWII`,
      `tech_era_tier=5` matching Zhukov/Eisenhower/Rommel/Manstein. Delegated a research pass first
      (candidate battles across the full 1941-45 Pacific/SWPA career, command attribution,
      draft strength/casualty figures per battle), then cross-checked every figure by hand via
      `scripts/scrape_wikipedia_infobox.py` (hit Wikipedia API rate-limiting mid-run, same as the
      Robert E. Lee task — spaced calls out rather than retry-looping) plus web research against
      named official U.S. Army Center of Military History volumes (Morton's *The Fall of the
      Philippines*, Milner's *Victory in Papua*, Miller's *CARTWHEEL: The Reduction of Rabaul*,
      Smith's *The Approach to the Philippines* and *Triumph in the Philippines*, Cannon's *Leyte:
      The Return to the Philippines*) plus Morison's naval-operations volumes, D. Clayton James's
      *The Years of MacArthur*, and Drea's *MacArthur's ULTRA* — `source_citation` names those
      historians/official histories, never "Wikipedia" alone. Deviation/judgment call, the big one:
      **excluded MacArthur's Korean War command (1950-51) entirely**, even though it contains his
      single cleanest personal-command case of his career (Inchon) and its mirror-image disaster
      (the Yalu advance/Chinese intervention) — the schema's `era` field is one value per general,
      not per battle, and the ERAS enum has no Korean War bucket; adding one would be a schema
      change beyond this task's scope and would immediately recreate the singleton-era-cohort
      z-scoring problem already flagged for Frederick/Napoleon/Grant/Zhukov in Phase 5. Per
      SCOPE.md's "don't expand scope mid-run to chase a nice-to-have field" guidance, kept
      WWII-only and documented Korea as a candidate for a future schema decision rather than
      deciding it unilaterally — full reasoning in `generals.csv`'s note. Also excluded, on the
      established personal-command bar: Kokoda Track (Blamey's own relief of subordinates, no
      documented MacArthur decision) and the Battle of the Bismarck Sea (Kenney's air-interdiction
      battle against a convoy, also a poor fit for the schema's troop-strength fields with no
      comparable ground force on either side); the broader Battle of Luzon campaign is excluded as
      a standalone row to avoid double-counting the included, better-documented Manila row within
      it (same treatment as Gazala absorbing Tobruk elsewhere in this dataset). Manila's ~100,000
      Filipino civilian deaths are deliberately kept out of the enemy_casualties/own_casualties
      fields (an atrocity inflicted by the defending garrison on the city's population, not a
      combatant loss on either side) and noted in the row's `notes` instead of forced into a field
      the schema has no room for. `resource_backing_tier` set per-row on a rising 1→5 curve
      (Philippines 1941-42 cut off under "Europe First" to Manila 1945's peak Pacific material
      superiority), same per-row approach as Grant/Eisenhower. Roster size (6) matches the same
      structural shortfall already documented for Zhukov/Eisenhower. Net record is 5 wins (3
      Rout-level: Hollandia, Leyte, Manila; 1 Pyrrhic: Buna-Gona) / 1 loss (Rout-level: the
      Philippines 1941-42, the worst single defeat of his career) — a dramatic arc from
      catastrophic early defeat to increasingly lopsided victories as US material superiority grew,
      matching historian consensus. `python scripts/validate_data.py` passes; full test suite (150
      tests, unchanged — data curation doesn't add tests) still green.
- [x] Re-run full pipeline against the 19-general roster: `python scripts/validate_data.py`,
      `pytest`, then re-run every `scripts/render_*.py` script to regenerate
      `output/viz/*.png`/`*.csv`/`*.html` from the expanded dataset (old output is stale the
      moment a new general lands). Re-run Phase 7's sanity pass against the new composite
      ranking/category tables — in particular check whether the n=2-era-cohort z-scoring issue
      flagged for Caesar (see Notes above) resolves now that Ancient/Medieval/WWII cohorts have
      more members; log findings in Notes below, do not hand-tune weights. — validate passes;
      full suite 150/150 unchanged; all four `render_*.py` scripts re-ran clean against the
      19-general/178-row dataset (`ranking_tables.py`'s Monte Carlo pass took >2min so it ran in
      the background, no code issue). Sanity pass: the original Caesar n=2 artifact *is* resolved
      (Ancient now has 4 members: Caesar/Alexander/Hannibal/Scipio; Medieval 4:
      Genghis/Saladin/Subutai/Tokugawa; WWII 5: Zhukov/Eisenhower/Rommel/Manstein/MacArthur — none
      are forced-mirror n=2 pairs anymore), but the *same* mechanical issue reappeared in three
      different eras: Early Modern (Frederick+Washington), Napoleonic (Napoleon+Wellington), and
      Industrial (Grant+Lee) each grew from a singleton to exactly 2 members, so those three pairs
      now show the identical exact-mirror-magnitude artifact Caesar/Alexander had before
      (Frederick 0.85 / Washington -0.85, Napoleon -0.70 / Wellington 0.70, Grant 0.85 / Lee
      -0.85 — mathematically guaranteed for any 2-member population: z always resolves to exactly
      ±1 regardless of how large or small the real gap between the two is). Full writeup with the
      math and the rest of the findings (Rommel's last-place finish, Eisenhower's #1) in Notes
      below — no weights touched.

## Notes / deviations — Phase 2b sanity re-pass (19-general roster)

- **Pipeline re-run, clean**: `python scripts/validate_data.py` passes on the full 178-row/
  19-general dataset; `pytest` is still 150/150 (data curation tasks don't add tests, per
  established convention); all four `scripts/render_*.py` scripts ran without error and
  overwrote the stale (8-general, this-morning) `output/viz/*` files. `render_ranking_tables.py`
  took long enough (Monte Carlo resampling over ~4x the rows) to exceed the interactive command
  timeout and finished in the background — that's a runtime characteristic, not a bug; its fixed
  `MC_SEED` means the output is still fully reproducible.
- **The n=2-era-cohort exact-mirror artifact, previously flagged for Caesar/Alexander, is
  resolved for Ancient/Medieval/WWII but has mechanically reappeared in three other eras.**
  Ancient grew from 2 to 4 members (Caesar, Alexander, Hannibal, Scipio), Medieval from 2 to 4
  (Genghis, Saladin, Subutai, Tokugawa), and WWII from a 1-member singleton to 5 (Zhukov,
  Eisenhower, Rommel, Manstein, MacArthur) — none of those cohorts force the old ±1.0-mirror
  z-score anymore, and Zhukov's composite score is no longer mechanically pinned at exactly 0.0.
  But Early Modern (Frederick + Washington), Napoleonic (Napoleon + Wellington), and Industrial
  (Grant + Lee) each grew from a 1-member singleton to *exactly* 2 members — one new general
  added per era, no more — which reproduces the identical structural issue `composite.py`'s
  docstring already names for n=2 cohorts. Confirmed against the regenerated
  `output/viz/ranking_tables_composite.csv`: Frederick 0.85 / Washington -0.85, Napoleon -0.70 /
  Wellington 0.70, Grant 0.8499999999999984 / Lee -0.8500000000000015 (floating-point noise on an
  exact 0.85) — every pair's composite magnitude matches exactly. This isn't a coincidence of
  this particular data; it's guaranteed by the math. For any 2-value population {a, b} with
  population std (`ddof=0`), the deviation of each point from the mean is ±(a-b)/2 and the
  population std is |a-b|/2, so z = deviation/std is always exactly ±1 regardless of how large or
  small the real gap between a and b is. `_z_scores_within_era` in `war/metrics/composite.py`
  (lines 81-102) does exactly this per metric per era, so any 2-member era cohort will always
  produce mirror-magnitude z-scores, and therefore mirror-magnitude composite scores when the
  other three inputs happen to agree in sign (as they do for two of these three pairs — see
  below). **Practical read**: within an n=2 pair, the *sign* (who ranks above whom) is still
  meaningful and, for these three pairs, matches historian consensus (Washington's overall record
  is weaker than Frederick's; Wellington's largely-undefeated run edges Napoleon's mixed one
  including the Russian disaster and Waterloo; Grant's material-advantage-backed record edges
  Lee's harder fight against it) — but the *magnitude* (0.85, 0.70) is mechanically forced and
  not comparable across eras or informative about the size of the real quality gap. This is the
  same limitation already documented in Phase 5/Phase 7's original notes, just relocated to new
  generals by the specific shape of this roster expansion (one general added per already-thin
  era rather than several) — not a new bug, not something to weight-tune around per SCOPE.md's
  explicit instruction, and expected to keep recurring for any era that stays at exactly 1-2
  members. Noted here rather than patched.
- **Julius Caesar's own placement (17th of 19, composite -0.90) no longer traces to the n=2
  artifact, but is still worth a second look.** With Ancient now at n=4, Caesar's z-scores are a
  real 4-way comparison, not a forced mirror of Alexander. Checked his category placements
  directly: `casualty_efficiency` 5th of 19 (good), `squander_index` 8th (tied-good, 0.0, no
  squandered wins), `clutch_rating` 11th (mid-pack), `win_rate` 13th (0.73, respectable) — none of
  these are last-place. The two inputs actually pulling his composite down are `opponent_adjusted_
  rating` (14th of 19 overall, and lowest of the four Ancient generals specifically) and
  `war_residual` (-0.104, with a tight CI of -0.109 to -0.095 that doesn't cross zero, so it isn't
  Monte Carlo noise). Both are real, not artifacts of the z-scoring bug. A plausible explanation,
  not confirmed: this file's Phase 5 notes already document that off-roster opponents (most of
  Caesar's — Gallic tribes, various Roman rivals with no `generals.csv` row of their own) get a
  default rating in the OAR solver rather than a curated one, and Caesar's battles skew unusually
  heavily toward off-roster opponents compared to Alexander/Hannibal/Scipio, who fought more of
  each other or better-documented Successor-era commanders. That would understate his OAR without
  it reflecting a real quality gap — but this is a hypothesis, not a verified root cause, and
  fixing it (curating ratings for two dozen ancient tribal/political opponents) is a data-sourcing
  effort beyond this task's scope. Flagged as a candidate follow-up, not acted on.
- **Rommel finishes dead last (19th of 19, composite -1.24), just below Saladin.** Re-checked
  against the reasoning already logged at data-entry time (see the Erwin Rommel entry above):
  `win_rate` 17th (0.44), `opponent_adjusted_rating` 18th, and `squander_index` worst in the whole
  roster (0.5, tied-worst previously held by Frederick at 0.44 in the 8-general run) all trace to
  the same documented back-half-of-the-desert-campaign losing streak from Alam el Halfa through
  Second Alamein — a real historical pattern this dataset's 9-row roster happens to weight toward
  (it doesn't include his earlier, more successful 1941 battles as heavily). Historian consensus
  rates Rommel as a top tactician whose campaign nonetheless ended in strategic defeat — a
  last-place *composite* finish for a campaign-scoped dataset is consistent with that, not a
  contradiction of it. No action taken; this is the same "matches consensus, not an artifact"
  call already made once for this general.
- **Eisenhower ranks 1st overall (composite 1.29), ahead of Alexander (2nd, 0.90).** This doesn't
  trip SCOPE.md's named bug-check ("does anyone universally considered a poor commander rank
  #1?") — Eisenhower is a well-regarded commander, so a surprising #1 isn't the same as a wrong
  #1. But it's worth flagging as likely driven by roster composition rather than a uniquely
  dominant record: his 6 rows are all wins (`decisive_win_rate`=1.0) in Allied campaigns fought
  with growing material superiority, giving the highest `opponent_adjusted_rating` of any WWII
  general (1872.7, above Zhukov/Manstein/MacArthur/Rommel) and a solidly positive `war_residual`
  even after controlling for that superiority — this is the same "thin roster, all wins" shape
  already flagged as a structural shortfall for Eisenhower/Zhukov/MacArthur at data-entry time,
  not a new problem, just now visible in the composite ranking's top slot instead of a category
  table. Left as-is per SCOPE.md's "do not hand-tune weights" instruction — the underlying data is
  honestly sourced, and the composite formula is doing exactly what it's documented to do with it.
- **No universally-recognized poor commander ranks at the top, and no universally-recognized great
  commander ranks unaccountably at the bottom relative to their own documented record in this
  dataset** — the two names at the extremes (Eisenhower #1, Rommel #19) both trace to real,
  already-documented data/roster characteristics rather than a pipeline bug. This closes out the
  re-run of Phase 7's sanity-pass instruction for the 19-general roster; no weights were changed.
