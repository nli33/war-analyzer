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

- [ ] B1. Schema change: nullable strength/casualty fields, drop `source_confidence` and
      `political_constraint_flag`, decide on `objective_secured`, add a per-field low/high range
      for when two sources disagree. Migrate the gold set mechanically. Validator and schema tests green.
- [ ] B2. Rules in place of hand judgment: `tech_era_tier` from a date lookup table,
      `resource_backing_tier` from COW CINC after 1816 and a coarse per-era default before that
      (only if A4 shows CINC is cheap to load), `decisiveness` from the infobox result text.
- [ ] B3. Metrics handle missing values (define the policy: drop the row, impute, or fall back per
      metric) and Monte Carlo uses source ranges instead of confidence tags. Tests green. Log the
      gold-set ranking before versus after the schema change.

## Phase C: Build the pipeline

- [ ] C1. Battle universe: crawl Wikipedia "List of battles" pages into a battle URL list. Cached,
      throttled, resumable.
- [ ] C2. Deterministic infobox extractor with unit tests. Cover at least: ranges, "c."/"~", k/m
      suffixes, multi-segment fields, plainlist/ubl templates, killed/wounded/captured sums,
      per-nation breakdowns, qualitative words ("heavy", "light") become null. Add a test for each
      failure mode that A3 shows.
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
