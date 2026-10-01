# Progress: scalable data ingestion

The first build (19 hand-curated generals, 177 battles, all metrics, rankings, visuals) is done.
Its task log is archived at `notes/PROGRESS-v1.md`; read it only if you need to know why
something in `war/` looks the way it does.

Goal of this run: replace per-battle agent research with a cheap, deterministic pipeline so the
database can grow to hundreds of generals, then re-run the rankings and visuals on the result.

## Priorities for choosing a method (in order)

1. **Cost and latency.** No agents doing per-battle research or per-battle web lookups. Code runs
   in seconds-to-minutes per thousand battles. The only LLM use allowed is task C5 below.
2. **Exhaustiveness and consensus.** Prefer one source that covers many battles over stitching
   many APIs together. Cross-reference a second source only if it is a cheap file join.
3. **Historical accuracy.** Not a dealbreaker. Numbers within a factor of 2-3 are probably fine for
   ranking; task A5 measures how true that is instead of assuming it. Do not spend effort
   reconciling historians' disagreements.

### How to apply the priorities

- **Floor first, then the order.** A method must clear the quality floor below before the
  priorities rank it. Among methods that clear the floor, choose the cheapest and fastest. If
  costs are within the same order of magnitude, call it a tie and pick the one with broader
  coverage (priority 2). Accuracy only breaks a remaining tie.
- **Default floor** (measured against the gold set with `scripts/eval_ingest.py`): troop strength
  within 3x of the gold value on at least 75% of rows where both exist, and strength present for
  both sides on at least 60% of the battles that go into the dataset. Casualties may be sparse:
  report the null rate and keep the field only if at least 40% of rows have it. Task A5 may
  move these numbers, but only with the measured reason written in Notes. Do not lower the
  floor to make a method pass; pick a different method or flag it.
- **Time-box.** One iteration per method comparison. If a source is blocked, rate-limited, or
  unclear after a reasonable try, note it and move on to the next best option. Do not gold-plate:
  stop improving the extractor once another fix moves the gold-set numbers by less than about 2
  points.
- **Run limits for C5** (change only with a note): at most 3,000 rows and 60 CLI calls in total.

### Archiving datasets between experiments

When you try a different source, floor, parser version, or roster rule and it replaces the
current dataset, do not overwrite or delete the old one. Move it to
`data/archive/<YYYY-MM-DD>-<short-label>/` (for example `2026-10-02-wikipedia-api-floor75`).
Each archive directory gets a `README.md` saying what it is: the source and method, the floor and
settings used, row and general counts, its `eval_ingest.py` scores against the gold set, and why it
was replaced. Add one line per archive to `data/archive/INDEX.md` (path, date, one-sentence
purpose), and record the reasoning in the dev log notes. Keep the gold set in `data/` untouched.
Large raw caches stay in `data/raw/` (gitignored) and are not archived; archive only the
generated CSVs.

### How much to ingest

The agents decide the methods, then ingest as much as the pipeline can do within these
constraints. Aim for the low hundreds of generals (about 200-400). Do not pad the roster with
generals whose battles have thin or missing numbers just to hit a count. If fewer than 100
generals clear the floor, stop and flag it in Notes instead of lowering the floor.

## Decisions already made (do not re-ask)

- The 19 hand-curated generals in `data/` stay untouched as a gold set. New pipeline output goes
  to a separate directory (`data/auto/`). The gold set is the benchmark the pipeline is scored on.
- Schema may change: allow missing casualties/strength, replace hand-judged fields with rules, drop
  `source_confidence` and `political_constraint_flag`. Update metrics, validator, and tests to match.
  The gold set is migrated mechanically, not re-researched.
- Deterministic parsing first, hard. Rows that regex cannot parse are collected into one queue and
  handled in a single bounded pass with the Claude CLI on the lowest model and lowest effort
  setting (task C5). If no CLI auth is available in the sandbox, skip C5, drop or null those
  fields, and note it.
- Reference implementation to study: github.com/ethanarsht/military_rankings (the code behind the
  "Napoleon was the best general ever" Medium article). It crawls Wikipedia "List of battles"
  pages, then scrapes each battle page. It also has hand-entered strength spreadsheets, so strength
  extraction was not fully automatic there. The repo is huge (about 1,000 cached HTML pages): use
  `git clone --depth 1 --filter=blob:none --sparse` and fetch only the `.ipynb`, `.py`, and `.csv`
  files you need.
- Known from a previous probe (23 battles, regex only): troop strength matched within 25% about
  75% of the time, casualties only about 45-50%. Wikidata has no strength or casualty data, so it
  is only useful for ids, dates, and places. "What links here" finds every battle for a general but
  with poor precision; use the infobox `commander` field instead. Wikipedia rate-limits at 429, so
  throttle and cache raw pages under `data/raw/` (gitignored).
- Candidate extra sources to test cheaply, not to depend on: CDB90 (github.com/jrnold/CDB90, 600+
  battles 1600-1973, strength/losses/victor, commanders with Wikipedia uris per A4), Correlates of War National Material
  Capabilities (CINC score per state-year from 1816, a proxy for resource backing).

## Phase A: Decide the method (measure, then write down the choice)

- [x] A1. Study `ethanarsht/military_rankings`: how it builds the battle list, extracts infobox
      fields, and codes results. Record what to reuse and what to avoid, plus its license.
      Findings in `~/notes/war-analyzer/ingestion.md`: no root LICENSE (code is all-rights-
      reserved, don't copy verbatim, techniques aren't copyrightable so reuse ideas only); reuse
      its battle-list-page structure (7 era pages, bullets vs wikitables) and infobox field
      names/positions; do NOT reuse its result coding or strength/casualty parsing — both were
      hand-labeled/manual there, not automated, so ours has to be real code (C2/C3); avoid its
      per-commander-page HTTP fetch for canonicalization, use the anchor's own `title` attribute
      instead.
- [x] A2. Pick the Wikipedia access method by measuring: throttled API versus enwiki dump versus
      DBpedia. Compare time for 1,000 pages, completeness of infobox fields, and setup effort.
      Reuse or extend `war/scrape.py` where it fits.
      Decision in `~/notes/war-analyzer/ingestion.md`: batched `action=query` (up to 50
      titles/call) over one-page-per-call — same wikitext/field completeness, ~50x fewer HTTP
      round trips (~1,000 calls -> ~20 for 1,000 pages). Added `war.scrape.fetch_wikitext_batch`
      with exponential backoff on HTTP 429 (both methods hit 429 unpredictably in this sandbox,
      even on the first batched call) and unit tests (mocked `urlopen`, no network). Rejected
      enwiki dump (26.8GB compressed for ~7M pages to get ~1-3k battles — fails cost/latency) and
      DBpedia (has strength/casualty predicates but values are unlabeled per-side and fragmented
      with sub-counts like artillery pieces; not a cheap join, would need as much parsing work as
      the wikitext infobox with worse structure, plus IPv6-only endpoint unreachable in this
      sandbox without forcing IPv4).
- [x] A3. Build `scripts/eval_ingest.py`: runs the extractor on the 177 gold battles and reports, per
      field, coverage and the share within 1.5x, 2x, and 3x of the gold value (use log error, not
      percent). Everything later is scored with this.
      Full findings in `~/notes/war-analyzer/ingestion.md`. Since C1-C2's real extractor don't
      exist yet, scored a naive "first number in the field" regex parser defined in the script
      itself as a baseline/floor, not the production extractor. Side assignment (own/enemy vs.
      combatant1/2) also doesn't exist yet (C3), so the script tries both orientations per battle
      and keeps the lower-error one — makes these numbers an optimistic upper bound, not a
      prediction of C7's eventual score. Results (177 rows, battle_name as-is as the Wikipedia
      title): page found 155/177 (88%); own/enemy troop strength 66%/65% coverage, 89% within 3x;
      own/enemy casualties 58%/62% coverage, 71%/78% within 3x. Clears the default quality floor
      comfortably on strength and is at-or-above it on casualties coverage, with the real C2
      extractor and C3 side-matching still to come.
- [x] A4. CDB90 join test: download it, join to the gold set by name and date, report agreement and
      coverage. Check whether it has commanders and what its license is. Check COW CINC
      availability. Keep a source only if joining it is cheap.
      Full findings in `~/notes/war-analyzer/ingestion.md`. Cloned CDB90 (small, ~5MB, no sparse
      checkout needed); joined by deriving a Wikipedia title from its `dbpedia` URI column and
      exact-matching gold `battle_name`: 50/177 gold rows matched (CDB90 only covers 1600-1973, a
      fixed list of 660 battles). On the matched rows, agreement with gold is far above the A3
      Wikipedia-regex baseline: strength 100% within 3x (94% within 1.5x), casualties 95% within
      3x. CDB90 does have commanders (1,358 rows, 74% with a ready-made Wikipedia `uri`) —
      corrects PROGRESS.md's earlier note that it doesn't. License: data odc-by, original source
      public domain, code BSD-3, no blocker. COW CINC (`NMC-70-abridged.csv`) downloads directly,
      has `ccode/year/cinc` from 1816, confirms B2 is buildable. Decision: the join is cheap, but
      CDB90's fixed 660-battle list can't replace Wikipedia as the primary source (fails
      exhaustiveness at the scale this run targets) — recommend it as an optional accuracy
      override in C2/C6 for battles that match, not a dependency. Wiring left to C2/C6; A4 is
      measurement only.
- [x] A5. Sensitivity test: perturb the gold set's numbers by random log-normal factors (about 1.5x,
      2x, 3x) over many trials and measure how much the composite ranking moves (rank correlation,
      top-5 stability). Write down the error level the ranking tolerates. This sets the quality
      bar for everything below.
      Built `scripts/sensitivity_test.py` (300 trials/level on the 177-row gold set). Finding in
      `~/notes/war-analyzer/ingestion.md`: the ranking tolerates strength/casualty error up to at
      least 3x log-error with almost no movement (mean Spearman >=0.998, top-5 unchanged in
      97-99.7% of trials) — because 3 of 4 composite inputs (OAR, decisiveness, longevity) are
      outcome-only and mathematically can't move from this kind of noise, and the 4th
      (war_residual) is a pooled-OLS, per-general-averaged residual that partly cancels per-battle
      noise. Decision: keep A6's quality gate at PROGRESS.md's existing default floor rather than
      loosening it — this test shows the ranking doesn't need tighter accuracy, not that the
      ingested data can be less honest/usable for other purposes.
- [x] A6. Write the decision: chosen source(s), measured numbers from A2-A5, and the pass/fail
      thresholds for the ingest quality gate (task C7). Put it in the dev log.
      Decision recorded in `~/notes/war-analyzer/ingestion.md`: Wikipedia batched API (A2) as
      primary source, `military_rankings` page-structure ideas only (A1, no code reuse), CDB90
      (A4) as an optional accuracy override for 1600-1973 battles that join, COW CINC (A4)
      confirmed for B2's resource-backing tier. C7's gate is PROGRESS.md's existing default floor
      unchanged (A5 showed the ranking tolerates far worse, but that's not grounds to loosen it —
      the floor protects data honesty beyond this one ranking formula): strength within 3x on
      >=75% of rows where both sides exist, strength present both sides on >=60% of battles,
      casualties kept only if >=40% coverage. A3's naive-parser baseline already clears all three
      (89%/89% within 3x, 58-62% coverage) so C2's real extractor has a concrete bar to beat.

## Phase B: Simplify the schema

- [x] B1. Schema change: nullable strength/casualty fields, drop `source_confidence` and
      `political_constraint_flag`, decide on `objective_secured`, add a per-field low/high range
      for when two sources disagree. Migrate the gold set mechanically. Validator and schema tests green.
      Made all four strength/casualty columns `required=False` and added an optional `_low`/`_high`
      sibling pair for each (8 new columns); `validate.py` gained `validate_ranges` to check
      `low <= high` and that a recorded point estimate falls inside its own range. Dropped
      `source_confidence` and `political_constraint_flag` outright (decided in A6, unused outside
      schema/records). Decision on `objective_secured`: dropped it too, not just left alone — unlike
      `decisiveness`, which C2 can read off a Wikipedia infobox result string by rule, "was the
      general's stated objective achieved" has no deterministic source and would stay a permanent
      manual judgment call. `rate.py`'s `decisive_win_rate` now derives the identical concept from
      `decisiveness` (Strategic/Rout = converted, same split `squander.py` already used, wins with no
      label excluded from both num/denom). This forced `uncertainty.py`'s Monte Carlo off the old
      confidence-tag noise model onto the new low/high ranges (uniform sample in `[low, high]` when
      both present, point estimate trusted otherwise) — functionally this is B3's "Monte Carlo uses
      source ranges instead of confidence tags" bullet, done now because leaving `source_confidence`
      referenced after deleting the column would crash the whole metrics suite, not a decision to
      skip ahead on B3's other work (missing-value policy for rate.py/war_residual.py when strength
      is genuinely null — nothing in the gold set exercises that yet, so left for B3). Gold set
      (`data/battles.csv`, 177 rows) migrated mechanically: 3 columns dropped, 8 empty columns added,
      no values re-researched. `validate_all()` returns `[]`; full suite (178 tests across all of
      `tests/` and `war/`, including every file that constructs a `Battle` by hand) green.
- [x] B2. Rules in place of hand judgment: `tech_era_tier` from a date lookup table,
      `resource_backing_tier` from COW CINC after 1816 and a coarse per-era default before that
      (only if A4 shows CINC is cheap to load), `decisiveness` from the infobox result text.
      Added `war/rules.py` (standalone, not yet wired into any pipeline — C2/C6 are what call
      these once they exist) with three functions plus tests in `tests/test_rules.py`:
      `tech_era_tier_for_year` (plain 5-step year lookup, boundaries at 1400/1700/1860/1914);
      `resource_backing_tier` (COW CINC quintile-rank-within-year when year>=1816 and a
      country/table are given, else a per-era default); `decisiveness_from_result` (regex over
      the infobox `result` string, keyed off the already-known `outcome` — see module docstring
      for the keyword table). Re-downloaded COW CINC v7 (A4's source) since the A4 clone wasn't
      persisted; added `scripts/fetch_cow_cinc.py` to make `data/raw/cow_cinc/` reproducible
      since `data/raw/` is gitignored. Gold set (`data/battles.csv`) untouched, per A6's decision
      that it's the benchmark, not a target to regenerate. Full suite + doctests green (192
      passed); validator still passes (schema unchanged, no new columns). Decisions recorded in
      `~/notes/war-analyzer/ingestion.md`: the tech-era year breakpoints, the per-era
      resource-backing defaults, and the decisiveness keyword mapping are all judgment calls with
      no single authoritative source — written down there with the reasoning so they can be
      revisited.
- [x] B3. Metrics handle missing values (define the policy: drop the row, impute, or fall back per
      metric) and Monte Carlo uses source ranges instead of confidence tags. Tests green. Log the
      gold-set ranking before versus after the schema change.
      Monte Carlo/ranges half was already done in B1 out of necessity. This pass covered the
      other half: `raw.py` totals and `rate.py`'s `casualty_exchange_ratio` now sum only the rows
      that carry each field (impute by omission, `None` when zero rows do); `rate.py`'s
      `avg_force_ratio_faced` and `war_residual.py`'s OLS fit drop rows missing a strength field
      (no partial force ratio/regression row exists); `clutch.py` falls back to the
      resource-tier condition alone when strength is missing. Full reasoning and the
      per-metric table in `~/notes/war-analyzer/ingestion.md`. 10 new tests across
      `test_metrics_raw.py`/`rate.py`/`war_residual.py`/`clutch.py` (202 total, all green);
      `scripts/validate_data.py` and `scripts/eval_ingest.py` unaffected (schema/extractor
      untouched); `composite_ranking` on the gold set is byte-identical before/after
      (Eisenhower 1st, Rommel last) since the gold set has no missing values yet — confirms this
      is a true no-op until real nulls exist.

## Phase C: Build the pipeline

- [x] C1. Battle universe: crawl Wikipedia "List of battles" pages into a battle URL list. Cached,
      throttled, resumable.
      Added `war.scrape.extract_battle_titles` (keyword filter over every `[[wikilink]]` on a
      list page, reusing A1's keyword set; works unchanged on both the bullet-list and
      wikitable markup these pages mix) and `scripts/build_battle_universe.py`, which fetches
      the 7 list pages (`LIST_OF_BATTLES_PAGES`), caches their wikitext at
      `data/raw/battle_universe_cache.json`, and writes the deduped candidate titles to
      `data/raw/battle_universe.csv`. Real run: 7/7 pages fetched, 8,824 candidate titles;
      rerun hit the cache (2s, no network) confirming resumability. This is a recall-oriented
      candidate list, not a verified one — known misses are non-keyword battle names (e.g.
      ancient sites like "Jebel Sahaba") and false positives like nav links ("List of sieges",
      explicitly excluded) or campaign pages with no military-conflict infobox; C2's extractor
      is the precision filter on this list, not this script. 8 new tests in
      `tests/test_scrape.py` cover keyword filtering, dedup, fragment-stripping, namespace
      exclusion, and both markup shapes. Full suite green (210 passed). No schema/extractor
      change, so `validate_data.py`/`eval_ingest.py` don't apply to this task.
- [x] C2. Deterministic infobox extractor with unit tests. Cover at least: ranges, "c."/"~", k/m
      suffixes, multi-segment fields, plainlist/ubl templates, killed/wounded/captured sums,
      per-nation breakdowns, qualitative words ("heavy", "light") become null. Add a test for each
      failure mode that A3 shows.
      Pulling real wikitext (Waterloo/Borodino/Pharsalus, already cached from A3) showed the old
      `parse_military_infobox` had a real truncation bug beyond anything A3's naive-parser numbers
      exposed: its param splitter used a `(?=\n}}|\Z)` lookahead that stops at the *first* `}}` it
      sees, which is wrong as soon as a field's value contains a nested template (a `{{efn|...}}`
      multi-estimate citation, a `{{ubl|...}}` breakdown) whose own closing `}}` comes first —
      confirmed it silently cut off Waterloo's `strength1` mid-citation. Fixed at the root: added
      `war/wikitext.py` (brace-depth-aware `balanced_template_end`/`split_top_level`/
      `strip_templates`) and rewrote `war/scrape.py`'s body/param splitting
      (`find_infobox_body`/`split_infobox_params`) to track nesting depth instead of guessing from
      the next literal `}}`. `parse_military_infobox`'s own output contract (dict of cleaned
      strings) is unchanged and its existing tests pass unmodified, so this is a drop-in
      correctness fix for every field, not just the numeric ones — `eval_ingest.py`'s naive-parser
      baseline shifted slightly (coverage down ~2pts e.g. own_troop_strength 66%->64%; within-3x
      shares essentially unchanged) now that it's reading correctly-bounded text instead of
      occasionally over-scanned text that happened to contain a lucky number.
      Built `war/infobox_numbers.py` for the real numeric parse (kept separate from
      `parse_military_infobox`'s generic text cleanup, which collapses whitespace and deletes
      templates in ways that lose exactly the structure numbers need). Pipeline per field: strip
      citation/footnote wrapper templates whole (`efn`/`efn-lr`/`sfn`/`sfnp`/`sfnm`/`cite*`/
      `#tag:ref`/etc. — recursing into kept templates so a citation nested inside a kept `{{ubl}}`
      still gets removed), substitute small inline templates (`{{approximately|X}}`, `{{circa}}`,
      `{{ndash}}`, `{{*}}`, `{{tree list}}`), unwrap `{{ubl|...}}`/`{{plainlist|...}}`/
      `{{bulletedlist|...}}` into one item per line, drop equipment-only segments ("40+ cannon",
      "20 ships" — not personnel), then decide per field: if the first parseable segment is a bare
      number/range (optionally "Total: ..."), trust it alone — real infobox fields almost always
      state the headline total first, with everything after it being an alternative citation, a
      breakdown of that same total, or a different unit, never an addend; summing it in would
      double-count. Only when the first parseable segment *isn't* bare (names a casualty category,
      "500 killed"; a unit type, "7,000 infantry"; or a per-nation "<label>: <number>" line) is
      there no stated total, and every parsed segment is summed — this is what makes
      killed/wounded/captured and per-nation breakdowns work. Verified this rule against every real
      example pulled (not just synthetic fixtures) before trusting it, including Waterloo's
      genuinely brutal `strength2`/`casualties1` fields (nested `{{tree list}}`/`{{Ubl}}`/`{{efn}}`
      several layers deep) — all four fields on all three battles came out matching the
      well-known historical headline figures. One real bug caught this way, not from a synthetic
      test: unwrapping a list template that directly abuts preceding text with no separator (e.g.
      a headline number immediately followed by `{{Ubl|...}}`) was concatenating the two into one
      unparseable segment; fixed by always prefixing an unwrapped list's items with `\n`.
      41 new tests in `tests/test_infobox_numbers.py` (one or more per named failure mode, plus
      integration tests against the real cached Waterloo/Borodino/Pharsalus text), 3 regression
      tests in `tests/test_scrape.py` for the truncation fix, and 5 doctests (`war/wikitext.py`,
      `war/infobox_numbers.py`); full suite 259 passed (210 + 49).
      `scripts/validate_data.py` still passes (schema untouched). `scripts/eval_ingest.py` doesn't
      score this module — it's wired in by C6/C7, not C2 — but was re-run anyway as a sanity check
      per the note above. Not yet wired into any pipeline (same "built standalone, C3/C6 call it
      later" pattern as `war/rules.py` from B2).
- [ ] C3. Commanders and sides: parse infobox commander links per side, set `opponent_general_id`,
      and invert into general to battles. A general counts as personally commanding a battle if
      they are listed first on their side (document this rule and its known misses).
- [ ] C4a. Seed roster: build a candidate list of a few hundred generals from online "top X
      generals in history" lists and similar published rankings, plus Wikipedia's lists of
      commanders and generals by era. Cache the source pages, record which list each name came
      from, and merge duplicates to Wikipedia page titles. This is a one-time scrape and a merge
      script, not research per general.
- [ ] C4b. Roster selection: for each seed, count battles from C3 that have usable strength
      figures, and keep generals with at least N such battles (pick N, record why). Opponents who
      appear in kept battles but are not on the seed list may join if they clear the same bar.
      Generate `generals.csv` automatically: era and career years from battle dates. The famous-names
      seeding favors generals people already rank highly. Record this bias in Notes, and keep
      lower-profile generals in when the data clears the bar.
- [ ] C5. Uncertain-row queue: collect every field regex could not parse into one file. Process the
      whole queue in a single bounded pass: `claude -p` on the lowest model and effort, chunked
      rows per call, a hard cap on total rows and calls, outputs checked against sanity bounds
      (no negative numbers, casualties not far above strength). Never one call per battle. Record the
      row count, call count, and rough cost.
- [ ] C6. Full run into `data/auto/`. Validator passes. Row counts and null rates per field logged.
- [ ] C7. Quality gate: score the pipeline against the gold set with `scripts/eval_ingest.py`
      using the thresholds from A6. If it fails, write why in Notes and stop (SCOPE.md "stop and
      flag"); do not move on to Phase D with bad data.

## Phase D: Rankings and visuals at scale

- [ ] D1. Run the metrics on `data/auto/`. Check runtime (Monte Carlo over hundreds of generals);
      fix it if it is too slow.
- [ ] D2. Ranking tables and the three scatter plots at hundreds of generals: tables show top N with
      full CSV alongside, scatter plots label only the extremes. Verify without a display, as in
      SCOPE.md Phase 6 (assert on output files and data).
- [ ] D3. Sanity pass on the new ranking against historian consensus. Flag likely bugs and roster
      artifacts; do not hand-tune weights. Compare against the gold-set ranking.
- [ ] D4. Update README.md with how to rerun ingestion and what the pipeline can and cannot do.

## Notes / deviations
(none yet)
