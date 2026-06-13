# 💾 Database Module Reference (db_sqlite.py)

**File**: `db_sqlite.py`
**Purpose**: SQLite persistence layer for papers and citation relationships
**Status**: Production-ready

---

## 🗂️ Storage layout (v5, 2026-06-08)

The single-file `academic_knowledge_graph.db` has been split into the
`database/` directory:

```
database/
    index.db        papers metadata only (doi, title, year, journal, authors, last_updated)
    {year}.db       citations whose source paper was published in {year}
                    (citations(source_doi, target_doi, direction, coefficient))
    unknown.db      citations for papers with NULL / non-integer year
```

- The `papers` table lives in `index.db` and is indexed by `doi` (and by `year`).
- Each `{year}.db` keys citations by `source_doi` directly (no integer FK across files).
- `upsert_paper()` automatically deletes citations from the old year-DB when a
  paper's year changes.
- Year-DB files are created lazily on first write; missing files read as empty.
- Migration helper: `python db_sqlite.py migrate [legacy_db_path]` copies the
  old single-file DB into the new layout.

**All other modules (`fitch_citations`, `data_browser`, `graph_server`,
`data_export`, `visualize_graph`) access the database exclusively through
`db_sqlite`'s public API — do not open `index.db` or `{year}.db` directly.**

---

## 🎯 Quick Start

### Basic Usage

```python
from db_sqlite import load_db, get_paper, upsert_paper, init_db

# Ensure schema exists
init_db()

# Load entire database into memory
db = load_db()  # Returns {doi: paper_data}

# Query single paper
paper = get_paper("10.1038/nphys2439")
if paper:
    print(f"Title: {paper['metadata']['title']}")
    print(f"Citations (who cites this): {len(paper['citation'])}")
    print(f"References (what this cites): {len(paper['reference'])}")

# Add or update a paper
new_paper = {
    "doi": "10.xxxx",
    "metadata": {
        "title": "New Paper",
        "year": 2025,
        "journal": "Nature",
        "authors": ["Author1", "Author2"]
    },
    "citation":  ["10.aaaa", "10.bbbb"],   # who cites this paper
    "reference": ["10.cccc"],              # what this paper cites
    "classified_citation":  [{"doi": "10.aaaa", "coefficient": 0.35}],
    "classified_reference": [],
    "last_updated": "2026-04-21"
}
upsert_paper(new_paper)
```

---

## 🗄️ Database Schema

### Tables

#### `papers` Table
Stores paper metadata (one row per unique DOI)

```sql
CREATE TABLE papers (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    doi          TEXT    UNIQUE NOT NULL,
    title        TEXT,
    year         INTEGER,
    journal      TEXT,
    authors      TEXT,              -- JSON array stored as string
    last_updated TEXT               -- ISO format: "2026-04-21"
);
```

**Constraints**:
- `doi`: Unique identifier (e.g., "10.1038/nphys2439")
- `authors`: JSON array (e.g., `["Author1", "Author2"]`)

**Indexes**:
- Primary key on `id` (auto-generated)
- Implicit index on `doi` (UNIQUE constraint)

---

#### `citations` Table (one per `{year}.db`)
Stores directed citation relationships, sharded by the source paper's year.

```sql
CREATE TABLE citations (
    source_doi  TEXT NOT NULL,
    target_doi  TEXT NOT NULL,
    direction   TEXT NOT NULL CHECK(direction IN ('forward','backward')),
    coefficient REAL,               -- NULL = raw; non-NULL = classified (Jaccard)
    PRIMARY KEY (source_doi, target_doi, direction)
);

CREATE INDEX idx_cit_src ON citations(source_doi, direction);
CREATE INDEX idx_cit_tgt ON citations(target_doi, direction);
```

**Constraints**:
- `source_doi`: identifies the citing paper (lives in `index.db.papers.doi`).
  Cross-file foreign keys aren't enforceable in SQLite, so DOIs act as the
  logical join key.
- `direction`: enum stored on disk — `'forward'` means the row belongs to the
  source's Citation list (the target cites the source); `'backward'` means it
  belongs to the source's Reference list (the source cites the target).
  **The Python API does not expose these strings**: `db_sqlite.py` translates
  them to `'citation'` / `'reference'` at the boundary, and every other module
  and HTTP endpoint speaks `citation` / `reference`. The legacy column values
  are retained only to avoid migrating 13.7M rows across 156 year DBs.
- `coefficient`: NULL for raw edges, float 0.0-1.0 for Jaccard edges.

**Why split by year?**
- `index.db` stays small (~150 MB) — autocomplete and listing are SQL-fast.
- Each `{year}.db` is independently readable; similarity_search and
  find_citing_dois fan out across them with a process / thread pool.
- Current scale: **144,015 papers** in `index.db`, **13,717,945 citations**
  across **156 year DBs** (1949–2026 + `unknown.db`).

---

## 🔧 Core Functions

### Initialization

#### `init_db()`

**Purpose**: Create database schema if not exists

**Behavior**:
- Safe to call multiple times (uses `CREATE TABLE IF NOT EXISTS`)
- Enables WAL mode (Write-Ahead Logging) for concurrent access
- Enables foreign key constraints

**Example**:
```python
init_db()  # Sets up schema on first run
```

---

### Query Operations

#### `get_paper(doi: str) -> Optional[Dict]`

**Purpose**: Fetch a single paper with all citations

**Parameters**:
- `doi` (str): Paper DOI, e.g., "10.1038/nphys2439"

**Returns**: 
- Paper dict (see Data Structure below) if found
- `None` if DOI not in database

**Performance**: ~5-10ms (single row + citations lookup)

**Example**:
```python
paper = get_paper("10.1038/nphys2439")
if paper:
    print(f"Title: {paper['metadata']['title']}")
    print(f"Citation list — papers citing this: {paper['citation']}")
    print(f"Reference list — papers this cites: {paper['reference']}")
```

---

#### `load_db() -> Dict[str, Dict]`

**Purpose**: Load entire database into memory (one-time operation)

**Returns**: `{doi: paper_data}` dictionary with ~144K entries (current scale).

**Performance**:
- Full load reads `index.db` once and then every year DB in turn.
  Expect **minutes**, not seconds, at the current scale.
- This call is rarely the right tool. Almost every caller has a fast helper
  available (see the year-scoped / metadata-only / pagination helpers below).

**Memory Usage**: Several GB for the full 144K-paper / 13.7M-citation snapshot.

**Example**:
```python
db = load_db()

# Iterate over all papers
for doi, paper_data in db.items():
    print(f"{paper_data['metadata']['title']} ({paper_data['metadata']['year']})")
```

---

### Write Operations

#### `upsert_paper(paper_data: Dict)`

**Purpose**: Insert or update a single paper with all citations

**Parameters**:
- `paper_data` (Dict): Paper structure (see Data Structure below)

**Behavior**:
1. Insert/update paper metadata (title, year, journal, authors)
2. Clear all existing citation rows for this paper
3. Re-insert every entry from `citation` / `reference` (and their `classified_*` siblings)
4. De-duplicate: if the same DOI appears in both `citation` and `classified_citation` (or `reference`/`classified_reference`), keep the classified version (the one with the coefficient)

**Performance**: 10-50ms per paper

**Example**:
```python
paper = {
    "doi": "10.1038/nphys2439",
    "metadata": {
        "title": "Coherent synchrotron emission...",
        "year": 2012,
        "journal": "Nature Physics",
        "authors": ["Smith J", "Jones M"]
    },
    "citation":  ["10.1234/abc", "10.5678/def"],  # Papers citing this
    "reference": ["10.9999/xyz"],                  # Papers this cites
    "classified_citation": [
        {"doi": "10.1234/abc", "coefficient": 0.35}
    ],
    "classified_reference": [],
    "last_updated": "2026-04-21"
}
upsert_paper(paper)
```

---

#### `save_db(db: Dict)`

**Purpose**: Batch upsert all papers (drop-in for old JSON-based save_db)

**Parameters**:
- `db` (Dict): `{doi: paper_data}` dictionary

**Behavior**: Calls `upsert_paper()` for each paper

**Performance**: Scales linearly — each `upsert_paper` is 10–50ms, so a full
144K-paper save runs into the hour range. Prefer incremental `upsert_paper()`.

---

### Year-scoped & metadata-only helpers (added with the split layout)

| Helper | When to use |
|---|---|
| `load_db_year_range(min, max, include_unknown=False)` | bulk load `{doi: paper_dict}` restricted to a year range |
| `load_db_year(y)` | one year (or `None`/`"unknown"` for the unknown bucket) |
| `list_papers_paginated(year_min, year_max, search, sort_by, page, per_page) -> (rows, total)` | SQL-paginated metadata listing for UI |
| `get_metadata(doi) -> dict \| None` | one paper, metadata only (no citation join) |
| `get_metadata_batch(dois) -> {doi: meta_dict}` | bulk metadata fetch |
| `search_metadata(query, limit=20)` | SQL `LIKE` on doi + title |
| `get_citation_counts(dois) -> {doi: {citation, reference}}` | batched counts only |
| `find_citing_dois(target, direction='reference')` | reverse lookup: who cites target (default scans for target in others' Reference lists); parallel scan with thread pool. Pass `direction='citation'` for the inverse query. |
| `list_available_years() -> list[str]` | year-DB files on disk |
| `migrate_from_legacy(legacy_path=None)` | one-shot import from the legacy single-file DB |

Performance at 144K-paper / 13.7M-citation scale:

| Helper | Latency |
|---|---|
| `get_paper(doi)` | ~1.5 ms |
| `get_metadata(doi)` | ~0.3 ms |
| `list_papers_paginated(...)` per 50-row page | ~20 ms |
| `search_metadata("attosecond")` | ~100 ms |
| `get_citation_counts(200 dois)` | ~4 ms |
| `find_citing_dois(target)` | ~80 ms (parallel across 156 year DBs) |
| `load_db_year_range(2024, 2026)` | ~2 s (17K papers + their citations) |

---

### Utility Functions

#### `is_expired(last_updated_str: str, update_days: int = 1000) -> bool`

**Purpose**: Check if a paper's data is stale

**Parameters**:
- `last_updated_str` (str): ISO date string, e.g., "2026-04-21"
- `update_days` (int): How many days considered "fresh" (default 1000 days ≈ 2.7 years)

**Returns**: 
- `True` if paper is older than update_days
- `True` if last_updated is NULL
- `False` otherwise

**Example**:
```python
if is_expired(paper['last_updated'], update_days=30):
    print("Paper data is >30 days old, refresh needed")
```

---

#### `_connect() -> sqlite3.Connection`

**Purpose**: Create database connection with optimizations

**Configuration**:
- WAL mode: Write-Ahead Logging (concurrent reads + writes)
- Foreign keys: Enabled (referential integrity)
- Row factory: sqlite3.Row (dict-like access)

**Returns**: Open connection (auto-committed via `with` context manager)

---

## 📊 Data Structure

Every paper returned by `get_paper()` or in `load_db()` has this structure:

```python
{
    "doi": "10.1038/nphys2439",
    
    "metadata": {
        "title": "Coherent synchrotron emission from electron...",
        "year": 2012,
        "journal": "Nature Physics",
        "authors": ["Smith J", "Jones M", "Lee S"]
    },
    
    # Raw lists (no Jaccard coefficient)
    "citation": [          # papers that cite this paper (被引)
        "10.1103/PhysRevE.101.033202",
        "10.1088/1367-2630/15/1/015025",
        # ... more DOIs
    ],

    "reference": [         # papers this paper cites (参考文献)
        "10.1234/downstream.paper",
        # ... more DOIs
    ],

    # Classified (with Jaccard similarity coefficient)
    "classified_citation": [
        {"doi": "10.1103/PhysRevE.101.033202", "coefficient": 0.25},
        {"doi": "10.1088/1367-2630/15/1/015025", "coefficient": 0.18},
    ],

    "classified_reference": [
        {"doi": "10.1234/downstream.paper", "coefficient": 0.42},
    ],
    
    "last_updated": "2026-04-21"
}
```

**Key Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `doi` | str | Unique paper identifier |
| `metadata.title` | str | Paper title |
| `metadata.year` | int | Publication year |
| `metadata.journal` | str | Journal name |
| `metadata.authors` | list | Author names |
| `citation` | list | DOIs of papers **citing this** — Citation list / 被引 (raw) |
| `reference` | list | DOIs of papers **this cites** — Reference list / 参考文献 (raw) |
| `classified_citation` | list of dicts | Subset of `citation` carrying a Jaccard coefficient (scored citers) |
| `classified_reference` | list of dicts | Subset of `reference` carrying a Jaccard coefficient (scored refs) |
| `last_updated` | str | When data was fetched (ISO format) |

---

### Understanding "classified" vs Raw

**Raw** (`citation`, `reference`):
- Simple list of DOIs
- No coefficient (NULL in database)
- All discovered citers / references

**Classified** (`classified_citation`, `classified_reference`):
- Subset with Jaccard similarity coefficient
- A small fraction of all citations get coefficients (the miner only scores edges that
  cross the `THRESHOLD`); the rest are stored with NULL coefficient
- Indicate "similar" papers based on citation overlap

**Why Both?**:
- Raw list: Complete reference set
- Classified list: Pre-filtered for relevance (high Jaccard = similar research)

**Example**:
```python
paper = get_paper("10.1038/nphys2439")

# All papers citing this one
print(len(paper['citation']))  # 45 papers

# Only the most similar citers (with coefficient)
print(len(paper['classified_citation']))  # 8 papers

for cite in paper['classified_citation']:
    print(f"  {cite['doi']}: Jaccard = {cite['coefficient']:.2f}")
```

---

## 🔄 ACID & Concurrency

### Database Safeguards

**WAL Mode** (Write-Ahead Logging):
- Enables concurrent reads while write is happening
- Safer than default mode
- Small performance overhead

**Foreign Keys**:
- Enabled to maintain referential integrity
- Deleting a paper automatically removes its citations

**Transactions**:
- Each operation is atomic
- Partial writes never occur

---

## 📈 Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| `get_paper(doi)` | ~1.5 ms | index lookup + one year-DB read |
| `get_metadata(doi)` | ~0.3 ms | index.db only |
| `list_papers_paginated()` | ~20 ms / page | SQL LIMIT/OFFSET on index.db |
| `search_metadata()` | ~100 ms | SQL LIKE across 144K rows |
| `get_citation_counts(200)` | ~4 ms | batched COUNT() per year DB |
| `find_citing_dois()` | ~80 ms | thread pool across 156 year DBs |
| `upsert_paper()` | 10–50 ms | index + one year DB; routes by `year` |
| `load_db_year_range(2024, 2026)` | ~2 s | 17K papers with citations |
| `load_db()` (full library) | **minutes** | reads all 156 year DBs — avoid |

---

## 🔒 Data Integrity

### Deduplication Logic (in upsert_paper)

When a paper has the same DOI in both `citation` and `classified_citation`
(or the analogous `reference` / `classified_reference` pair):

```
Input:
  citation: ["10.xxxx", "10.yyyy"]
  classified_citation: [{"doi": "10.xxxx", "coefficient": 0.35}]

Output:
  citations rows in {year}.db:
    (source_doi, "10.xxxx", "forward", 0.35)
    (source_doi, "10.yyyy", "forward", NULL)
```

**Priority**: Classified entries (with coefficient) override raw entries

---

## 🐛 Common Patterns

### Pattern 1: Find all papers citing a given paper

```python
db = load_db()
ref_doi = "10.1038/nphys2439"

citing_papers = []
for doi, paper in db.items():
    # `reference` is what each paper cites — so ref_doi being in this paper's
    # `reference` list means this paper cites ref_doi.
    if ref_doi in paper['reference']:
        citing_papers.append(doi)

print(f"Found {len(citing_papers)} papers citing {ref_doi}")
```

### Pattern 2: Find papers with most citations (most cited by others)

```python
db = load_db()

# `citation` is the Citation list (papers citing this one).  Its length is
# how many times the paper has been cited.
papers_by_citations = sorted(
    db.items(),
    key=lambda x: len(x[1]['citation']),
    reverse=True
)

for doi, paper in papers_by_citations[:10]:
    print(f"{paper['metadata']['title']}: {len(paper['citation'])} citations")
```

### Pattern 3: Export database to JSON

```python
from db_sqlite import load_db
import json

db = load_db()
with open("backup.json", "w") as f:
    json.dump(db, f, indent=2, ensure_ascii=False)
```

---

## 🔧 Advanced Configuration

### Connection Parameters

```python
# In _connect()
conn.execute("PRAGMA journal_mode=WAL")           # Write-Ahead Logging
conn.execute("PRAGMA foreign_keys=ON")            # Referential integrity
conn.row_factory = sqlite3.Row                    # Dict-like row access
```

### Cache Duration (in data_browser.py)

```python
_CACHE_DURATION = 300  # 5 minutes
# Reload database every 5 minutes to get fresh data
```

---

## 📚 Related Modules

- **fitch_citations.py**: Populates database with papers and citations
- **download_paper.py**: Fetches paper metadata for database
- **data_browser.py**: Queries database for web API
- **graph_utils.py**: Graph algorithms on database
- **data_export.py**: Export database to other formats

---

## 🚀 Best Practices

1. **Always call `init_db()`** at startup to ensure schema exists
2. **Use `load_db()` once** per server (cache it for 5 minutes minimum)
3. **Batch upserts** when possible (faster than individual inserts)
4. **Check `is_expired()`** before API calls to external services
5. **Backup database** regularly (copy `.db` file to safe location)

---

**Last Updated**: 2026-04-21  
**Version**: 2.0  
**Status**: ✅ Production-ready  
**Test Coverage**: All functions tested ✓
