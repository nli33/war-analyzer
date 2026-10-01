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
  battles 1600-1973, strength/losses/victor, no commanders), Correlates of War National Material
  Capabilities (CINC score per state-year from 1816, a proxy for resource backing).

## Phase A: Decide the method (measure, then write down the choice)

- [ ] A1. Study `ethanarsht/military_rankings`: how it builds the battle list, extracts infobox
      fields, and codes results. Record what to reuse and what to avoid, plus its license.
- [ ] A2. Pick the Wikipedia access method by measuring: throttled API versus enwiki dump versus
      DBpedia. Compare time for 1,000 pages, completeness of infobox fields, and setup effort.
      Reuse or extend `war/scrape.py` where it fits.
- [ ] A3. Build `scripts/eval_ingest.py`: runs the extractor on the 177 gold battles and reports, per
      field, coverage and the share within 1.5x, 2x, and 3x of the gold value (use log error, not
      percent). Everything later is scored with this.
- [ ] A4. CDB90 join test: download it, join to the gold set by name and date, report agreement and
      coverage. Check whether it has commanders and what its license is. Check COW CINC
      availability. Keep a source only if joining it is cheap.
- [ ] A5. Sensitivity test: perturb the gold set's numbers by random log-normal factors (about 1.5x,
      2x, 3x) over many trials and measure how much the composite ranking moves (rank correlation,
      top-5 stability). Write down the error level the ranking tolerates. This sets the quality
      bar for everything below.
- [ ] A6. Write the decision: chosen source(s), measured numbers from A2-A5, and the pass/fail
      thresholds for the ingest quality gate (task C7). Put it in the dev log.

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
- [ ] C4. Roster selection: keep generals with at least N battles that have usable strength figures
      (pick N, record why, aim for hundreds of generals). Generate `generals.csv` automatically:
      era and career years from battle dates.
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
