# 🔍 Citation Mining Module Reference (fitch_citations.py)

**File**: `fitch_citations.py` (265 lines)  
**Purpose**: Recursive citation network miner using Breadth-First Search + Jaccard filtering  
**Status**: Production-ready

---

## 🎯 Quick Start

### Basic Usage

```python
from fitch_citations import run_miner, fetch_combined_data

# Build citation network from seed papers
seed_dois = ["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"]
run_miner(seeds=seed_dois)  # Runs for 1-5 hours depending on depth

# Fetch single paper data
paper_data = fetch_combined_data("10.1038/nphys2439")
print(f"Title: {paper_data['title']}")
print(f"Citations: {len(paper_data['citations'])}")
print(f"References: {len(paper_data['references'])}")
```

---

## 🏗️ Mining Algorithm

### BFS + Jaccard Strategy

```
Input: Seed DOIs (initial papers)
  ↓
Initialize queue ← seed_dois
depth ← 0

While queue not empty AND depth < MAX_DEPTH:
  For each paper P in queue:
    1. Fetch metadata + citations/references from APIs
    2. Compute Jaccard similarity between P and papers in queue
    3. For similar papers (Jaccard ≥ THRESHOLD):
       - Add to next_queue (for deeper exploration)
       - Save to database
    4. Update last_updated timestamp
  
  queue ← next_queue
  depth += 1

Output: Saved to SQLite database
```

**Key Parameters**:

```python
THRESHOLD = 0.1              # Jaccard similarity threshold
                             # Only papers with >10% citation overlap pursued

MAX_DEPTH = 3                # Maximum search depth
                             # Prevents combinatorial explosion

UPDATE_DAYS = 1000           # Cache validity (days)
                             # Don't refetch if <1000 days old

REQUEST_DELAY = 1.2          # Delay between API calls (seconds)
                             # Rate limit compliance
```

---

## 🔧 Core Functions

### Main Entry Point

#### `run_miner(seeds: List[str]) -> None`

**Purpose**: Main mining loop - build citation network from seed papers

**Parameters**:
- `seeds` (List[str]): List of seed DOI strings, e.g., `["10.1038/nphys2439", ...]`

**Behavior**:
1. Initialize BFS queue with seed DOIs
2. For each paper at depth < MAX_DEPTH:
   - Fetch combined metadata from S2 and Crossref APIs
   - Compute Jaccard similarity to papers in current queue
   - Filter by THRESHOLD (only follow similar papers)
   - Save paper and citations to SQLite
3. Track depth to prevent runaway expansion

**Performance**: 
- Typical execution: 1-5 hours
- Network size: 100-1000 papers depending on field density
- API calls: 500-5000 requests

**Termination Conditions**:
- No more papers to explore (BFS exhausted)
- Maximum depth reached
- Manual interruption (Ctrl+C)

**Example**:
```python
# Mine laser physics papers
seed_dois = [
    "10.1038/nphys2439",
    "10.1103/PhysRevE.101.033202"
]
run_miner(seeds=seed_dois)

# After completion, check database
from db_sqlite import load_db
db = load_db()
print(f"Mined {len(db)} papers")
```

---

### Data Fetching

#### `fetch_combined_data(doi: str) -> Optional[Dict]`

**Purpose**: Fetch complete paper metadata from three API sources and merge results

**Implementation** (Triple-source fusion):
1. **Semantic Scholar API**: Title, authors, year, citations (forward), references (backward)
2. **Crossref API**: Journal info, DOI validation, references (backward)
3. **OpenCitations API**: Comprehensive citation coverage (forward & backward)

**Data Merge Strategy**:
- **Metadata Priority**: S2 > Crossref (title, authors, year, journal)
- **Forward (被引信息 - who cites this paper)**:
  - Combines: S2 citations + OpenCitations citations
- **Backward (参考文献 - what this paper cites)**:
  - Combines: S2 references + Crossref references + OpenCitations references
- **Deduplication**: Automatic via set operations across sources

**Parameters**:
- `doi` (str): Paper DOI, e.g., "10.1038/nphys2439"

**Returns**: Dictionary or None
```python
{
    "doi": "10.1038/nphys2439",
    "metadata": {
        "title": "Coherent synchrotron emission...",
        "authors": ["Author1", "Author2"],
        "year": 2012,
        "journal": "Nature Physics"
    },
    "forward": ["10.xxx/yyy", "10.aaa/bbb"],   # Who cites this paper (Citations)
    "backward": ["10.ccc/ddd"],                 # What this paper cites (References)
    "last_updated": "2026-04-21"
}
```

**API Sources**:
1. **Semantic Scholar** (`api.semanticscholar.org`)
   - Provides citations & references
   - Field: citations.externalIds.DOI, references.externalIds.DOI

2. **Crossref** (`api.crossref.org`)
   - Provides backward references only
   - Field: reference[].DOI

3. **OpenCitations** (`opencitations.net`)
   - Provides forward & backward
   - Endpoints: /citations/ (citing), /references/ (cited)

**Performance**: 3-6 seconds per paper (3 API calls with 1.2s delays)

**Error Handling**:
- Returns None if both APIs fail
- Logs retry attempts
- Respects rate limits (1.2s delay)

**Example**:
```python
paper_data = fetch_combined_data("10.1038/nphys2439")
if paper_data:
    print(f"Fetched: {paper_data['title']}")
    print(f"Found {len(paper_data['citations'])} citations")
else:
    print("Failed to fetch paper")
```

---

## 📊 Jaccard Similarity Calculation

### Formula

```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|

Where:
  A = citations of paper A
  B = citations of paper B
  ∩ = intersection (common citations)
  ∪ = union (all unique citations)
```

### Example

```
Paper A cites:   {ref1, ref2, ref3, ref4}        (4 citations)
Paper B cites:   {ref2, ref3, ref5}              (3 citations)

Intersection:    {ref2, ref3}                    (2 shared)
Union:           {ref1, ref2, ref3, ref4, ref5}  (5 total)

Jaccard = 2/5 = 0.4
```

**Decision at THRESHOLD = 0.1**:
- 0.4 ≥ 0.1 → **Include paper B** (similar)
- 0.05 < 0.1 → **Skip paper B** (not similar enough)

---

## 🎯 Mining Strategy Details

### Depth-Limited Search

```
Depth 0: Input seeds (e.g., 2 papers)
  ↓
Depth 1: Papers similar to seeds (e.g., 20 papers)
  ├─ Only explore Jaccard ≥ THRESHOLD
  ├─ Prevents following dissimilar papers
  ↓
Depth 2: Papers similar to depth 1 (e.g., 100 papers)
  ├─ Further filtering by similarity
  ↓
Depth 3: Papers similar to depth 2 (e.g., 300 papers)
  ├─ Final depth level
  ↓
STOP: MAX_DEPTH reached
```

**Why Threshold?**
- Raw BFS would explore ALL papers (infinite)
- Threshold keeps network focused on relevant domain
- Prevents "topic drift" through weak connections

---

## 🔌 External APIs

### Semantic Scholar API

**Endpoint**: `https://api.semanticscholar.org/graph/v1/paper/{doi}`

**Rate Limit**: 100 req/sec (rarely hit with 1.2s delay)

**Returns**:
- Paper metadata
- Citation list (forward/backward)
- Author information

---

### Crossref API

**Endpoint**: `https://api.crossref.org/works/{doi}`

**Rate Limit**: 50 req/sec (respectful)

**Returns**:
- DOI validation
- Journal info
- Publication date
- Publisher information

---

## 📈 Performance Metrics

| Operation | Time | Notes |
|-----------|------|-------|
| `fetch_combined_data()` | 1-2s | API call + parsing |
| Jaccard calculation | <1ms | ~6K citations |
| Single BFS level | 10-60s | Depends on papers per level |
| Full mining (3 levels) | 1-5 hours | ~500-1000 papers |
| Database insert | 50ms | Per paper + citations |

---

## ⚙️ Configuration Parameters

```python
THRESHOLD = 0.1           # Minimum Jaccard similarity to follow
MAX_DEPTH = 3             # Maximum search depth
UPDATE_DAYS = 1000        # Cache validity (days)
REQUEST_DELAY = 1.2       # Delay between API calls (seconds)
```

### Tuning Guide

**To expand network**: Lower `THRESHOLD` (e.g., 0.05)
- Explores more tangentially related papers
- Risk: Lower quality connections, slower mining

**To focus network**: Raise `THRESHOLD` (e.g., 0.25)
- Follows only tightly related papers
- Risk: May miss important work

**To speed up**: Lower `MAX_DEPTH` (e.g., 2)
- Shallower exploration
- Risk: Incomplete network

**To get more papers**: Raise `MAX_DEPTH` (e.g., 4)
- Deeper exploration
- Warning: Very slow (exponential growth)

---

## 🔄 Recovery & Resumption

### Incremental Restart

```python
# Mining interrupted after 2 hours
# DATABASE ALREADY HAS: Depth 0, 1, 2 papers

# Just run again
run_miner(seeds=["10.1038/nphys2439"])

# System automatically:
# 1. Detects papers already in DB
# 2. Uses is_expired() to check freshness
# 3. Skips fetching (unless UPDATE_DAYS passed)
# 4. Resumes from last depth
```

**Safe to interrupt**: Yes, partial results are saved

---

## 🐛 Common Issues & Solutions

### Issue: Mining very slow
- **Cause**: Too many papers to explore (network dense)
- **Solution**: Raise `THRESHOLD` (e.g., 0.15 instead of 0.1)

### Issue: "API rate limited" errors
- **Cause**: Network/API issue or too many requests
- **Solution**: Increase `REQUEST_DELAY` (e.g., 2.0 instead of 1.2)

### Issue: No new papers added
- **Cause**: All papers already in DB (is_expired() returns False)
- **Solution**: Delete papers or set `UPDATE_DAYS=0` to force refresh

### Issue: Memory growing over time
- **Cause**: Keeping large data structures in memory during mining
- **Solution**: System periodically flushes to DB, should be OK

---

## 📚 Related Modules

- **db_sqlite.py**: Save mined papers and citations
- **graph_utils.py**: Similarity calculations used by mining
- **download_paper.py**: Download PDFs of mined papers
- **data_browser.py**: Query mined network
- **fitch_citations.py**: This module

---

## 🚀 Advanced Usage

### Custom Seed Selection

```python
from db_sqlite import load_db

db = load_db()

# Find papers with most citations
most_cited = sorted(
    db.items(),
    key=lambda x: len(x[1]['backward']),
    reverse=True
)[:5]

# Use as new seeds
seed_dois = [doi for doi, _ in most_cited]
run_miner(seeds=seed_dois)
```

### Monitor Mining Progress

```python
from db_sqlite import load_db
import time

def check_progress():
    while True:
        db = load_db()
        print(f"{len(db)} papers in database")
        time.sleep(30)  # Check every 30 seconds
```

---

**Last Updated**: 2026-04-21  
**Version**: 2.0  
**Status**: ✅ Production-ready  
**Algorithm**: BFS with Jaccard thresholding ✓
