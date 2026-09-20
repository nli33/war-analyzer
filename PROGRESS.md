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
