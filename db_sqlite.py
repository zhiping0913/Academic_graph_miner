"""
SQLite backend for the academic knowledge graph.

Schema
------
papers   : one row per paper (basic metadata, indexed by integer id)
citations: one row per (source_paper, target_doi, direction) triple
           coefficient is NULL for raw (unclassified) edges,
           non-NULL after Jaccard scoring
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from backend import DB_PATH

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------

def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db():
    with _connect() as conn:
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

            CREATE TABLE IF NOT EXISTS citations (
                source_id   INTEGER NOT NULL
                                REFERENCES papers(id) ON DELETE CASCADE,
                target_doi  TEXT    NOT NULL,
                direction   TEXT    NOT NULL
                                CHECK(direction IN ('forward','backward')),
                coefficient REAL,        -- NULL = raw; non-NULL = classified
                PRIMARY KEY (source_id, target_doi, direction)
            );

            CREATE INDEX IF NOT EXISTS idx_cit_source
                ON citations(source_id, direction);
        """)


# ---------------------------------------------------------------------------
# Single-paper read / write
# ---------------------------------------------------------------------------

def get_paper(doi: str) -> dict | None:
    """Return one paper as a dict (same shape as the old JSON entries), or None."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM papers WHERE doi=?", (doi,)).fetchone()
        if row is None:
            return None
        return _row_to_dict(conn, row)


def upsert_paper(paper_data: dict):
    """Insert or update a single paper and its citation lists."""
    doi = paper_data["doi"]
    meta = paper_data.get("metadata", {})

    with _connect() as conn:
        conn.execute("""
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

        paper_id = conn.execute(
            "SELECT id FROM papers WHERE doi=?", (doi,)
        ).fetchone()[0]

        # Wipe existing citation rows for this paper and reinsert
        conn.execute("DELETE FROM citations WHERE source_id=?", (paper_id,))

        rows = []
        for direction in ("forward", "backward"):
            # Raw (unclassified) edges
            for target in paper_data.get(direction, []):
                rows.append((paper_id, target, direction, None))
            # Classified edges (override coefficient)
            for entry in paper_data.get(f"classified_{direction}", []):
                rows.append((paper_id, entry["doi"], direction, entry["coefficient"]))

        # Deduplicate: for same (source, target, direction) keep the one with coefficient
        seen: dict[tuple, float | None] = {}
        for source_id, target_doi, direction, coeff in rows:
            key = (source_id, target_doi, direction)
            if key not in seen or coeff is not None:
                seen[key] = coeff
        conn.executemany(
            "INSERT OR REPLACE INTO citations (source_id, target_doi, direction, coefficient) "
            "VALUES (?, ?, ?, ?)",
            [(k[0], k[1], k[2], v) for k, v in seen.items()],
        )


# ---------------------------------------------------------------------------
# Bulk read / write (drop-in replacements for the old JSON load_db/save_db)
# ---------------------------------------------------------------------------

def load_db() -> dict:
    """Load every paper into a {doi: paper_dict} mapping (same shape as old JSON)."""
    with _connect() as conn:
        papers = conn.execute("SELECT * FROM papers").fetchall()
        return {row["doi"]: _row_to_dict(conn, row) for row in papers}


def save_db(db: dict):
    """Batch-upsert every paper in *db*. Prefer upsert_paper() for incremental saves."""
    for paper_data in db.values():
        upsert_paper(paper_data)


# ---------------------------------------------------------------------------
# Expiry check
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

def _row_to_dict(conn, row) -> dict:
    paper_id = row["id"]
    doi = row["doi"]

    cits = conn.execute(
        "SELECT target_doi, direction, coefficient FROM citations WHERE source_id=?",
        (paper_id,),
    ).fetchall()

    forward_raw, backward_raw = [], []
    classified_forward, classified_backward = [], []
    for c in cits:
        if c["direction"] == "forward":
            forward_raw.append(c["target_doi"])
            if c["coefficient"] is not None:
                classified_forward.append({"doi": c["target_doi"], "coefficient": c["coefficient"]})
        else:
            backward_raw.append(c["target_doi"])
            if c["coefficient"] is not None:
                classified_backward.append({"doi": c["target_doi"], "coefficient": c["coefficient"]})

    return {
        "doi": doi,
        "metadata": {
            "title": row["title"],
            "year": row["year"],
            "journal": row["journal"],
            "authors": json.loads(row["authors"]) if row["authors"] else [],
        },
        "forward": forward_raw,
        "backward": backward_raw,
        "classified_forward": classified_forward,
        "classified_backward": classified_backward,
        "last_updated": row["last_updated"],
    }


# Ensure schema exists on first import
init_db()
