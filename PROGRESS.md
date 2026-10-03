# Progress: fix identities and roster coverage in the auto dataset

The ingestion pipeline works (task logs archived at `notes/PROGRESS-v2.md`, and
`notes/PROGRESS-v1.md` before that). The first auto ranking was not trustworthy because of roster
bugs, not ranking bugs. This run fixes them and regenerates the dataset.

What went wrong, from the previous run's sanity pass:
- `general_id` is a slug of the wikilink title as written in the infobox, so redirects split one
  person into several (Napoleon is "Napoleon", "Napoleon I", and "Napoleon Bonaparte").
- The roster only keeps seed-list generals (Wikipedia general categories) plus their opponents.
  Ruler-generals such as Caesar are never seeded, even though their battles parse fine. 12 of the
  19 gold-set generals are absent.
- Only 920 battle rows came out of 8,824 candidate titles, and 82 roster candidates had zero rows
  because the infobox result text could not be classified. Nobody has measured where rows are lost.
- The top of the auto ranking is full of generals with 3-11 battles.

## Rules that still apply (do not re-ask)

- No agents or sub-agents researching individual battles or generals. Data comes from
  deterministic code. The only LLM use allowed is the bounded Claude CLI batch pass (lowest model
  and effort, at most 3,000 rows and 60 calls in total), and only in task F3.
- Priorities for any choice: cost and latency first, then exhaustiveness and consensus, then
  historical accuracy. Rough numbers are fine. Clear the quality floor first: troop strength
  within 3x of the gold value on at least 75% of rows where both exist, strength present for both
  sides on at least 60% of battles, casualties kept only if at least 40% of rows have them. Do not
  lower the floor to make something pass.
- Time-box each investigation to one iteration. Stop tuning once a fix moves the gold-set numbers by
  less than about 2 points.
- The 19 hand-curated generals in `data/` stay untouched as the gold set. Before regenerating
  `data/auto/`, archive the current version to `data/archive/<YYYY-MM-DD>-<short-label>/` with a
  `README.md` (source, settings, counts, scores, why replaced) and a line in
  `data/archive/INDEX.md`. Record the reasoning in the dev log notes.
- Roster target is about 200-400 generals. If fewer than 100 clear the floor, stop and flag it
  in Notes. Do not pad with thin-data generals.
- Decisions already made for this run: the roster no longer requires a seed list (task E4), and
  the headline ranking uses a minimum-battle cutoff, not shrinkage (task G1).
- Must-include generals: all 19 gold-set generals plus Han Xin must be in the final
  `data/auto/` roster. They go in `data/must_include.csv` (canonical Wikipedia title and reason).
  Roster membership is guaranteed, but they get no exemption from the quality floor or from the
  headline ranking's minimum-battle cutoff (task G1). If one ends up below the cutoff, they stay
  in the full CSV and the report says why.
- Published "top N generals" lists are a reference check only, never a roster source or a weight.
- No `Co-Authored-By` or other AI attribution in commit messages.

## Phase E: Identity and roster

- [x] E1. Canonical identity resolver. Batch every distinct commander wikilink title through the
      MediaWiki API (redirects plus page properties, 50 titles per call, cached under `data/raw/`,
      resumable) to get the canonical page title, the Wikidata ID, and whether the page is a
      disambiguation page. Unit tests use small fixtures taken from real responses. Verify:
      Napoleon, Wellington, and Hannibal variants each resolve to one canonical title, and print
      distinct title counts before and after.
      `war/identity.py` + `scripts/build_identity_map.py`. Ran against the full wikitext cache:
      14,967 distinct commander wikilink titles -> 13,988 distinct identities after merging shared
      Wikidata IDs. Napoleon/Wellington/Hannibal spot-checks all collapse to one identity. Full run
      took about 35 minutes against the live MediaWiki API (rate-limit backoff, not CPU-bound);
      `resolve_cached` only persists the cache once the whole batch finishes rather than per-chunk,
      so a kill mid-run would have lost all progress — it finished cleanly this time, but if a
      future re-run (e.g. `--refresh`) gets interrupted, note that caveat rather than assuming
      resumability works at the batch level. 375 tests pass.
- [x] E2. Use it in the pipeline. `general_id` comes from the canonical title, and titles sharing a
      Wikidata ID merge into one general. A link that resolves to a disambiguation page counts as
      an unidentified commander. Update tests. Verify: no two `general_id`s share a Wikidata ID,
      and the full test suite passes.
      `war.commanders`/`war.roster`/`war.battles_dataset` gained an optional `identity_resolver`
      param (default `None` = old raw-slug behavior), fed by new `war.identity.build_general_id_
      resolver` (groups titles by Wikidata ID, slugs the alphabetically-first canonical title per
      group; disambiguation/unresolved -> `None` = unidentified). Also threaded into
      `seed_general_ids` (not explicitly named in this line, but needed so seed membership stays
      comparable to the now-canonicalized battle `general_id`s — otherwise the merge would have
      broken seed matching for exactly the split-identity generals it's meant to fix). Verified
      against the real 14,967-title E1 run: a dedicated test asserts no two `general_id`s share a
      Wikidata ID (passes), and a throwaway in-memory run of the real roster-selection logic
      (not written to `data/auto/` — that's G2's job) showed roster size 434->503 kept generals and
      duplicate-`display_name` count 12->2, the remaining 2 confirmed by hand to be genuinely
      different people (Philip II of France/Macedon, William III of England/the Silent), not a
      merge bug. 406 tests pass (31 new). `scripts/eval_ingest.py`/`validate_data.py` re-run clean
      (unaffected by construction — both call the parser with the default `None` resolver).
- [ ] E3. Must-include list. Write `data/must_include.csv` with the 19 gold-set generals mapped to
      their canonical Wikipedia titles, plus Han Xin. Add a script that reports, for each one,
      whether they are in the auto roster and, if not, why (not a commander in any parsed battle,
      too few usable battles, and so on).
- [ ] E4. Drop the seed requirement. Any commander with at least N battles that have usable
      strength figures joins the roster, whether or not they were on a seed list, and every
      must-include general joins regardless of N. Keep the seed list only as a flag in the
      output. Choose N so the rule-based roster lands in the target band and write down the roster
      size at N=1 through 5. Verify with E3's report. For a must-include general with fewer than
      N usable pipeline battles: the 19 gold-set generals fall back to their hand-curated rows
      (migrated to the current schema, and marked as hand-curated in the notes column of
      `generals.csv`); Han Xin has no hand-curated rows, so use whatever the pipeline finds and
      record why if it is thin or empty. Report each case.

## Phase F: Where rows are lost

- [ ] F1. Funnel analysis script: from the 8,824 candidate titles, count how many survive each
      stage (page has an infobox, a linked primary commander on a side, usable strength, outcome
      resolved) and write the table to the dev log. List the top loss causes with counts and a few
      real examples each.
- [ ] F2. Fix the biggest deterministic loss causes from F1, at most three fixes. Each one gets a
      test and a before/after row count. Stop after three even if loss remains and note what is
      left.
- [ ] F3. Only if unresolved result strings are still a top loss after F2: classify them in one
      bounded Claude CLI pass (see rules above). Report the row count, call count, and rough cost,
      and drop anything outside sanity bounds. If the queue exceeds the cap, process the most
      frequent patterns first and note the rest. Skip this task if F1/F2 show results are not a
      main cause, and say so in Notes.

## Phase G: Rankings and checks

- [ ] G1. Minimum-battle cutoff for the headline ranking. Look at the distribution of battle
      counts, choose a cutoff, and record why. Show each general's battle count in the ranking
      tables and CSVs, and apply the cutoff to category rankings too. Generals below the cutoff
      stay in the full CSV. Re-run `scripts/sensitivity_test.py` on the new data and confirm the
      ranking is still stable.
- [ ] G2. Archive the current `data/auto/`, regenerate it with the full pipeline, and re-run the
      quality gate with `scripts/eval_ingest.py` against the floor above. If it fails, write why
      in Notes and stop.
- [ ] G3. Published-ranking reference. Collect 3-5 published "top N greatest generals" lists from
      different kinds of sources (for example a Wikipedia list, a historians' survey, a popular
      list). Fetch the pages with plain HTTP; reading names off a list page is fine, no research
      per general. Save the names, ranks, and source URLs in `data/reference/top_n_lists.csv`.
      Map names to canonical titles with E1's resolver. Report which listed generals are missing
      from our roster, and for those in both, how our ranking compares (rank correlation and the
      biggest disagreements). This is a reference check only.
- [ ] G4. Regenerate `output/viz_auto/`. Sanity-check the new ranking against historian
      consensus and G3's reference lists: report where the 19 gold generals and Han Xin landed
      and flag anything that looks like a bug or a roster artifact. Do not hand-tune weights.
      Update README.md: remove the two bugs from the known-limitations list if they are fixed,
      and add the minimum-battle cutoff.

## Notes / deviations
(none yet)
