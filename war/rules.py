"""Deterministic rules that replace hand judgment on three schema fields, plus (C4b) the
year -> era cohort rule used to auto-generate `data/auto/generals.csv`.

PROGRESS.md Phase B task B2: `tech_era_tier`, `resource_backing_tier`, and `decisiveness`
were all hand-judged per row in the original 19-general gold set. The pipeline being built
in Phase C has no human in the loop to make that call per battle, so each field needs a rule
a machine can apply instead. This module holds those three rules. Nothing here touches
`data/battles.csv` (the gold set) — it stays hand-judged, per A6's decision that it is the
benchmark the pipeline is scored against, not a dataset to regenerate. C2/C6 are what call
these functions when building `data/auto/`.
"""

from __future__ import annotations

import csv
import re
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from war.schema import ERAS

# --- tech_era_tier: a plain year lookup table -------------------------------
#
# Boundaries are a judgment call (no single historian's periodization maps cleanly onto 5
# tiers for 6 eras) but are keyed on reasonably uncontroversial technology shifts, not era
# names, so a tier can change mid-era (e.g. medieval battles before vs. after ~1400 land in
# different tiers) rather than pinning every battle in an era to the same number:
#   1: pre-gunpowder - muscle and animal power logistics (year < 1400)
#   2: gunpowder arrives - early firearms and siege cannon, armies still not standardized
#      (1400-1699)
#   3: standardized flintlock-musket and massed-artillery warfare, pre-rail logistics
#      (1700-1859)
#   4: rail and telegraph logistics, rifled breech-loading weapons, ironclads (1860-1913)
#   5: mechanised warfare - aircraft, armor, radio (1914+)
_TECH_ERA_BREAKPOINTS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (1400, 2),
    (1700, 3),
    (1860, 4),
    (1914, 5),
)


def tech_era_tier_for_year(year: int) -> int:
    """Map a battle's year to a 1-5 tech_era_tier via `_TECH_ERA_BREAKPOINTS`.

    >>> tech_era_tier_for_year(-334)
    1
    >>> tech_era_tier_for_year(1415)
    2
    >>> tech_era_tier_for_year(1815)
    3
    >>> tech_era_tier_for_year(1863)
    4
    >>> tech_era_tier_for_year(1944)
    5
    """
    tier = _TECH_ERA_BREAKPOINTS[0][1]
    for threshold, candidate_tier in _TECH_ERA_BREAKPOINTS:
        if year >= threshold:
            tier = candidate_tier
    return tier


# --- resource_backing_tier: COW CINC after 1816, a coarse era default before ------------
#
# CINC (Composite Index of National Capability) is a 0-1 share of that year's total world
# military/industrial/demographic capability across every state COW tracks, so a state's
# CINC is already relative to its contemporaries - the same "relative to the general's own
# period" framing schema.py documents for this tier. Below, a country's CINC is converted to
# a tier by its quintile rank among every state's CINC *that year*, not a fixed cutoff, so
# the tier keeps meaning "strong/weak for the time" in 1820 and in 1940 alike.
#
# COW CINC starts in 1816 (A4). Before that there is no comparable cross-state dataset cheap
# enough to join (A2 rejected the alternatives), so pre-1816 battles fall back to one default
# tier per era - a coarse stand-in, not a measurement, and it will not distinguish a
# well-backed general from a poorly-backed one within the same era. That is a known and
# accepted limitation (PROGRESS.md: "a coarse per-era default"), recorded here and in the dev
# log rather than hidden behind a more precise-looking number.
CINC_START_YEAR = 1816

RESOURCE_ERA_DEFAULT: dict[str, int] = {
    "Ancient": 3,  # large organized state armies (Rome, Persia, Macedon) in this dataset
    "Medieval": 2,  # fragmented polities, feudal levies; weaker average fiscal-military reach
    "Early Modern": 3,  # centralizing fiscal-military states with standing armies
    "Napoleonic": 4,  # mass conscription, nation-at-war mobilization (entirely pre-1816)
    "Industrial": 3,  # fallback only: used when a matched state/year is missing from CINC
    "WWII": 3,  # fallback only: used when a matched state/year is missing from CINC
    "Modern": 3,  # fallback only: used when a matched state/year is missing from CINC
}
assert set(RESOURCE_ERA_DEFAULT) == set(ERAS)


@dataclass(frozen=True)
class CincTable:
    """Correlates of War National Material Capabilities, indexed for lookup.

    `by_country_year` is the raw point value; `by_year` is every state's CINC that year
    (including the lookup country's own), used to rank it into a tier.
    """

    by_country_year: dict[tuple[str, int], float]
    by_year: dict[int, list[float]]


def load_cinc_table(path: Path | str) -> CincTable:
    """Load `NMC-70-abridged.csv` (`scripts/fetch_cow_cinc.py` downloads it to
    `data/raw/cow_cinc/`). Keyed by COW `stateabb` (e.g. "USA", "FRN", "UKG"), not full
    country names.
    """
    by_country_year: dict[tuple[str, int], float] = {}
    by_year: dict[int, list[float]] = defaultdict(list)
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            year = int(row["year"])
            cinc = float(row["cinc"])
            by_country_year[(row["stateabb"], year)] = cinc
            by_year[year].append(cinc)
    return CincTable(by_country_year=by_country_year, by_year=dict(by_year))


def _cinc_quintile_tier(cinc: float, year_values: list[float]) -> int:
    """1-5 tier from `cinc`'s rank among `year_values` (that year's full CINC distribution)."""
    ordered = sorted(year_values)
    percentile = bisect_left(ordered, cinc) / len(ordered)
    if percentile >= 0.8:
        return 5
    if percentile >= 0.6:
        return 4
    if percentile >= 0.4:
        return 3
    if percentile >= 0.2:
        return 2
    return 1


def resource_backing_tier(
    year: int,
    era: str,
    country_abbr: str | None = None,
    cinc_table: CincTable | None = None,
) -> int:
    """1-5 resource_backing_tier: CINC-quintile when available, era default otherwise.

    Falls back to `RESOURCE_ERA_DEFAULT[era]` whenever `year` predates COW CINC (1816), no
    `country_abbr`/`cinc_table` was given, or the country/year pair isn't in the table
    (a state COW doesn't track, or a gap in its coverage).

    >>> resource_backing_tier(1700, "Early Modern")
    3
    >>> table = CincTable(by_country_year={("USA", 1900): 0.09}, by_year={1900: [0.01, 0.03, 0.09, 0.2]})
    >>> resource_backing_tier(1900, "Industrial", "USA", table)
    3
    >>> resource_backing_tier(1900, "Industrial", "FRN", table)
    3
    """
    if year >= CINC_START_YEAR and country_abbr and cinc_table is not None:
        key = (country_abbr, year)
        if key in cinc_table.by_country_year:
            return _cinc_quintile_tier(cinc_table.by_country_year[key], cinc_table.by_year[year])
    return RESOURCE_ERA_DEFAULT[era]


# --- decisiveness: parsed from the infobox `result` field -------------------------------
#
# Wikipedia's military-conflict infobox `result` field is free text like "Decisive French
# victory", "Pyrrhic victory for the Allies", "Strategic Soviet victory", or a plain
# "X victory" with no modifier. schema.py's DECISIVENESS_LEVELS describe the *result for this
# general*, and `outcome` (Win/Loss/Draw) already encodes which side that is, so this rule
# doesn't need to know which named side is "this general" - it only needs the keyword and the
# already-known outcome:
#   - "decisive"/"rout"/"annihilat*"/"destroyed" -> Rout regardless of Win or Loss: a decisive
#     result means one army broke, and `outcome` already says whether it was this general's
#     own army (Loss) or the enemy's (Win) - schema.py's definition of Rout for a Loss.
#   - Draw -> always None; there is no stronger label than a drawn outcome.
#   - Pyrrhic/Strategic only apply to the side that nominally won, so they're only assigned
#     when outcome is Win; a Loss with no rout keyword returns None ("no stronger label than
#     the outcome applies", which schema.py explicitly allows).
#   - A plain "X victory" with no modifier defaults to Tactical for a Win - the floor level,
#     since infobox text alone can't tell us the win advanced the actual campaign objective
#     (that gap is exactly why B1 dropped `objective_secured` instead of trying to derive it).
#
# `\b` word boundaries matter here: "decisive" must not match inside "indecisive" (a stalemate
# word, not a decisive one) - `\bdecisive\b` already excludes it, since "n" and "d" are both
# word characters with no boundary between them.
_ROUT_RE = re.compile(r"\b(decisive|routed?|routing|annihilat\w*|destroyed)\b", re.IGNORECASE)


def decisiveness_from_result(result_text: str | None, outcome: str) -> str | None:
    """Derive `decisiveness` from the infobox `result` field text and the already-known
    `outcome`. Returns `None` when no stronger label than `outcome` applies (see module notes).
    """
    if outcome == "Draw" or not result_text:
        return None

    text = result_text.lower()
    if _ROUT_RE.search(text):
        return "Rout"

    if outcome != "Win":
        return None

    if "pyrrhic" in text:
        return "Pyrrhic"
    if "strategic" in text:
        return "Strategic"
    return "Tactical"


# --- era_for_year: a plain year lookup table (C4b) --------------------------------------
#
# `data/battles.csv`'s `era` column was hand-assigned per general by the gold set's curators,
# not computed from a year cutoff — e.g. its "Medieval" rows run from 1175 to 1615 while its
# "Early Modern" rows start at 1741, a gap with no battle in it, so the gold set itself doesn't
# pin down where the boundary actually falls. C4b's auto-generated `data/auto/generals.csv`
# has no curator to make that call per general, so this table picks one boundary year per era
# transition from the conventional historical turning point nearest the gold set's gap, each
# chosen independently (not derived from `_TECH_ERA_BREAKPOINTS` above, whose 5 tiers don't
# line up 1:1 with `ERAS`'s 6 — though two breakpoints do end up numerically identical, noted
# below, since both rules picked the same real-world turning point for different reasons):
#   Ancient / Medieval     - 500  (conventional fall of the Western Roman Empire, 476 CE)
#   Medieval / Early Modern - 1500 (Renaissance / Age of Discovery)
#   Early Modern / Napoleonic - 1792 (French Revolutionary Wars begin)
#   Napoleonic / Industrial - 1816 (the year after Waterloo; also where COW CINC data starts,
#       a coincidence of two independent choices, not a dependency between them)
#   Industrial / WWII      - 1914 (matches `_TECH_ERA_BREAKPOINTS`'s tier-5 threshold: WWI has
#       no era of its own in `ERAS`, so 1914-1918 battles land in the "WWII" bucket — a known,
#       accepted gap in the enum, not a claim that WWI battles are WWII battles)
#   WWII / Modern          - 1945 (WWII's end). H1: the original table had no upper bound on
#       "WWII" at all, so 2001-2017 battles (Macedonia, Iraq, Libya, Syria) were landing in that
#       bucket too, inflating "WWII" careers and z-score cohorts with Cold-War-and-later rows
#       that have nothing to do with the war. This is the fix PROGRESS.md's H1 asked for: add a
#       bound, don't leave post-1945 battles mistagged.
_ERA_BREAKPOINTS: tuple[tuple[int, str], ...] = (
    (-999999, "Ancient"),
    (500, "Medieval"),
    (1500, "Early Modern"),
    (1792, "Napoleonic"),
    (1816, "Industrial"),
    (1914, "WWII"),
    (1945, "Modern"),
)
assert {era for _, era in _ERA_BREAKPOINTS} == set(ERAS)


# --- outcome_from_result: which side won, from the infobox `result` text (C6) -----------
#
# Deriving `outcome` (Win/Loss/Draw) is a gap PROGRESS.md's plan left implicit: B2 built
# `decisiveness_from_result` *assuming* `outcome` was already known, and C3 only assigned
# commanders to sides, never results. But `outcome` is a required schema column, so C6's full
# run needs a rule for it. Added here, in the same "rule that replaces hand judgment" spirit
# as the other three in this module, and the same way: measured against real cached pages
# before picking a design, not guessed (see dev log's C6 entry).
#
# The `result` field names a *nation/demonym* ("Confederate victory", "Pyrrhic Carthaginian
# victory"), not "combatant1"/"combatant2" directly, so telling which side it means requires
# matching that word against `combatant1`/`combatant2`'s own free text. Most of the time the
# word is already a literal substring of one side's text ("Roman victory" / combatant1 "Roman
# Republic"); the rest of the time it is a demonym built from a country name by an irregular
# rule English doesn't apply predictably ("French" from "France", "British" from "Britain") -
# `_DEMONYM_TO_COUNTRY` is a hand-built lookup for the common irregular cases seen in a sample
# of this project's own battle universe, not a general solution. Measured on 8,433 real cached
# pages before committing to this design: a plain substring/suffix-stem match alone resolved
# ~46% of pages with a "victory"-shaped result and at least one combatant field; adding the
# demonym table raised that to ~56%, a worthwhile gain for a bounded, one-time addition, but the
# remainder (results naming a demonym this table doesn't have, or missing both combatant fields
# outright) is accepted as unresolved - this returns (None, None) for those; the row is not
# written to data/auto/battles.csv rather than guessing a winner.
_DEMONYM_TO_COUNTRY: dict[str, str] = {
    "french": "france", "british": "britain", "english": "england", "american": "america",
    "spanish": "spain", "portuguese": "portugal", "italian": "italy", "german": "germany",
    "russian": "russia", "chinese": "china", "japanese": "japan", "turkish": "turkey",
    "dutch": "netherlands", "swedish": "sweden", "danish": "denmark", "polish": "poland",
    "austrian": "austria", "hungarian": "hungary", "prussian": "prussia", "egyptian": "egypt",
    "persian": "persia", "indian": "india", "korean": "korea", "vietnamese": "vietnam",
    "mexican": "mexico", "canadian": "canada", "australian": "australia", "israeli": "israel",
    "greek": "greece", "carthaginian": "carthage", "macedonian": "macedon", "gallic": "gaul",
    "gaulish": "gaul", "norman": "normandy", "castilian": "castile", "aragonese": "aragon",
    "venetian": "venice", "genoese": "genoa", "florentine": "florence", "neapolitan": "naples",
    "sicilian": "sicily", "papal": "papacy", "burgundian": "burgundy", "bavarian": "bavaria",
    "saxon": "saxony", "scottish": "scotland", "irish": "ireland", "welsh": "wales",
    "norwegian": "norway", "finnish": "finland", "belgian": "belgium", "swiss": "switzerland",
    "romanian": "romania", "bulgarian": "bulgaria", "serbian": "serbia", "croatian": "croatia",
    "ethiopian": "ethiopia", "algerian": "algeria", "moroccan": "morocco", "iraqi": "iraq",
    "iranian": "iran", "syrian": "syria", "pakistani": "pakistan", "bangladeshi": "bangladesh",
    "thai": "thailand", "burmese": "burma", "filipino": "philippines", "indonesian": "indonesia",
    "brazilian": "brazil", "argentine": "argentina", "chilean": "chile", "peruvian": "peru",
    "colombian": "colombia", "cuban": "cuba", "haitian": "haiti",
}

_DEMONYM_SUFFIXES = ("ese", "ian", "ish", "an", "ic")

# Some common official country names don't contain their own demonym as a word at all --
# "United Kingdom" has no word that stems to "britain", not even via a suffix strip, because
# both of its words ("united", "kingdom") are themselves generic polity-type stopwords, not a
# country name. Same gap for "United States" vs. "american"/"america". Measured against the real
# battle-universe cache (F2 dev log entry): these two phrases alone account for most of the
# "ambiguous_side_match" no_outcome loss cause F1 found -- adding them as whole-phrase aliases
# (checked against the raw text, before stopword filtering, rather than trying to patch the
# stopword list or suffix rules) resolves them without touching any other country.
_COUNTRY_PHRASE_ALIASES: dict[str, str] = {
    "united kingdom": "britain",
    "united states": "america",
}

# Generic polity-type nouns that don't identify *which* polity, stripped before token matching
# so e.g. "Confederate States" matches on "confederate" and not also, uselessly, on "states".
_POLITY_STOPWORDS = frozenset(
    {
        "the", "of", "and", "forces", "kingdom", "republic", "empire", "duchy", "colony",
        "colonial", "dynasty", "confederacy", "government", "company", "states", "united",
        "army", "state", "clan", "garrison", "rebels", "rebellion", "supported", "supporting",
    }
)

_RESULT_VICTORY_RE = re.compile(r"^(.*?)\bvictory\b", re.IGNORECASE)
_RESULT_DRAW_RE = re.compile(r"inconclusive|indecisive|stalemate|\bdraw\b|status quo", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-zA-Z]{3,}")

# Some result strings put the winning side *after* "victory" instead of before it -- "Victory
# for Philip II", "Victory of Antiochus Hierax" -- which the leading-adjective extraction above
# can't see (its capture group stops at "victory"). Unlike the leading-adjective case, the name
# here is often a person or a specific faction rather than a country demonym, so it's matched as
# a literal substring against the combatant text instead of through the demonym-stem machinery.
# A trailing clause (another sentence/bullet, e.g. "Victory for Drenthe * Death of Otto II of
# Lippe") is cut at the first `;`/`*`/newline so it doesn't pollute the matched name.
_RESULT_TRAILING_VICTORY_RE = re.compile(r"\bvictory\s+(?:for|of|to)\s+(.+)", re.IGNORECASE)
_TRAILING_NAME_SPLIT_RE = re.compile(r"[;*\n]")


def _trailing_victory_name(result_text: str) -> str | None:
    match = _RESULT_TRAILING_VICTORY_RE.search(result_text)
    if not match:
        return None
    name = _TRAILING_NAME_SPLIT_RE.split(match.group(1))[0].strip()
    return name or None


def _name_in_combatant(name: str, combatant_text: str | None) -> bool:
    if not combatant_text:
        return False
    name, combatant_text = name.lower(), combatant_text.lower()
    return name in combatant_text or combatant_text in name


def _demonym_stem(word: str) -> str:
    word = word.lower()
    if word in _DEMONYM_TO_COUNTRY:
        return _DEMONYM_TO_COUNTRY[word]
    for suffix in _DEMONYM_SUFFIXES:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _combatant_tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    lowered = text.lower()
    tokens = {w for w in _WORD_RE.findall(lowered) if w not in _POLITY_STOPWORDS}
    for phrase, alias in _COUNTRY_PHRASE_ALIASES.items():
        if phrase in lowered:
            tokens.add(alias)
    return tokens


def _side_match_score(adjective_words: list[str], combatant_text: str | None) -> int:
    tokens = _combatant_tokens(combatant_text)
    score = 0
    for word in adjective_words:
        stem = _demonym_stem(word)
        for token in tokens:
            token_stem = _demonym_stem(token)
            if stem == token_stem or stem.startswith(token_stem) or token_stem.startswith(stem):
                if min(len(stem), len(token_stem)) >= 3:
                    score += 1
                    break
    return score


def outcome_from_result(
    result_text: str | None, combatant1_text: str | None, combatant2_text: str | None
) -> tuple[str | None, str | None]:
    """Derive (outcome_for_side1, outcome_for_side2) from the infobox `result`/`combatant1`/
    `combatant2` fields. Each element is "Win"/"Loss"/"Draw", or `None` if the text does not let
    this rule tell who won (see module notes above for exactly when that happens and why).

    >>> outcome_from_result("Roman victory", "Roman Republic", "Gauls")
    ('Win', 'Loss')
    >>> outcome_from_result("Confederate victory", "United States", "Confederate States")
    ('Loss', 'Win')
    >>> outcome_from_result("Indecisive, stalemate", "France", "Great Britain")
    ('Draw', 'Draw')
    >>> outcome_from_result("Ceasefire agreed", "France", "Great Britain")
    (None, None)
    >>> outcome_from_result("Victory for Philip II", "Supporters of António", "Supporters of Philip II")
    ('Loss', 'Win')
    """
    if not result_text:
        return (None, None)
    if _RESULT_DRAW_RE.search(result_text):
        return ("Draw", "Draw")

    match = _RESULT_VICTORY_RE.search(result_text)
    if not match:
        return (None, None)
    adjective_words = [
        w for w in _WORD_RE.findall(match.group(1).lower()) if w not in _POLITY_STOPWORDS
    ]
    if not adjective_words:
        return _outcome_from_trailing_victory_name(
            result_text, combatant1_text, combatant2_text
        )

    score1 = _side_match_score(adjective_words, combatant1_text)
    score2 = _side_match_score(adjective_words, combatant2_text)
    if score1 == score2:
        return (None, None)
    return ("Win", "Loss") if score1 > score2 else ("Loss", "Win")


def _outcome_from_trailing_victory_name(
    result_text: str, combatant1_text: str | None, combatant2_text: str | None
) -> tuple[str | None, str | None]:
    name = _trailing_victory_name(result_text)
    if name is None:
        return (None, None)
    in1 = _name_in_combatant(name, combatant1_text)
    in2 = _name_in_combatant(name, combatant2_text)
    if in1 == in2:  # named side matches both/neither combatant text -- stay unresolved
        return (None, None)
    return ("Win", "Loss") if in1 else ("Loss", "Win")


def era_for_year(year: int) -> str:
    """Map a year to one of `war.schema.ERAS` via `_ERA_BREAKPOINTS`.

    >>> era_for_year(-334)
    'Ancient'
    >>> era_for_year(1200)
    'Medieval'
    >>> era_for_year(1600)
    'Early Modern'
    >>> era_for_year(1800)
    'Napoleonic'
    >>> era_for_year(1863)
    'Industrial'
    >>> era_for_year(1916)
    'WWII'
    >>> era_for_year(1944)
    'WWII'
    >>> era_for_year(1945)
    'Modern'
    >>> era_for_year(2011)
    'Modern'
    """
    era = _ERA_BREAKPOINTS[0][1]
    for threshold, candidate_era in _ERA_BREAKPOINTS:
        if year >= threshold:
            era = candidate_era
    return era
