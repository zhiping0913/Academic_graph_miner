# 📊 Data Browser Module Reference

**File**: `data_browser.py` (285 lines)  
**Purpose**: Flask REST API for browsing papers, filtering by similarity, and exporting data  
**Status**: Production-ready

---

## 🎯 Quick Start

### Launch Server

```bash
source /home/zhiping/research-env/bin/activate
python data_browser.py
# Server running on http://localhost:5001
```

### Basic API Calls

```python
import requests

# Get first 10 papers
resp = requests.get("http://localhost:5001/api/papers?page=1&per_page=10")
papers = resp.json()['data']['papers']

# Search by keyword
resp = requests.get("http://localhost:5001/api/papers?search=laser")

# Filter by year range
resp = requests.get("http://localhost:5001/api/papers?year_min=2010&year_max=2020")
```

---

## 🔌 API Endpoints

### GET `/api/papers` - List Papers with Filtering

**Purpose**: Query papers with pagination, search, filtering, and optional similarity ranking

**Query Parameters**:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page` | int | 1 | Page number (starts at 1) |
| `per_page` | int | 50 | Items per page (max 500) |
| `search` | str | "" | Search in title or DOI |
| `year_min` | int | - | Minimum publication year |
| `year_max` | int | - | Maximum publication year |
| `ref_doi` | str | - | Reference DOI (for similarity scoring) |
| `similarity_min` | float | 0 | Minimum Jaccard similarity (0-1) |
| `sort_by` | str | - | Sort order (see below) |

**Sort Options**:
- `similarity_desc`: Highest similarity first (requires `ref_doi`)
- `similarity_asc`: Lowest similarity first (requires `ref_doi`)
- `year_desc`: Newest first
- `year_asc`: Oldest first
- `title_asc`: Alphabetical by title

**Response Format**:
```json
{
  "success": true,
  "data": {
    "papers": [
      {
        "doi": "10.1038/nphys2439",
        "title": "Coherent synchrotron emission...",
        "year": 2012,
        "authors": ["Author1", "Author2"],
        "forward_count": 25,
        "backward_count": 18,
        "similarity": 0.35
      },
      ...
    ],
    "total": 1245,
    "page": 1,
    "per_page": 50,
    "pages": 25
  },
  "timestamp": "2026-04-21T12:34:56"
}
```

**Examples**:

```bash
# Get first 50 papers
curl "http://localhost:5001/api/papers?page=1&per_page=50"

# Search for "plasma" papers
curl "http://localhost:5001/api/papers?search=plasma&per_page=20"

# Filter: papers from 2015-2020
curl "http://localhost:5001/api/papers?year_min=2015&year_max=2020"

# Find similar papers (sorted by Jaccard similarity)
curl "http://localhost:5001/api/papers?ref_doi=10.1038/nphys2439&sort_by=similarity_desc&similarity_min=0.1"
```

---

### GET `/api/citing-papers` - Find Papers Citing a Given Paper

**Purpose**: Get all papers that cite a specific paper (backward citations)

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `doi` | str | **Required** - Paper DOI to query |

**Response Format**:
```json
{
  "success": true,
  "data": {
    "source_doi": "10.1038/nphys2439",
    "source_title": "Coherent synchrotron emission...",
    "citing_papers": [
      {
        "doi": "10.1234/example",
        "title": "Follow-up study...",
        "year": 2014,
        "authors": ["Author A", "Author B"]
      },
      ...
    ],
    "count": 18
  },
  "timestamp": "2026-04-21T12:34:56"
}
```

**Example**:
```bash
curl "http://localhost:5001/api/citing-papers?doi=10.1038/nphys2439"
```

---

### GET `/api/search-papers` - Auto-complete Search

**Purpose**: Quick search suggestions for user input

**Query Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `q` | str | Search query (partial match) |

**Response Format**:
```json
{
  "success": true,
  "data": {
    "suggestions": [
      {
        "doi": "10.1038/nphys2439",
        "title": "Coherent synchrotron emission...",
        "year": 2012
      },
      ...
    ]
  }
}
```

**Example**:
```bash
curl "http://localhost:5001/api/search-papers?q=synchrotron"
```

---

### POST `/api/fetch-paper` - Fetch Missing Paper

**Purpose**: Download and add a paper to the database in real-time

**Request Body**:
```json
{
  "doi": "10.1234/new.paper"
}
```

**Response Format**:
```json
{
  "success": true,
  "data": {
    "doi": "10.1234/new.paper",
    "title": "New paper title...",
    "added": true
  },
  "timestamp": "2026-04-21T12:34:56"
}
```

**Example**:
```bash
curl -X POST http://localhost:5001/api/fetch-paper \
  -H "Content-Type: application/json" \
  -d '{"doi":"10.1234/new.paper"}'
```

---

### POST `/api/export` - Export Data

**Purpose**: Export papers in various formats

**Request Body**:
```json
{
  "dois": ["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"],
  "format": "json"
}
```

**Supported Formats**:
- `json`: Full JSON structure (with citations)
- `csv`: Comma-separated values (spreadsheet-friendly)
- `txt`: Plain text list (one DOI per line)

**Response**:
- Direct file download (attachment)

**Example**:
```bash
curl -X POST http://localhost:5001/api/export \
  -H "Content-Type: application/json" \
  -d '{"dois":["10.1038/nphys2439"],"format":"csv"}' \
  -o export.csv
```

---

## 🔧 Core Functions

### Internal Helper Functions

#### `get_cached_db() -> Dict`

**Purpose**: Load database with 5-minute caching to avoid repeated disk I/O

**Returns**: `{doi: paper_data}` dictionary

**Caching**: Reloads every 300 seconds

---

#### `_apply_filters(db, search, year_min, year_max, ref_doi, similarity_min)`

**Purpose**: Filter papers based on all criteria

**Returns**: Filtered list of (doi, paper_data) tuples

---

#### `_apply_sorting(papers, sort_by, ref_forward)`

**Purpose**: Sort papers by selected criterion

**Returns**: Sorted list of papers

---

## 📊 Database Integration

### Connection Pattern

```python
from db_sqlite import load_db, get_paper, upsert_paper
from data_browser import app

# Access cached database
db = get_cached_db()

# Query single paper
paper = db.get("10.1038/nphys2439")
```

### Paper Data Structure

Each paper in `db` has this structure:

```python
{
    "doi": "10.1038/nphys2439",
    "metadata": {
        "title": "Coherent synchrotron emission...",
        "year": 2012,
        "journal": "Nature Physics",
        "authors": ["Author1", "Author2"]
    },
    "forward": ["10.xxxx", "10.yyyy"],           # Papers this cites
    "backward": ["10.aaaa", "10.bbbb"],         # Papers citing this
    "classified_forward": [                      # With Jaccard coefficient
        {"doi": "10.xxxx", "coefficient": 0.25}
    ],
    "classified_backward": [],
    "last_updated": "2026-04-21"
}
```

---

## 🔍 Similarity Calculation

### Jaccard Coefficient

When `ref_doi` is provided, similarity is calculated as:

```
similarity = |references_A ∩ references_B| / |references_A ∪ references_B|
```

**Example**:
- Paper A citations: {ref1, ref2, ref3, ref4}
- Paper B citations: {ref2, ref3, ref5}
- Intersection: {ref2, ref3} (2 items)
- Union: {ref1, ref2, ref3, ref4, ref5} (5 items)
- Similarity: 2/5 = 0.4

---

## 💻 Usage Patterns

### Pattern 1: Browse Papers by Year

```python
import requests

# Get papers from 2015
resp = requests.get(
    "http://localhost:5001/api/papers",
    params={
        "year_min": 2015,
        "year_max": 2015,
        "per_page": 100
    }
)
papers = resp.json()['data']['papers']
print(f"Found {len(papers)} papers from 2015")
```

### Pattern 2: Find Similar Papers

```python
# Get all papers similar to a reference
resp = requests.get(
    "http://localhost:5001/api/papers",
    params={
        "ref_doi": "10.1038/nphys2439",
        "similarity_min": 0.15,
        "sort_by": "similarity_desc"
    }
)
papers = resp.json()['data']['papers']
for paper in papers:
    print(f"{paper['title']} (similarity: {paper['similarity']:.2f})")
```

### Pattern 3: Export Filtered Results

```python
import requests

# Search and export
resp = requests.get(
    "http://localhost:5001/api/papers",
    params={"search": "laser", "per_page": 1000}
)
papers_data = resp.json()['data']['papers']

# Get all DOIs
dois = [p['doi'] for p in papers_data]

# Export as CSV
export_resp = requests.post(
    "http://localhost:5001/api/export",
    json={"dois": dois, "format": "csv"}
)

with open("laser_papers.csv", "wb") as f:
    f.write(export_resp.content)
```

---

## ⚙️ Configuration

### Environment Variables

```bash
# Database path (set in backend.py)
export DB_PATH="/home/zhiping/Projects/Academic_graph_miner/academic_knowledge_graph.db"

# Output directory
export OUTPUT_PATH="/home/zhiping/Projects/Academic_graph_miner/output"
```

### Server Configuration

```python
# Port
PORT = 5001

# Cache duration (seconds)
_CACHE_DURATION = 300  # 5 minutes

# Max results per page
MAX_PER_PAGE = 500

# Default results per page
DEFAULT_PER_PAGE = 50
```

---

## 🚀 Advanced Features

### Filtering Algorithm

```
Papers → [Search Filter]
      → [Year Range Filter]
      → [Similarity Filter (if ref_doi provided)]
      → [Sort]
      → [Paginate]
```

### Performance Optimization

- **5-minute database caching**: Avoid reloading entire DB per request
- **In-memory filtering**: All filtering done in Python (not SQL)
- **Lazy similarity calculation**: Only computed for papers matching other criteria

---

## 🐛 Common Issues & Solutions

### Issue: Slow response on first request
- **Cause**: Database loading on first query (5-minute cache then)
- **Solution**: Normal behavior, subsequent queries are fast

### Issue: Empty results for similarity search
- **Cause**: `ref_doi` paper not in database
- **Solution**: Add paper using `/api/fetch-paper` first

### Issue: Export file is empty
- **Cause**: No papers matched the filter criteria
- **Solution**: Check filter parameters, try with fewer filters

---

## 📈 Performance Metrics

| Operation | Time |
|-----------|------|
| First page load | 2-5s (DB load) |
| Subsequent queries | 50-200ms |
| Search in 17K papers | 100-300ms |
| Similarity calculation | 20-50ms per paper |
| Export 1000 papers | 500-1000ms |

---

## 🔗 Related Modules

- **db_sqlite.py**: Database operations
- **graph_utils.py**: Similarity calculations
- **download_paper.py**: Paper acquisition
- **data_export.py**: Export formats
- **graph_server.py**: Knowledge graph visualization

---

**Last Updated**: 2026-04-21  
**Version**: 2.0  
**Status**: ✅ Production-ready
