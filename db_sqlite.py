"""
SQLite backend for the academic knowledge graph (split-by-year layout).

Layout
------
database/
    index.db       one row per paper: doi, title, year, journal, authors, last_updated
    {year}.db      citations whose source paper was published in {year}
    unknown.db     citations for papers with NULL / non-integer year

All database access in this project MUST go through this module.

Public API (preserved across the refactor)
------------------------------------------
init_db()                             create / migrate schema
get_paper(doi)        -> dict | None  single-paper read
upsert_paper(data)                    single-paper write
load_db()             -> dict         bulk read into {doi: paper_dict}
save_db(db)                           bulk write
is_expired(...)       -> bool         metadata-age helper
DB_PATH               (str)           kept for backward compatibility — points at
                                      the new split-DB directory; only used by
                                      callers that print it

Migration
---------
migrate_from_legacy([path]) reads the old single-file academic_knowledge_graph.db
and populates the split layout. Can also be invoked as `python db_sqlite.py migrate`.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from backend import OUTPUT_PATH

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DB_DIR = os.path.join(OUTPUT_PATH, "database")
INDEX_DB_PATH = os.path.join(DB_DIR, "index.db")
UNKNOWN_YEAR_KEY = "unknown"

# Backward-compatible alias. Used only for print statements in graph_server.py
# and data_export.py; now points at the directory holding the split layout.
DB_PATH = DB_DIR

os.makedirs(DB_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _connect_index() -> sqlite3.Connection:
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _year_key(year) -> str:
    """Map a paper's year value to the year-DB key used as a filename stem."""
    if year is None or year == "":
        return UNKNOWN_YEAR_KEY
    try:
        return str(int(year))
    except (TypeError, ValueError):
        return UNKNOWN_YEAR_KEY


def _year_db_path(year_key: str) -> str:
    return os.path.join(DB_DIR, f"{year_key}.db")


def _connect_year(year_key: str, *, readonly: bool = False) -> sqlite3.Connection:
    """Open the year-DB file for *year_key*.

    readonly=False (default): create the file + schema if missing.
    readonly=True: open existing file without schema init — much faster when
    opening many files for bulk reads.
    """
    path = _year_db_path(year_key)
    if readonly:
        # No schema init — caller guarantees the file already exists.
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS citations (
            source_doi  TEXT NOT NULL,
            target_doi  TEXT NOT NULL,
            direction   TEXT NOT NULL
                            CHECK(direction IN ('forward','backward')),
            coefficient REAL,
            PRIMARY KEY (source_doi, target_doi, direction)
        );
        CREATE INDEX IF NOT EXISTS idx_cit_src
            ON citations(source_doi, direction);
        CREATE INDEX IF NOT EXISTS idx_cit_tgt
            ON citations(target_doi, direction);
    """)
    return conn


def list_available_years() -> list[str]:
    """Sorted list of year keys whose .db files currently exist on disk."""
    out = []
    for name in os.listdir(DB_DIR):
        if name.endswith(".db") and name != "index.db":
            out.append(name[:-3])
    return sorted(out, key=lambda k: (k == UNKNOWN_YEAR_KEY, k))


# ---------------------------------------------------------------------------
# Naming bridge:
#
# The public Python API uses `citation` (incoming — who cites this paper) and
# `reference` (outgoing — what this paper cites). The on-disk SQLite schema
# was originally written with `direction='forward'` for the Citation list and
# `direction='backward'` for the Reference list. Migrating 13.7M rows across
# 156 year DBs has zero functional benefit, so the DB keeps its old column
# values and every read/write through this module translates at the boundary.
# Nothing outside this module should reference the strings 'forward'/'backward'.
# ---------------------------------------------------------------------------

_KEY_TO_DB_DIR = {"citation": "forward", "reference": "backward"}
_DB_DIR_TO_KEY = {v: k for k, v in _KEY_TO_DB_DIR.items()}


def _to_db_direction(key: str) -> str:
    try:
        return _KEY_TO_DB_DIR[key]
    except KeyError as e:
        raise ValueError(
            f"direction must be 'citation' or 'reference'; got {key!r}"
        ) from e


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db() -> None:
    os.makedirs(DB_DIR, exist_ok=True)
    conn = _connect_index()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS papers (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                doi          TEXT    UNIQUE NOT NULL,
                title        TEXT,
                year         INTEGER,
                journal      TEXT,
                authors      TEXT,        -- JSON array stored as text
                last_updated TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_papers_year ON papers(year);
        """)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Single-paper read
# ---------------------------------------------------------------------------

def get_paper(doi: str) -> dict | None:
    """Return one paper as a dict (same shape as the old JSON entries), or None."""
    idx = _connect_index()
    try:
        row = idx.execute("SELECT * FROM papers WHERE doi=?", (doi,)).fetchone()
    finally:
        idx.close()
    if row is None:
        return None

    year_key = _year_key(row["year"])
    citations: list = []
    if os.path.exists(_year_db_path(year_key)):
        ycon = _connect_year(year_key)
        try:
            citations = ycon.execute(
                "SELECT target_doi, direction, coefficient "
                "FROM citations WHERE source_doi=?",
                (doi,),
            ).fetchall()
        finally:
            ycon.close()
    return _build_paper_dict(row, citations)


# ---------------------------------------------------------------------------
# Single-paper write
# ---------------------------------------------------------------------------

def upsert_paper(paper_data: dict) -> None:
    """Insert or update a single paper and its citation lists.

    If the paper already exists with a different year, its citations are
    deleted from the old year-DB before being written to the new one.
    """
    doi = paper_data["doi"]
    meta = paper_data.get("metadata", {})
    new_year_key = _year_key(meta.get("year"))

    # ---- metadata ---------------------------------------------------------
    idx = _connect_index()
    try:
        old_row = idx.execute(
            "SELECT year FROM papers WHERE doi=?", (doi,)
        ).fetchone()
        old_year_key = _year_key(old_row["year"]) if old_row else None

        idx.execute("""
            INSERT INTO papers (doi, title, year, journal, authors, last_updated)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(doi) DO UPDATE SET
                title        = excluded.title,
                year         = excluded.year,
                journal      = excluded.journal,
                authors      = excluded.authors,
                last_updated = excluded.last_updated
        """, (
            doi,
            meta.get("title"),
            meta.get("year"),
            meta.get("journal"),
            json.dumps(meta.get("authors", []), ensure_ascii=False),
            paper_data.get("last_updated"),
        ))
        idx.commit()
    finally:
        idx.close()

    # ---- build citation rows ---------------------------------------------
    # Public keys are citation/reference; DB still uses forward/backward.
    rows: list[tuple] = []
    for key, db_dir in _KEY_TO_DB_DIR.items():
        for target in paper_data.get(key, []):
            rows.append((doi, target, db_dir, None))
        for entry in paper_data.get(f"classified_{key}", []):
            rows.append((doi, entry["doi"], db_dir, entry["coefficient"]))

    # Dedup: prefer the row with a non-null coefficient
    seen: dict[tuple, float | None] = {}
    for s, t, d, c in rows:
        key = (s, t, d)
        if key not in seen or c is not None:
            seen[key] = c

    # ---- if the year changed, drop citations from the old year DB --------
    if old_year_key is not None and old_year_key != new_year_key:
        old_path = _year_db_path(old_year_key)
        if os.path.exists(old_path):
            old_con = _connect_year(old_year_key)
            try:
                old_con.execute(
                    "DELETE FROM citations WHERE source_doi=?", (doi,)
                )
                old_con.commit()
            finally:
                old_con.close()

    # ---- write to the new year DB ----------------------------------------
    ycon = _connect_year(new_year_key)
    try:
        ycon.execute("DELETE FROM citations WHERE source_doi=?", (doi,))
        if seen:
            ycon.executemany(
                "INSERT OR REPLACE INTO citations "
                "(source_doi, target_doi, direction, coefficient) "
                "VALUES (?, ?, ?, ?)",
                [(k[0], k[1], k[2], v) for k, v in seen.items()],
            )
        ycon.commit()
    finally:
        ycon.close()


# ---------------------------------------------------------------------------
# Bulk read / write
# ---------------------------------------------------------------------------

def load_db() -> dict:
    """Load every paper into a {doi: paper_dict} mapping (old JSON shape)."""
    idx = _connect_index()
    try:
        papers = idx.execute("SELECT * FROM papers").fetchall()
    finally:
        idx.close()

    by_year: dict[str, list] = {}
    for row in papers:
        by_year.setdefault(_year_key(row["year"]), []).append(row)

    result: dict[str, dict] = {}
    # SQLite default SQLITE_MAX_VARIABLE_NUMBER is 999 on older builds; chunk
    # IN-clauses to stay safe.
    CHUNK = 500
    for year_key, rows in by_year.items():
        path = _year_db_path(year_key)
        if not os.path.exists(path):
            for row in rows:
                result[row["doi"]] = _build_paper_dict(row, [])
            continue

        cits_by_src: dict[str, list] = {}
        ycon = _connect_year(year_key)
        try:
            dois = [r["doi"] for r in rows]
            for i in range(0, len(dois), CHUNK):
                chunk = dois[i:i + CHUNK]
                placeholders = ",".join("?" * len(chunk))
                cits = ycon.execute(
                    f"SELECT source_doi, target_doi, direction, coefficient "
                    f"FROM citations WHERE source_doi IN ({placeholders})",
                    chunk,
                ).fetchall()
                for c in cits:
                    cits_by_src.setdefault(c["source_doi"], []).append(c)
        finally:
            ycon.close()

        for row in rows:
            result[row["doi"]] = _build_paper_dict(
                row, cits_by_src.get(row["doi"], [])
            )

    return result


def save_db(db: dict) -> None:
    """Batch-upsert every paper in *db*. Prefer upsert_paper() for incremental saves."""
    for paper_data in db.values():
        upsert_paper(paper_data)


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

def is_expired(last_updated_str: str | None, update_days: int = 1000) -> bool:
    if not last_updated_str:
        return True
    try:
        last_date = datetime.strptime(last_updated_str, "%Y-%m-%d")
        return datetime.now() > last_date + timedelta(days=update_days)
    except Exception:
        return True


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------

def _build_paper_dict(row, citations) -> dict:
    citation, reference = [], []
    classified_citation, classified_reference = [], []
    for c in citations:
        key = _DB_DIR_TO_KEY[c["direction"]]
        if key == "citation":
            citation.append(c["target_doi"])
            if c["coefficient"] is not None:
                classified_citation.append(
                    {"doi": c["target_doi"], "coefficient": c["coefficient"]}
                )
        else:
            reference.append(c["target_doi"])
            if c["coefficient"] is not None:
                classified_reference.append(
                    {"doi": c["target_doi"], "coefficient": c["coefficient"]}
                )

    return {
        "doi": row["doi"],
        "metadata": {
            "title": row["title"],
            "year": row["year"],
            "journal": row["journal"],
            "authors": json.loads(row["authors"]) if row["authors"] else [],
        },
        "citation": citation,
        "reference": reference,
        "classified_citation": classified_citation,
        "classified_reference": classified_reference,
        "last_updated": row["last_updated"],
    }


# ---------------------------------------------------------------------------
# Year-scoped bulk reads (cheap; touches only the requested year DBs)
# ---------------------------------------------------------------------------

def load_db_year_range(year_min: int | None,
                       year_max: int | None,
                       include_unknown: bool = False) -> dict:
    """Load every paper whose year falls in [year_min, year_max] (inclusive)
    into the same {doi: paper_dict} shape used by load_db().

    None on either bound means open-ended on that side.
    include_unknown=True additionally pulls in papers with NULL year.
    """
    range_parts, params = [], []
    if year_min is not None:
        range_parts.append("year >= ?")
        params.append(year_min)
    if year_max is not None:
        range_parts.append("year <= ?")
        params.append(year_max)
    range_clause = " AND ".join(range_parts) if range_parts else "year IS NOT NULL"

    if include_unknown:
        where = f"WHERE ({range_clause}) OR year IS NULL"
    else:
        where = f"WHERE {range_clause}"

    idx = _connect_index()
    try:
        rows = idx.execute(f"SELECT * FROM papers {where}", params).fetchall()
    finally:
        idx.close()
    return _load_with_citations(rows)


def load_db_year(year) -> dict:
    """Convenience wrapper: load papers for a single year (int) or the
    unknown bucket (pass None or 'unknown')."""
    if year is None or (isinstance(year, str) and year.lower() == UNKNOWN_YEAR_KEY):
        idx = _connect_index()
        try:
            rows = idx.execute(
                "SELECT * FROM papers WHERE year IS NULL"
            ).fetchall()
        finally:
            idx.close()
        return _load_with_citations(rows)
    y = int(year)
    return load_db_year_range(y, y)


def _load_with_citations(rows) -> dict:
    """Shared body of load_db / load_db_year_range — given a set of paper rows,
    join their citations from the appropriate year DBs and build paper_dicts."""
    by_year: dict[str, list] = {}
    for row in rows:
        by_year.setdefault(_year_key(row["year"]), []).append(row)

    result: dict[str, dict] = {}
    CHUNK = 500
    for year_key, group in by_year.items():
        path = _year_db_path(year_key)
        if not os.path.exists(path):
            for row in group:
                result[row["doi"]] = _build_paper_dict(row, [])
            continue

        cits_by_src: dict[str, list] = {}
        ycon = _connect_year(year_key)
        try:
            dois = [r["doi"] for r in group]
            for i in range(0, len(dois), CHUNK):
                chunk = dois[i:i + CHUNK]
                placeholders = ",".join("?" * len(chunk))
                cits = ycon.execute(
                    f"SELECT source_doi, target_doi, direction, coefficient "
                    f"FROM citations WHERE source_doi IN ({placeholders})",
                    chunk,
                ).fetchall()
                for c in cits:
                    cits_by_src.setdefault(c["source_doi"], []).append(c)
        finally:
            ycon.close()

        for row in group:
            result[row["doi"]] = _build_paper_dict(
                row, cits_by_src.get(row["doi"], [])
            )
    return result


# ---------------------------------------------------------------------------
# Metadata-only operations (do not touch year DBs)
# ---------------------------------------------------------------------------

def get_metadata(doi: str) -> dict | None:
    """Fast metadata-only lookup (no citation load)."""
    idx = _connect_index()
    try:
        row = idx.execute(
            "SELECT doi, title, year, journal, authors, last_updated "
            "FROM papers WHERE doi=?", (doi,),
        ).fetchone()
    finally:
        idx.close()
    if row is None:
        return None
    return _metadata_row_to_dict(row)


def get_metadata_batch(dois: list[str]) -> dict[str, dict]:
    """Batch metadata fetch keyed by DOI."""
    if not dois:
        return {}
    out: dict[str, dict] = {}
    CHUNK = 500
    idx = _connect_index()
    try:
        for i in range(0, len(dois), CHUNK):
            chunk = dois[i:i + CHUNK]
            placeholders = ",".join("?" * len(chunk))
            rows = idx.execute(
                f"SELECT doi, title, year, journal, authors, last_updated "
                f"FROM papers WHERE doi IN ({placeholders})",
                chunk,
            ).fetchall()
            for r in rows:
                out[r["doi"]] = _metadata_row_to_dict(r)
    finally:
        idx.close()
    return out


def list_papers_paginated(year_min: int | None = None,
                          year_max: int | None = None,
                          search: str = "",
                          sort_by: str = "year_desc",
                          page: int = 1,
                          per_page: int = 50) -> tuple[list[dict], int]:
    """SQL-paginated listing of papers from index.db (metadata only).

    Returns
    -------
    (rows, total) where rows is a list of metadata dicts of length <= per_page
    and total is the total number of matches across all pages.

    Supported sort_by values: year_desc (default), year_asc, title_asc.
    Year filter is inclusive on both bounds; None means open-ended on that side.
    """
    clauses, params = [], []
    if year_min is not None:
        clauses.append("year >= ?")
        params.append(year_min)
    if year_max is not None:
        clauses.append("year <= ?")
        params.append(year_max)
    if search:
        like = f"%{search.lower()}%"
        clauses.append("(lower(doi) LIKE ? OR lower(title) LIKE ?)")
        params.extend([like, like])
    if year_min is None and year_max is None and not search:
        clauses.append("year IS NOT NULL")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    order = {
        "year_desc": "year DESC NULLS LAST, title ASC",
        "year_asc":  "year ASC NULLS LAST, title ASC",
        "title_asc": "title ASC",
    }.get(sort_by, "year DESC NULLS LAST, title ASC")

    offset = max(0, (page - 1) * per_page)

    idx = _connect_index()
    try:
        total = idx.execute(
            f"SELECT COUNT(*) FROM papers {where}", params
        ).fetchone()[0]
        rows = idx.execute(
            f"SELECT doi, title, year, journal, authors, last_updated "
            f"FROM papers {where} ORDER BY {order} LIMIT ? OFFSET ?",
            (*params, per_page, offset),
        ).fetchall()
    finally:
        idx.close()
    return [_metadata_row_to_dict(r) for r in rows], total


def search_metadata(query: str, limit: int = 20) -> list[dict]:
    """SQL LIKE search on doi + title via index.db (no citation load).

    Returns a list of metadata dicts, ranked: DOI-prefix matches first,
    then title-substring matches.
    """
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    idx = _connect_index()
    try:
        rows = idx.execute(
            "SELECT doi, title, year, journal, authors, last_updated, "
            "       (CASE WHEN lower(doi) LIKE ? THEN 0 ELSE 1 END) AS rank "
            "FROM papers "
            "WHERE lower(doi) LIKE ? OR lower(title) LIKE ? "
            "ORDER BY rank, year DESC NULLS LAST, title "
            "LIMIT ?",
            (f"{q}%", like, like, limit),
        ).fetchall()
    finally:
        idx.close()
    return [_metadata_row_to_dict(r) for r in rows]


def _metadata_row_to_dict(row) -> dict:
    return {
        "doi": row["doi"],
        "metadata": {
            "title": row["title"],
            "year": row["year"],
            "journal": row["journal"],
            "authors": json.loads(row["authors"]) if row["authors"] else [],
        },
        "last_updated": row["last_updated"],
    }


# ---------------------------------------------------------------------------
# Citation-count helpers (touch year DBs but skip building neighbor lists)
# ---------------------------------------------------------------------------

def get_citation_counts(dois: list[str]) -> dict[str, dict]:
    """Return {doi: {'citation': N, 'reference': N}} via per-year batch queries.

    'citation' = number of papers citing this DOI (incoming).
    'reference' = number of papers this DOI cites (outgoing).
    """
    if not dois:
        return {}

    meta = get_metadata_batch(dois)
    by_year: dict[str, list[str]] = {}
    for d in dois:
        m = meta.get(d)
        yk = _year_key(m["metadata"]["year"]) if m else UNKNOWN_YEAR_KEY
        by_year.setdefault(yk, []).append(d)

    out: dict[str, dict] = {d: {"citation": 0, "reference": 0} for d in dois}
    CHUNK = 500
    for year_key, group in by_year.items():
        path = _year_db_path(year_key)
        if not os.path.exists(path):
            continue
        ycon = _connect_year(year_key)
        try:
            for i in range(0, len(group), CHUNK):
                chunk = group[i:i + CHUNK]
                placeholders = ",".join("?" * len(chunk))
                rows = ycon.execute(
                    f"SELECT source_doi, direction, COUNT(*) AS n "
                    f"FROM citations WHERE source_doi IN ({placeholders}) "
                    f"GROUP BY source_doi, direction",
                    chunk,
                ).fetchall()
                for r in rows:
                    out[r["source_doi"]][_DB_DIR_TO_KEY[r["direction"]]] = r["n"]
        finally:
            ycon.close()
    return out


# ---------------------------------------------------------------------------
# Reverse-citation query (who cites target_doi)
# ---------------------------------------------------------------------------

def find_citing_dois(target_doi: str,
                     direction: str = "reference",
                     workers: int | None = None) -> list[str]:
    """Return every source_doi that has *target_doi* in the given direction.

    The default ``direction='reference'`` returns the citers of ``target_doi``
    — papers whose own Reference list contains it. Pass ``direction='citation'``
    for the inverse query (papers that list ``target_doi`` in their Citation
    list, which mirrors ``target_doi``'s own References when only one side of
    the edge has been mined).

    Scans every year DB in parallel (idx_cit_tgt makes per-file lookup O(log n)).
    """
    db_dir = _to_db_direction(direction)
    from concurrent.futures import ThreadPoolExecutor

    if workers is None:
        workers = min(16, max(2, (os.cpu_count() or 4) * 2))

    def _scan_one(year_key: str) -> list[str]:
        path = _year_db_path(year_key)
        if not os.path.exists(path):
            return []
        ycon = _connect_year(year_key, readonly=True)
        try:
            rows = ycon.execute(
                "SELECT source_doi FROM citations "
                "WHERE target_doi=? AND direction=?",
                (target_doi, db_dir),
            ).fetchall()
            return [r["source_doi"] for r in rows]
        finally:
            ycon.close()

    out: list[str] = []
    seen: set[str] = set()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for partial in pool.map(_scan_one, list_available_years()):
            for src in partial:
                if src not in seen:
                    seen.add(src)
                    out.append(src)
    return out


# ---------------------------------------------------------------------------
# Migration from the legacy single-file DB
# ---------------------------------------------------------------------------

def migrate_from_legacy(legacy_path: str | None = None,
                        chunk_size: int = 500) -> None:
    """Copy the old single-file academic_knowledge_graph.db into the split layout."""
    if legacy_path is None:
        legacy_path = os.path.join(OUTPUT_PATH, "academic_knowledge_graph.db")
    if not os.path.exists(legacy_path):
        raise FileNotFoundError(f"Legacy DB not found: {legacy_path}")

    init_db()
    src = sqlite3.connect(legacy_path)
    src.row_factory = sqlite3.Row

    try:
        paper_rows = src.execute(
            "SELECT id, doi, title, year, journal, authors, last_updated "
            "FROM papers"
        ).fetchall()
        total = len(paper_rows)
        print(f"Migrating {total} papers from legacy DB → {DB_DIR}")

        id_to_doi: dict[int, str] = {}
        by_year: dict[str, list] = {}
        for row in paper_rows:
            id_to_doi[row["id"]] = row["doi"]
            by_year.setdefault(_year_key(row["year"]), []).append(row)

        # ---- write index.db -------------------------------------------------
        idx = _connect_index()
        try:
            idx.executemany("""
                INSERT INTO papers
                    (doi, title, year, journal, authors, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(doi) DO UPDATE SET
                    title        = excluded.title,
                    year         = excluded.year,
                    journal      = excluded.journal,
                    authors      = excluded.authors,
                    last_updated = excluded.last_updated
            """, [
                (r["doi"], r["title"], r["year"], r["journal"],
                 r["authors"], r["last_updated"])
                for r in paper_rows
            ])
            idx.commit()
        finally:
            idx.close()
        print(f"  index.db populated: {total} papers")

        # ---- write per-year citation DBs -----------------------------------
        for year_key in sorted(by_year.keys()):
            rows = by_year[year_key]
            ids = [r["id"] for r in rows]

            collected = []
            for i in range(0, len(ids), chunk_size):
                chunk = ids[i:i + chunk_size]
                placeholders = ",".join("?" * len(chunk))
                cits = src.execute(
                    f"SELECT source_id, target_doi, direction, coefficient "
                    f"FROM citations WHERE source_id IN ({placeholders})",
                    chunk,
                ).fetchall()
                collected.extend(cits)

            if not collected:
                continue

            ycon = _connect_year(year_key)
            try:
                ycon.executemany(
                    "INSERT OR REPLACE INTO citations "
                    "(source_doi, target_doi, direction, coefficient) "
                    "VALUES (?, ?, ?, ?)",
                    [
                        (id_to_doi[c["source_id"]], c["target_doi"],
                         c["direction"], c["coefficient"])
                        for c in collected
                    ],
                )
                ycon.commit()
            finally:
                ycon.close()
            print(f"  {year_key}.db: {len(collected)} citations "
                  f"from {len(rows)} papers")

        print("Migration complete.")
    finally:
        src.close()


# Ensure schema exists on first import
init_db()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "migrate":
        legacy = sys.argv[2] if len(sys.argv) > 2 else None
        migrate_from_legacy(legacy)
    else:
        print("Usage: python db_sqlite.py migrate [legacy_db_path]")
