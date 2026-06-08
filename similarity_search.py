#!/usr/bin/env python3
"""
Parallel similarity search across the split-by-year SQLite layout.

For a given seed DOI, score every paper in the requested year range by Jaccard
similarity of citation neighborhoods, and return the top-N. Each year DB is
scored in its own process so a full-library scan stays interactive.

Usage as a library
------------------
    from similarity_search import find_similar

    hits = find_similar(
        seed_doi="10.1063/5.0303752",
        year_min=2020, year_max=2026,
        top_n=50,
        direction="both",     # forward | backward | both
    )
    for h in hits:
        print(h["similarity"], h["doi"], h["title"])

CLI
---
    python similarity_search.py SEED_DOI [--year-min Y] [--year-max Y]
        [--top N] [--direction forward|backward|both]
        [--workers N] [--output FIELDS] [--header]

    --output: comma-separated field list. Valid: doi, year, title, journal,
              similarity. Default: doi.
"""

from __future__ import annotations

import argparse
import heapq
import os
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor

from db_sqlite import (
    DB_DIR,
    UNKNOWN_YEAR_KEY,
    _connect_index,
    _year_db_path,
    _year_key,
    get_paper,
    get_metadata_batch,
)


# ---------------------------------------------------------------------------
# Year-key discovery
# ---------------------------------------------------------------------------

def _candidate_year_keys(year_min: int | None,
                         year_max: int | None,
                         include_unknown: bool) -> list[str]:
    """Year DBs to scan, filtered to the requested range."""
    keys: list[str] = []
    if not os.path.isdir(DB_DIR):
        return keys
    for name in os.listdir(DB_DIR):
        if not name.endswith(".db") or name == "index.db":
            continue
        stem = name[:-3]
        if stem == UNKNOWN_YEAR_KEY:
            if include_unknown:
                keys.append(stem)
            continue
        try:
            y = int(stem)
        except ValueError:
            continue
        if year_min is not None and y < year_min:
            continue
        if year_max is not None and y > year_max:
            continue
        keys.append(stem)
    return sorted(keys)


# ---------------------------------------------------------------------------
# Per-year worker (must be module-level so ProcessPoolExecutor can pickle it)
# ---------------------------------------------------------------------------

def _score_year(args: tuple) -> list[tuple[float, str, int]]:
    """Open one year DB, compute Jaccard for every source against the seed
    citation set, return that year's local top-N."""
    year_key, seed_cits, direction, top_n, seed_doi = args
    if not seed_cits:
        return []

    path = os.path.join(DB_DIR, f"{year_key}.db")
    if not os.path.exists(path):
        return []

    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        if direction in ("forward", "backward"):
            rows = conn.execute(
                "SELECT source_doi, target_doi FROM citations WHERE direction=?",
                (direction,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT source_doi, target_doi FROM citations"
            ).fetchall()
    finally:
        conn.close()

    # Group target DOIs by source
    groups: dict[str, set] = {}
    for r in rows:
        groups.setdefault(r["source_doi"], set()).add(r["target_doi"])

    seed_size = len(seed_cits)
    heap: list[tuple[float, str, int]] = []  # min-heap on similarity
    for src, targets in groups.items():
        if src == seed_doi or not targets:
            continue
        inter = len(targets & seed_cits)
        if inter == 0:
            continue
        union = len(targets) + seed_size - inter
        sim = inter / union
        if len(heap) < top_n:
            heapq.heappush(heap, (sim, src, len(targets)))
        elif sim > heap[0][0]:
            heapq.heapreplace(heap, (sim, src, len(targets)))
    return heap


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_similar(seed_doi: str,
                 year_min: int | None = None,
                 year_max: int | None = None,
                 top_n: int = 50,
                 workers: int | None = None,
                 direction: str = "both",
                 include_unknown: bool = False) -> list[dict]:
    """Return up to *top_n* papers most similar to *seed_doi*, sorted by
    Jaccard similarity descending.

    Parameters
    ----------
    seed_doi
        Must already be present in the database.
    year_min, year_max
        Inclusive candidate year range. None means open-ended.
    top_n
        Number of results to return (default 50).
    workers
        Worker process count. Default: min(cpu_count, 8).
    direction
        "forward", "backward", or "both" — which citation lists to compare.
    include_unknown
        If True, also scan unknown.db for unknown-year candidates.

    Returns
    -------
    list[dict] with keys: doi, year, title, journal, similarity, citation_count.
    """
    if direction not in ("forward", "backward", "both"):
        raise ValueError("direction must be 'forward', 'backward', or 'both'")

    seed = get_paper(seed_doi)
    if seed is None:
        raise ValueError(f"Seed DOI not found in DB: {seed_doi}")

    if direction == "forward":
        seed_cits = set(seed["forward"])
    elif direction == "backward":
        seed_cits = set(seed["backward"])
    else:
        seed_cits = set(seed["forward"]) | set(seed["backward"])

    if not seed_cits:
        return []

    year_keys = _candidate_year_keys(year_min, year_max, include_unknown)
    if not year_keys:
        return []

    if workers is None:
        workers = min(8, max(1, os.cpu_count() or 4))

    tasks = [(yk, seed_cits, direction, top_n, seed_doi) for yk in year_keys]

    merged: list[tuple[float, str, int]] = []
    if workers <= 1 or len(tasks) <= 1:
        for t in tasks:
            merged.extend(_score_year(t))
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for partial in pool.map(_score_year, tasks):
                merged.extend(partial)

    merged.sort(key=lambda x: -x[0])
    merged = merged[:top_n]
    if not merged:
        return []

    meta = get_metadata_batch([src for _, src, _ in merged])

    out: list[dict] = []
    for sim, src, n_cits in merged:
        m = meta.get(src, {}).get("metadata", {})
        out.append({
            "doi": src,
            "year": m.get("year"),
            "title": m.get("title"),
            "journal": m.get("journal"),
            "similarity": sim,
            "citation_count": n_cits,
        })
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_VALID_FIELDS = ("doi", "year", "title", "journal", "similarity")


def _format_field(value, field: str) -> str:
    if value is None:
        return ""
    if field == "similarity" and isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _cli() -> int:
    p = argparse.ArgumentParser(
        prog="similarity_search.py",
        description=(
            "Find papers most similar to a seed DOI by Jaccard similarity of "
            "their citation neighborhoods."
        ),
    )
    p.add_argument("seed_doi", help="Seed paper DOI (must already be in the DB).")
    p.add_argument("--year-min", type=int, default=None,
                   help="Minimum candidate year (inclusive).")
    p.add_argument("--year-max", type=int, default=None,
                   help="Maximum candidate year (inclusive).")
    p.add_argument("--top", type=int, default=50,
                   help="Number of results to print (default 50).")
    p.add_argument("--direction", choices=("forward", "backward", "both"),
                   default="both",
                   help="Citation list to compare (default both).")
    p.add_argument("--workers", type=int, default=None,
                   help="Parallel worker processes (default: min(cpu_count, 8)).")
    p.add_argument("--include-unknown", action="store_true",
                   help="Also scan unknown.db (papers with NULL year).")
    p.add_argument("--output", default="doi",
                   help=("Comma-separated fields to print, in order. "
                         f"Valid: {','.join(_VALID_FIELDS)}. Default: doi."))
    p.add_argument("--header", action="store_true",
                   help="Print a TSV header row before results.")
    args = p.parse_args()

    fields = [f.strip().lower() for f in args.output.split(",") if f.strip()]
    bad = [f for f in fields if f not in _VALID_FIELDS]
    if bad:
        print(f"Invalid --output fields: {bad}. Valid: {list(_VALID_FIELDS)}",
              file=sys.stderr)
        return 2

    try:
        results = find_similar(
            args.seed_doi,
            year_min=args.year_min,
            year_max=args.year_max,
            top_n=args.top,
            workers=args.workers,
            direction=args.direction,
            include_unknown=args.include_unknown,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if args.header:
        print("\t".join(fields))
    for r in results:
        print("\t".join(_format_field(r.get(f), f) for f in fields))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
