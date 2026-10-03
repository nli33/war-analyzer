# 2026-10-03 — pre-E4/F3 regen snapshot

What this is: `data/auto/generals.csv` (417 rows incl. header) and `data/auto/battles.csv` (920
rows incl. header) exactly as C6 last wrote them (2026-10-01, `roster_selection_report.json`/
`c6_report.json` timestamps 2026-10-01), before this run's Phase E (identity resolution, seedless
roster, must-include forcing) and Phase F (redirect-stub refresh, demonym/trailing-victory parser
fixes, F3's bounded LLM outcome-resolution pass) were folded into a regenerated `data/auto/`.

Source and method: `war.commanders`/`war.infobox_numbers` (C2/C3) over the C1 battle universe
(8,824 candidate titles, 8,430 found in `data/raw/battle_wikitext_cache.json` at the time),
roster selected by `war.roster.select_roster` at `--min-battles 2`, seed-list-gated (pre-E4), no
identity resolver (pre-E1/E2, so `general_id` is a raw slug of the wikilink title as written —
the Napoleon/Wellington/Hannibal redirect-splitting bug PROGRESS.md opens with), C5's bounded LLM
pass folded in as a strength/casualty fallback, no F3 outcome fallback (F3 didn't exist yet).

Why replaced: this is the exact snapshot PROGRESS.md's intro describes as not trustworthy --
`general_id` splits one person into several identities, the roster only admits seed-listed
generals (12 of 19 gold-set generals were absent), and `no_outcome` was the single largest row-
loss cause (2,907 of 8,824 titles pre-F2, still 2,907 post-F2 fixes since F2 targeted
`no_infobox`/`ambiguous_side_match`, not the `no_outcome` bucket F3 targets). E1-E4 and F1-F3 (see
`~/notes/war-analyzer/ingestion.md`) fix all three; G2 regenerates `data/auto/` with the fixed
pipeline and the F3 outcome fallback newly wired into `war.battles_dataset.build_battle_rows`.

Row/general counts (`roster_selection_report.json`/`c6_report.json` in this directory, as they
stood at the time): 434 generals cleared min-battles=2 pre-fallback, 417 rows written, 920 battle
rows, 342 generals with >=1 row. Field coverage (own/enemy strength 92%/93%, own/enemy casualties
79%/82%, decisiveness 56%) -- not re-measured against the gold-set floor here; C7's eval_ingest.py
run (`2026-10-01-pre-c7-parser-fixes/README.md`'s successor) already cleared the floor on the
underlying C2/C3 extractor, and this snapshot's roster/outcome bugs are membership/outcome-
resolution problems, not extraction-accuracy ones, so the floor numbers aren't why this is
replaced.
