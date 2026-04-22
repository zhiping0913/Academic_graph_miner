# 💾 Database Module Reference (db_sqlite.py)

**File**: `db_sqlite.py` (202 lines)  
**Purpose**: SQLite persistence layer for papers and citation relationships  
**Status**: Production-ready

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
    print(f"Citations: {len(paper['backward'])}")

# Add or update a paper
new_paper = {
    "doi": "10.xxxx",
    "metadata": {
        "title": "New Paper",
        "year": 2025,
        "journal": "Nature",
        "authors": ["Author1", "Author2"]
    },
    "forward": ["10.aaaa", "10.bbbb"],
    "backward": ["10.cccc"],
    "classified_forward": [{"doi": "10.aaaa", "coefficient": 0.35}],
    "classified_backward": [],
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

#### `citations` Table
Stores directed citation relationships

```sql
CREATE TABLE citations (
    source_id   INTEGER NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    target_doi  TEXT    NOT NULL,
    direction   TEXT    NOT NULL CHECK(direction IN ('forward','backward')),
    coefficient REAL,               -- NULL = raw; non-NULL = classified (Jaccard)
    PRIMARY KEY (source_id, target_doi, direction)
);

CREATE INDEX idx_cit_source ON citations(source_id, direction);
```

**Constraints**:
- `source_id`: Foreign key to `papers(id)` with CASCADE delete
- `direction`: Either 'forward' (cites) or 'backward' (cited by)
- `coefficient`: NULL for raw edges, float 0.0-1.0 for Jaccard similarity edges
- **Composite Primary Key**: One row per (source, target_doi, direction) combination

**Why Two Tables?**:
- `papers` normalized to 17,348 rows (no duplication)
- `citations` flattened to 1,746,807 rows (all relationships, forward and backward)
- Efficient querying of connections

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
    print(f"Forward cites: {paper['forward']}")
    print(f"Backward cited by: {paper['backward']}")
```

---

#### `load_db() -> Dict[str, Dict]`

**Purpose**: Load entire database into memory (one-time operation)

**Returns**: `{doi: paper_data}` dictionary with 17,348 entries

**Performance**: 
- First load: 2-5 seconds (reads all papers + citations)
- Subsequent loads: Same (full reload each time)

**Use Case**: 
- Needed for graph analysis (NetworkX construction)
- Web servers cache this for 5 minutes

**Memory Usage**: ~200-300 MB for 17K papers + 1.7M citations

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
3. Re-insert all forward and backward citations
4. De-duplicate: if same citation appears in both `forward` and `classified_forward`, keep classified version (with coefficient)

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
    "forward": ["10.1234/abc", "10.5678/def"],  # Papers this cites
    "backward": ["10.9999/xyz"],                # Papers citing this
    "classified_forward": [
        {"doi": "10.1234/abc", "coefficient": 0.35}
    ],
    "classified_backward": [],
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

**Performance**: 10-20 seconds for 17K papers

**Use Case**: Loading from JSON, bulk database updates

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
    
    # Raw citation lists (no Jaccard coefficient)
    "forward": [
        "10.1103/PhysRevE.101.033202",
        "10.1088/1367-2630/15/1/015025",
        # ... more DOIs
    ],
    
    "backward": [
        "10.1234/downstream.paper",
        # ... more DOIs
    ],
    
    # Classified (with Jaccard similarity coefficient)
    "classified_forward": [
        {"doi": "10.1103/PhysRevE.101.033202", "coefficient": 0.25},
        {"doi": "10.1088/1367-2630/15/1/015025", "coefficient": 0.18},
    ],
    
    "classified_backward": [
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
| `forward` | list | DOIs of papers this cites (raw list) |
| `backward` | list | DOIs of papers citing this (raw list) |
| `classified_forward` | list of dicts | Forward cites with Jaccard coefficient |
| `classified_backward` | list of dicts | Backward cites with Jaccard coefficient |
| `last_updated` | str | When data was fetched (ISO format) |

---

### Understanding "classified" vs Raw

**Raw** (`forward`, `backward`):
- Simple list of DOIs
- No coefficient (NULL in database)
- All discovered references

**Classified** (`classified_forward`, `classified_backward`):
- Subset with Jaccard similarity coefficient
- Only ~3% of all citations (54,691 out of 1,746,807)
- Indicate "similar" papers based on citation overlap

**Why Both?**:
- Raw list: Complete reference set
- Classified list: Pre-filtered for relevance (high Jaccard = similar research)

**Example**:
```python
paper = get_paper("10.1038/nphys2439")

# All papers this cites
print(len(paper['forward']))  # 45 papers

# Only the most similar ones (with coefficient)
print(len(paper['classified_forward']))  # 8 papers

for cite in paper['classified_forward']:
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
| `get_paper()` | 5-10ms | Single lookup + citation join |
| `load_db()` | 2-5s | Load 17K papers + 1.7M citations |
| `upsert_paper()` | 10-50ms | Insert/update + citations |
| `save_db(17K papers)` | 10-20s | Batch upsert |
| First connection | 50-100ms | Schema initialization |
| Subsequent connections | 10-20ms | Reuse connection |

---

## 🔒 Data Integrity

### Deduplication Logic (in upsert_paper)

When a paper has same citation in both `forward` and `classified_forward`:

```
Input:
  forward: ["10.xxxx", "10.yyyy"]
  classified_forward: [{"doi": "10.xxxx", "coefficient": 0.35}]

Output:
  Citations table gets: (source_id, "10.xxxx", "forward", 0.35)
                        (source_id, "10.yyyy", "forward", NULL)
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
    if ref_doi in paper['backward']:
        citing_papers.append(doi)

print(f"Found {len(citing_papers)} papers citing {ref_doi}")
```

### Pattern 2: Find papers with most citations

```python
db = load_db()

papers_by_citations = sorted(
    db.items(),
    key=lambda x: len(x[1]['backward']),
    reverse=True
)

for doi, paper in papers_by_citations[:10]:
    print(f"{paper['metadata']['title']}: {len(paper['backward'])} citations")
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
