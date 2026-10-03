"""G3: compare the auto roster's composite ranking against published "top N greatest generals"
lists, as a reference/sanity check only -- never a roster source or a scoring input (PROGRESS.md).

This module holds the pure, testable comparison logic. `scripts/report_reference_rankings.py`
does the I/O around it: reading `data/reference/top_n_lists.csv`, resolving each listed name to
a canonical Wikipedia identity (network calls, same E1 mechanism the pipeline itself uses) and
from there to a `general_id`, loading `data/auto/`'s own composite ranking, and writing the
combined report.
"""

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReferenceListEntry:
    """One row of `data/reference/top_n_lists.csv`: one name at one rank on one published list."""

    source: str
    source_kind: str
    url: str
    rank: int
    name: str


def load_reference_list(path: Path | str) -> list[ReferenceListEntry]:
    """Pure CSV parse, no network and no identity resolution."""
    with Path(path).open(newline="", encoding="utf-8") as handle:
        return [
            ReferenceListEntry(
                source=row["source"],
                source_kind=row["source_kind"],
                url=row["url"],
                rank=int(row["rank"]),
                name=row["name"],
            )
            for row in csv.DictReader(handle)
        ]


@dataclass(frozen=True)
class ComparisonRow:
    """One reference-list entry, joined against the auto roster.

    `status` is one of:
    - "ranked": in the roster and has a computed composite rank (at least one battle row).
    - "in_roster_unranked": in `data/auto/generals.csv` but has no battle row to rank
      (`composite_ranking` only scores generals with at least one battle).
    - "missing": resolved to a real Wikipedia identity, but that identity is not in the roster.
    - "unresolved": the name itself didn't resolve to any Wikipedia page (deleted/moved/typo'd
      since whatever source listed it, or a transliteration variant E1/E2's resolver has never
      seen).
    """

    source: str
    published_rank: int
    name: str
    general_id: str | None
    status: str
    our_rank: int | None
    our_battle_count: int | None


def build_comparison_rows(
    entries: list[ReferenceListEntry],
    name_to_general_id: dict[str, str | None],
    roster_general_ids: set[str],
    rank_by_general_id: dict[str, int],
    battle_count_by_general_id: dict[str, int],
) -> list[ComparisonRow]:
    """Join each reference entry against the roster and the computed composite ranking.

    `name_to_general_id` is the caller's already-resolved `{reference name: general_id or None}`
    (identity resolution is network-bound, so it happens in the script, not here).
    `rank_by_general_id`/`battle_count_by_general_id` come from `composite_ranking_rows` run
    against `data/auto/`.
    """
    rows = []
    for entry in entries:
        general_id = name_to_general_id.get(entry.name)
        if general_id is None:
            status = "unresolved"
        elif general_id not in roster_general_ids:
            status = "missing"
        elif general_id in rank_by_general_id:
            status = "ranked"
        else:
            status = "in_roster_unranked"

        rows.append(
            ComparisonRow(
                source=entry.source,
                published_rank=entry.rank,
                name=entry.name,
                general_id=general_id,
                status=status,
                our_rank=rank_by_general_id.get(general_id) if general_id else None,
                our_battle_count=battle_count_by_general_id.get(general_id) if general_id else None,
            )
        )
    return rows


def spearman_correlation(pairs: list[tuple[float, float]]) -> float | None:
    """Pearson correlation of two already-ranked sequences (Spearman, since both inputs are
    ranks). `None` if fewer than 2 pairs -- correlation over 0 or 1 points is undefined, not 0.

    No scipy dependency (not in requirements.txt, same reasoning as
    `scripts/sensitivity_test.py`'s own `spearman_correlation`) -- plain mean/variance.
    """
    n = len(pairs)
    if n < 2:
        return None
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def rank_correlation_by_source(rows: list[ComparisonRow]) -> dict[str, float | None]:
    """Spearman correlation between published rank and our composite rank, per source, over
    only the entries that resolved to a ranked roster general. `None` for a source with fewer
    than 2 such entries (reference lists are short -- 7-15 entries -- so this is common)."""
    by_source: dict[str, list[tuple[float, float]]] = {}
    for row in rows:
        if row.status != "ranked":
            continue
        by_source.setdefault(row.source, []).append((float(row.published_rank), float(row.our_rank)))
    return {source: spearman_correlation(pairs) for source, pairs in by_source.items()}


def biggest_disagreements(
    rows: list[ComparisonRow],
    list_size_by_source: dict[str, int],
    roster_ranked_count: int,
    top_k: int = 10,
) -> list[dict]:
    """The `top_k` "ranked" entries whose published-list percentile and our composite-ranking
    percentile disagree the most (e.g. a list's #1 pick who we rank near the bottom of the
    roster, or vice versa). Percentile, not raw rank, because the published lists (7-15 entries)
    and the full roster (hundreds) are on completely different scales -- only a scale-free
    measure is comparable across both. Percentile is `(rank - 1) / (size - 1)`, 0 at the top and
    1 at the bottom regardless of list size, so a #1 pick on a 7-entry list and a #1 pick on a
    340-entry roster both score 0 (`rank / size` would never let a short list's #1 match a long
    list's #1 exactly). A size-1 list (nothing to rank against) scores everyone 0.
    """
    scored = []
    for row in rows:
        if row.status != "ranked":
            continue
        list_size = list_size_by_source[row.source]
        published_pct = (row.published_rank - 1) / (list_size - 1) if list_size > 1 else 0.0
        our_pct = (row.our_rank - 1) / (roster_ranked_count - 1) if roster_ranked_count > 1 else 0.0
        scored.append((abs(our_pct - published_pct), published_pct, our_pct, row))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [
        {
            "source": row.source,
            "name": row.name,
            "general_id": row.general_id,
            "published_rank": row.published_rank,
            "published_percentile": round(published_pct, 3),
            "our_rank": row.our_rank,
            "our_percentile": round(our_pct, 3),
            "disagreement": round(disagreement, 3),
        }
        for disagreement, published_pct, our_pct, row in scored[:top_k]
    ]
