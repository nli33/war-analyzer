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
target `data/auto/` (or any other battles/generals CSV pair) instead:

```
python scripts/validate_data.py                     # schema check, run this first
python scripts/render_ranking_tables.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto
python scripts/render_scatter_oar_resource_backing.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto
python scripts/render_scatter_tactical_strategic.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto
python scripts/render_scatter_volume_efficiency.py --battles data/auto/battles.csv \
    --generals data/auto/generals.csv --output output/viz_auto
```

`render_ranking_tables.py` also takes `--top-n` (default 25) for how many rows its HTML tables
show; the CSV outputs next to it are always the full set.

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
- **Doesn't merge alternate Wikipedia titles for the same person.** A general with two Wikipedia
  pages (a full-name article and a shorter common-name one — Napoleon/Napoleon Bonaparte,
  Wellington/Arthur Wellesley, Hannibal/Hannibal Barca) ends up as two separate roster entries,
  each with half that person's real battle record. This both double-counts them in ranking tables
  and makes their individual stats noisier than they should be.
- **Misses ruler-generals in roster selection.** The automated roster is seeded from Wikipedia
  categories like "Generals by century/war/nationality"; someone who commanded armies but is
  categorized primarily as a king, khan, shogun, president, or field marshal (Julius Caesar,
  Alexander the Great, Genghis Khan, Eisenhower, Zhukov, Rommel) is often missing entirely, and
  the pipeline's fallback rule (pull in an unseeded general if they fought a seeded one) doesn't
  help when both sides of a battle share that same blind spot. Of the 19 gold-set generals, only
  6 appear in the current `data/auto/` roster under a shared id (several more are present but
  split across a different id per the point above).
- **No sample-size weighting in the composite ranking.** A general with 2-3 recorded battles and a
  general with 30 are z-scored the same way within their era, so a thin, lucky record can outrank
  a long, well-documented one. A sensitivity test found the ranking formula itself holds up fine
  against per-battle noise; this is a separate, roster-composition problem.
- **Casualty figures are the sparsest field** (gold-set coverage ~58-62%, see `eval_ingest.py`
  output for current numbers). Wikipedia infoboxes often describe casualties qualitatively
  ("heavy losses") instead of giving a number, and those are left null by design instead of
  guessed at.

Full detail, measurements, and the reasoning behind each of these — including the specific
battles used to verify them — are logged in `~/notes/war-analyzer/ingestion.md`.
