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
- [x] E3. Must-include list. `data/must_include.csv`: the 19 gold-set generals (by their
      `data/generals.csv` `general_id`) plus Han Xin, each mapped to its canonical Wikipedia title
      via E1's `data/raw/identity_map.json` (two differ from the gold slug after canonicalization:
      `hannibal-barca` -> canonical title "Hannibal", `napoleon-bonaparte` -> "Napoleon"; `wellington`
      stays "Arthur Wellesley, 1st Duke of Wellington"). `scripts/report_must_include.py` re-parses
      the cached battle universe the same way C4b does (read-only, no crawl) and reports each
      must-include general's appearance/usable-battle counts and roster status at a given
      `--min-battles`. At the current default (N=2, seed-gated, pre-E4): 9/20 in roster. Of the 11
      missing, 9 already clear the usable-battle bar but are blocked only by the still-active seed
      requirement (expected to resolve once E4 drops it) and 2 (Subutai, Eisenhower: 1 usable
      battle each) are genuinely thin and will need E4's hand-curated-fallback path. None are
      absent from the cache entirely (0 "not a commander in any parsed battle" cases). 412 tests
      pass (5 new, covering the status-classification logic).
- [x] E4. Drop the seed requirement. `war.roster.select_roster` no longer gates on seed
      membership (and the old "opponent of a kept general" hop is gone too -- it only ever
      admitted generals who already cleared the bar on their own, which is now sufficient by
      itself): any general with >= N usable-strength battles joins, seed-listed or not. The seed
      list is now informational only, carried into `generals.csv`'s `notes` column
      (`seed=true`/`seed=false`) by `generals_csv_rows`, not used to decide membership. A new
      `must_include_ids` param on `select_roster` forces every must-include general in
      regardless of N, including with zero pipeline appearances.
      Roster size at N=1 through 5 (seedless, no must-include forcing, from the full 8,430-page
      wikitext cache): N=1 -> 4,703, N=2 -> 1,245, N=3 -> 552, N=4 -> 284, N=5 -> 183. Target
      band is 200-400, so **N=4**. (N=5's 183 is close but under the floor; N=3's 552 overshoots.)
      With must-include forcing and the N=4 bar: 13/20 must-include generals clear the bar
      directly; 7 are thin (usable count below 4): genghis-khan (3), georgy-zhukov (3), subutai
      (1), dwight-d-eisenhower (1), erwin-rommel (3), erich-von-manstein (2), and han-xin (3).
      The first six are gold-set generals, so `scripts/build_roster_selection.py` substitutes
      their hand-curated `data/generals.csv`/`data/battles.csv` rows verbatim (notes column
      marked `hand-curated fallback (E4, must-include): ...`); their thin pipeline-derived roster
      entry is popped first so there's no duplicate `general_id` row. Han Xin has no hand-curated
      rows (he was never part of the original 8/19-general curation), so his thin pipeline entry
      (3 usable of 4 total appearances) stays as-is with a `THIN must-include` note explaining
      why -- flagged, not papered over. Final roster size: 288 (282 pipeline-cleared + 6
      hand-curated fallbacks), comfortably inside the 200-400 band.
      `scripts/build_auto_battles.py` reads the new fallback list from
      `data/raw/roster_selection_report.json` (written by `build_roster_selection.py`), excludes
      those general_ids from the pipeline wikitext parse (their canonical pipeline identity, not
      the gold slug, is what infoboxes actually link to, so the parse would never find them
      anyway), and copies their `data/battles.csv` rows in verbatim instead (39 rows across the 6
      generals), normalizing empty cells to `None` so null-rate reporting counts them correctly.
      Did not run either build script against the live `data/auto/` this task -- that
      regeneration is G2's job and requires archiving the current (pre-E4, seed-gated)
      `data/auto/` first per this file's "Decisions already made" rule. Verified instead via: (1)
      `tests/test_roster.py`/`tests/test_report_must_include.py`, rewritten for the new
      seedless/must-include-forcing behavior (420 tests pass, up from 412); (2)
      `scripts/report_must_include.py --min-battles 4` (read-only, no crawl) against the real
      cached data, confirming the 13-clear/7-thin split above; (3) a throwaway sandboxed run of
      the real `build_roster_selection.py`/`build_auto_battles.py` functions against the real
      cached wikitext and gold CSVs, writing to `/tmp` instead of `data/auto/`, confirming no
      duplicate `general_id` rows, correct display_name/era/years carried through from the gold
      set, and correct gold battle-row counts/normalization. `scripts/eval_ingest.py` and the
      validator weren't re-run for this task -- neither touches roster-selection logic, and
      `data/auto/` itself isn't regenerated until G2.

## Phase F: Where rows are lost

- [x] F1. Funnel analysis script: from the 8,824 candidate titles, count how many survive each
      stage (page has an infobox, a linked primary commander on a side, usable strength, outcome
      resolved) and write the table to the dev log. List the top loss causes with counts and a few
      real examples each.
      `scripts/funnel_analysis.py` (read-only, no network calls; reuses the real pipeline's
      parsing functions). Full table and root-caused loss breakdown in the dev log
      (`~/notes/war-analyzer/ingestion.md`, "F1" entry); summary: of 8,824 candidates, 394 never
      fetched, 1,160 have no infobox (981 of those are unresolved `#REDIRECT` stubs, not
      genuinely infobox-less), 453 have no parseable year, 621 have no wikilinked primary
      commander on either side, 2,716 have no resolved outcome (2,141 of those are
      `ambiguous_side_match`, and 924 of *those* trace to one demonym-table gap: "British" maps
      to "Britain" but real infobox text says "United Kingdom", whose words are both stopwords).
      3,480 titles (39%) would produce at least one row. Report written to
      `data/raw/funnel_report.json` (full loss-reason list, top 6 summarized in the dev log).
      431 tests pass (11 new, `tests/test_funnel_analysis.py`). `eval_ingest.py`/
      `validate_data.py` not re-run -- this task touches neither `data/auto/` nor the gold set.
      The two cheapest, highest-volume candidates for F2 (not implemented here): follow
      `#REDIRECT` targets before giving up on "no infobox" (~981 recoverable), and fix the
      "British"/"United Kingdom" demonym gap (~924 recoverable from one table edit).
- [x] F2. Three fixes, each measured with `scripts/funnel_analysis.py` before/after against the
      real cache: (1) `war.scrape.redirect_stub_target` + `scripts/refresh_redirect_stubs.py`
      refreshed 900 stale `#REDIRECT`-stub cache entries (the redirect-following fix already
      existed in `fetch_wikitext_batch` since b57cc1b, but the 8,430-page cache predated that
      commit by 8 minutes and was never refreshed) -- `no_infobox` 1,160 -> 310 (-850); (2)
      `war.rules._COUNTRY_PHRASE_ALIASES` fixes "United Kingdom"/"United States" matching no
      demonym (both words in each phrase are themselves stopwords) -- `ambiguous_side_match`
      2,141 -> 2,061 (-80, well under F1's ~924 estimate, which wasn't gated by the funnel's
      earlier stages -- see dev log for why raw text-pattern counts overstate real yield); (3)
      found while measuring (2): `_trailing_victory_name` handles "Victory for/of X" result text
      (name after the keyword, not before) -- `victory_keyword_no_adjective` 175 -> 98 (-77, 30
      of those resolved, 47 reclassified to an honestly-still-unresolved
      `ambiguous_trailing_victory_name`). Combined: `produced_row` 3,480 -> 3,982 (+502), usable
      strength on both sides 2,242 -> 2,555 (+313). Stopped at three per the cap.
      `ambiguous_side_match` (2,291 remaining, mostly both-combatant-fields-`None`) is the
      biggest loss left untouched; full numbers and what's left in the dev log's F2 entry.
      441 tests pass (10 new). `eval_ingest.py`/`validate_data.py` not re-run -- F2 touches the
      wikitext cache and rules, not `data/auto/` (G2's job); `funnel_analysis.py` is this task's
      own before/after tool.
- [x] F3. Only if unresolved result strings are still a top loss after F2: classify them in one
      bounded Claude CLI pass (see rules above). Report the row count, call count, and rough cost,
      and drop anything outside sanity bounds. If the queue exceeds the cap, process the most
      frequent patterns first and note the rest. Skip this task if F1/F2 show results are not a
      main cause, and say so in Notes.
      Confirmed F3 applies: `no_outcome` (2,907 titles post-F2) is still the single largest loss
      stage, well above `no_infobox` (310) or `no_commander` (698). Built
      `war/uncertain_outcomes.py` (queue: every title clearing the infobox/year/commander gates
      whose `outcome_from_result` returns `(None, None)`, restricted to titles with real `result`
      text and at least one `combatant` field's text to match it against -- same free-resolve
      rule C5 applied to digit-less numeric fields) and `scripts/resolve_uncertain_outcomes.py`
      (haiku, low effort, batched, `--tools ""`, JSON schema, resumable via
      `data/raw/f3_llm_cache.json`).
      Real queue against the full 8,824-title cache: 2,823 unresolved outcomes, 603 free-resolved
      (no side-identifying text at all -- genuinely nothing for a model to read either), 2,220
      sent to the model in 56 batches of 40 -- both inside the 3,000-row/60-call cap. One batch
      (21/56) hit the 180s subprocess timeout and crashed the script with an unhandled
      `TimeoutExpired` on the first attempt; fixed by catching that (and a malformed-JSON
      response) in `call_batch` and treating it as "no results this batch" rather than a crash --
      the per-batch cache write already made this safe to just rerun. Resumed from the 800 items
      already cached and finished the remaining 36 calls clean, no further errors.
      Final numbers (combined across both runs): 56 calls total, cost $1.1162 + $2.2083 =
      **$3.3245**, 1,656 of the 2,220 sent (74.6%) resolved to a real outcome (1,224 side1 / 372
      side2 / 60 draw), 0 rejected by the sanity check (output is a closed 3-value enum, so the
      only possible rejections are a malformed/off-enum value or a missing id -- neither showed
      up in practice). The other 564 sent to the model came back null (genuinely unresolvable from
      the given text) or missing (timed-out batch 21, since re-sent and resolved). Spot-checked 10
      `side1`, 6 `side2`, and 6 `draw` resolutions by hand against their raw queue text -- all
      correct, including non-trivial cases (matching a result's "Greek victory" against a
      combatant list naming Epirotes/Aetolians/Italiot Greeks with no literal "Greek" token, and
      inferring a winner from "weakening of the magnates" when the winning side's own combatant
      field was empty). The side1/side2 skew (1,224 vs. 372) held up under spot-checking as a real
      pattern in this queue, not the model defaulting to side1 under uncertainty -- not
      investigated further than the sample, since "why is it skewed" isn't a correctness question
      this task's sanity check needs to answer.
      457 tests pass (16 new, `tests/test_uncertain_outcomes.py`). `eval_ingest.py`/
      `validate_data.py` not re-run -- same reasoning as C5/F2: this task writes a standalone
      `data/auto/f3_resolved_outcomes.json` artifact, not `data/auto/battles.csv` itself (ran
      `validate_data.py` once anyway as a smoke test that nothing else broke; still clean). Not
      yet wired into `war/battles_dataset.py`/`data/auto/` -- per the same C5/C6 split this
      project already uses, that merge (reading `f3_resolved_outcomes.json` as a fallback when
      `outcome_from_result` itself returns `None`, same shape as C5's `resolved_fields` fallback
      for strength/casualties) is G2's job, which regenerates `data/auto/` from the full pipeline,
      not F3's.

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
