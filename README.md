# War Analyzer

A data analysis project that examines historical data about famous generals' battles (adjusted for reliability of sources) and attempts to create an all-time ranking. 

Would Napoleon beat prime Julius Caesar? Is Genghis Khan the GOAT? Find out.

This project was built entirely with Claude working autonomously overnight as an experiment. After iterating on an initial scope document, I left it running in a custom Ralph loop inside a VM.

## Two datasets

- `data/` — 19 hand-curated generals, 177 battles, each row sourced and cross-checked by hand.
  Small, trustworthy, the benchmark the automated pipeline is scored against.
- `data/auto/` — hundreds of generals, scraped and parsed automatically from Wikipedia with no
  per-battle research. Bigger and noisier; see "What the pipeline can't do" below before trusting
  any one row of it.

Rankings and visuals for the gold set live in `output/viz/`; the same outputs for `data/auto/`
live in `output/viz_auto/`. Setup: `pip install -r requirements.txt` (or `uv sync` against
`pyproject.toml`).

## Rerunning the metrics and visuals

No network access needed — this just reruns the metrics/viz code against whichever CSVs you point
it at. Each script defaults to the gold set and takes `--battles`/`--generals`/`--output` to
target `data/auto/` (or any other battles/generals CSV pair) instead. `--output` is the path of
the primary output *file* (sibling CSVs are derived from its name), not a directory:

```
python scripts/validate_data.py                     # schema check, run this first
python scripts/render_ranking_tables.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto/ranking_tables.html
python scripts/render_scatter_oar_resource_backing.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto/oar_vs_resource_backing.png
python scripts/render_scatter_tactical_strategic.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto/tactical_vs_strategic.png
python scripts/render_scatter_volume_efficiency.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto/volume_vs_efficiency.png
```

`render_ranking_tables.py` also takes `--top-n` (default 25, how many rows its HTML tables show)
and `--min-battles` (default 5, the floor below which a general's HTML row is dropped) — the CSV
outputs next to it are always the full set, every general, with a `battle_count` column.

## Rerunning ingestion (growing `data/auto/`)

The gold set (`data/`) is hand-curated and not meant to be regenerated. `data/auto/` is built by a
deterministic scrape → parse → roster pipeline with no per-battle web research or LLM calls (one
narrow exception below). Full design history and measurements are in
`~/notes/war-analyzer/ingestion.md` (via the `project-notes` skill); this is just the run order.
Each step caches its raw fetches under `data/raw/` (gitignored) and is resumable — rerunning after
a crash or interruption only fetches what's still missing.

```
python scripts/build_battle_universe.py        # C1: crawl Wikipedia's "List of battles" pages
python scripts/build_general_seed_roster.py    # C4a: crawl Wikipedia general/commander categories
python scripts/fetch_cow_cinc.py                # resource-backing tier input (COW CINC v7)
python scripts/build_roster_selection.py [--min-battles N]   # C4b: writes data/auto/generals.csv
python scripts/resolve_uncertain_fields.py      # C5: one bounded claude -p pass, see below
python scripts/build_auto_battles.py            # C6: writes data/auto/battles.csv
python scripts/eval_ingest.py                   # C7: score the real extractor against data/ (gold)
```

`resolve_uncertain_fields.py` is the **one** place this pipeline calls an LLM: a single bounded
`claude -p` pass (lowest model, lowest effort, batched rows, hard row/call caps in
`war/uncertain_fields.py`) over the queue of strength/casualty fields that have real infobox text
but that the regex extractor couldn't turn into a number. It is not used for research — it never
sees a battle it wasn't already looking at, and most of the queue (observed ~88%) resolves to
`None` for free before any model call happens, because the text has no digit in it at all.

`eval_ingest.py` is the quality gate: it reruns the real extractor against the 177-row gold set
and reports coverage and accuracy. The thresholds it's checked against (and why) are in
`~/notes/war-analyzer/ingestion.md`'s Phase A notes and PROGRESS.md's "Priorities for choosing a
method" section.

## What the pipeline can and can't do

**Can:** turn a Wikipedia battle infobox into structured strength/casualty numbers (handling
ranges, "c."/"~", k/m suffixes, nested citation templates, per-nation breakdowns), identify each
side's primary commander, and build a general roster and battle dataset at a scale (hundreds of
generals) that hand-curation can't reach — all without per-battle research. `scripts/eval_ingest.py`
shows it clears this project's accuracy floor against the hand-curated gold set.

**Can't (known, unfixed, as of the last run):**
- **No sample-size weighting in the composite ranking.** A general with 2-3 recorded battles and a
  general with 30 are z-scored the same way within their era, so a thin, lucky record can outrank
  a long, well-documented one. A sensitivity test found the ranking formula itself holds up fine
  against per-battle noise; this is a separate, roster-composition problem. The headline ranking
  tables mitigate the worst of this with a display-only minimum-battle cutoff (5 battles, matching
  the gold set's own thinnest cases) that drops thin-record generals from the rendered HTML; the
  CSV outputs next to it keep every general, with a `battle_count` column, so nobody is hidden,
  only de-emphasized. 11 of the current top 30 have fewer than 5 battles.
- **Casualty figures are the sparsest field** (gold-set coverage ~58-62%, see `eval_ingest.py`
  output for current numbers). Wikipedia infoboxes often describe casualties qualitatively
  ("heavy losses") instead of giving a number, and those are left null by design instead of
  guessed at.
- **The composite ranks statistical performance within an era cohort, not historical reputation.**
  Fed the 19 hand-curated gold generals on their own gold battle rows (the method's best-case
  input), the unmodified composite still only reaches +0.296 Spearman agreement with the published
  "greatest generals" lists in `data/reference/top_n_lists.csv`. Switching to the auto pipeline's
  data for the same 19 people drops that to +0.222, and the real 343-general roster drops it again
  to +0.188 — roughly half the total gap to those lists is the method's own definition of "good,"
  not data quality. Treat the reference lists as a sanity check, not a target.
- **Decisiveness is sparse and currently amplifies small samples.** Only 41 of 1,887 pre-H4 battle
  rows (2.2%) carry a Strategic or Rout label, so a general with one or two labeled wins gets a
  near-binary z-score. Shrinking that value toward 0.5 (a pseudo-count of 5) was the single biggest
  improvement found across 16 tested ranking variants; the shipped composite does not do this yet.
- **Longevity can exceed its own ceiling.** `longevity_adjusted_value` sums outcome scores across a
  career and divides by career years, not battle count, so 20% of ranked generals have a value
  above 1.0 — impossible for a bounded rate metric. Every general in the top 10 by this metric has
  a 1- or 2-year career; swapping in plain win rate drops all of them sharply.
- **Some head-to-head comparisons have no shared battle to anchor them.** Napoleon and Wellington
  share zero opponents in `data/auto/`: Waterloo produces no row for either side because its result
  is phrased as a generic "Coalition victory" with no literal country name to match against either
  combatant, and the side-matching logic has no per-conflict alliance lookup to resolve that. Their
  relative order depends entirely on their disjoint opponent pools, and the gap between them swings
  by roughly 115 Elo points across three otherwise-reasonable opponent-rating methods.
- **Credit for a battle goes entirely to one commander per side.** Whoever is listed first in a
  battle's infobox gets the full outcome and the full troop strength; every other named commander
  on that side gets nothing for that battle. 49% of battle sides name more than one commander, and
  this is the documented reason Patton and Bradley never make the roster (someone else is always
  listed first on their headline battles).

Full detail, measurements, and the reasoning behind each of these — including the specific
battles used to verify them — are logged in `~/notes/war-analyzer/ingestion.md` and
`notes/ranking-diagnosis/FINDINGS.md`.
