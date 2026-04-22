# Quick Start for AI: Academic Graph Miner Functions

**Target**: AI systems and developers unfamiliar with this codebase  
**Language**: English  
**Focus**: Core functions, APIs, and programmatic usage (no UI/visualization)

---

## 🎯 System Overview

Academic Graph Miner provides three main functional modules:

```
Module                File                Purpose
──────────────────────────────────────────────────────────────
1. Citation Mining   fitch_citations.py  Extract paper citations via APIs
2. Paper Download    download_paper.py   Download PDFs from multiple sources
3. Data Operations   db_sqlite.py        Query and manage the database
4. Graph Analysis    graph_utils.py      Calculate similarity metrics
```

---

## 📦 Installation

```bash
# Activate the research environment
source /home/zhiping/research-env/bin/activate

# Install dependencies
pip install -r requirements.txt

# For browser automation (if using Playwright features)
playwright install chromium
```

---

## 1️⃣ Citation Mining (`fitch_citations.py`)

### Purpose
Recursively crawl paper citation networks using Semantic Scholar and Crossref APIs.

### Basic Usage

```python
from fitch_citations import run_miner

# Seed DOIs to start mining
seed_dois = [
    "10.1038/nphys2439",
    "10.1103/PhysRevE.101.033202"
]

# Run mining with default parameters
run_miner(
    seed_dois=seed_dois,
    depth=2,                    # Search depth (1-3)
    threshold=0.1,              # Jaccard similarity threshold (0.0-1.0)
    max_papers=1000,            # Maximum papers to collect
    verbose=True                # Print progress
)
```

### Function Signature

```python
def run_miner(
    seed_dois: List[str],
    depth: int = 2,
    threshold: float = 0.1,
    max_papers: int = 1000,
    verbose: bool = True
) -> None:
    """
    Build citation network around seed papers.
    
    Args:
        seed_dois: Starting DOIs (e.g., ["10.1038/nphys2439"])
        depth: How many levels deep to search (1=immediate citations, 2=2 hops, etc.)
        threshold: Jaccard coefficient threshold (0.1 = 10% citation overlap)
        max_papers: Stop searching when this many papers are found
        verbose: Print progress messages
    
    Returns:
        None (writes to academic_knowledge_graph.db)
    """
```

### Fetch Combined Data

```python
from fitch_citations import fetch_combined_data

# Get metadata about a specific paper
paper_data = fetch_combined_data("10.1038/nphys2439")
print(f"Title: {paper_data.get('title')}")
print(f"Year: {paper_data.get('year')}")
print(f"Forward citations: {len(paper_data.get('forward', []))}")
print(f"Backward citations: {len(paper_data.get('backward', []))}")
```

### Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Single API query | 1-2s | Respects rate limits (1.2s delay) |
| Full depth-2 search | 1-5 hours | Depends on seed papers and network |
| Jaccard calculation | 0.0079ms | Very fast, computed on-demand |

---

## 2️⃣ Paper Downloading (`download_paper.py`)

### Batch Download

```python
from download_paper import process_doi_list

# Download multiple papers
dois = [
    "10.1038/nphys2439",
    "10.1103/PhysRevE.101.033202",
    "10.1088/1367-2630/15/1/015025"
]

# Process and download
df_report = process_doi_list(
    dois=dois,
    output_base_dir="research/papers/"
)

# Check results
print(df_report[['DOI', 'Title', 'PDF_Path', 'File_Size_MB', 'Supplementary_Status']])
```

### Function Signature

```python
def process_doi_list(
    dois: List[str],
    output_base_dir: str = "papers/"
) -> pd.DataFrame:
    """
    Batch download papers from multiple sources.
    
    Args:
        dois: List of DOI strings
        output_base_dir: Where to save PDFs
    
    Returns:
        DataFrame with columns:
        - DOI, Title, Year
        - PDF_Status, PDF_Path, File_Size_MB
        - Supplementary_Status, Supplementary_Files
    
    Processing Steps:
        1. Check if PDF already exists (skip if found)
        2. Try 9 download sources in priority order
        3. Validate PDF (magic bytes, structure check)
        4. Search for supplementary materials
        5. Generate CSV report
    
    Example Output:
        DOI: 10.1038/nphys2439
        Title: Coherent synchrotron emission...
        Year: 2012
        PDF_Path: papers/2012/2012--coherent-synchrotron.pdf
        File_Size_MB: 2.34
        Supplementary_Status: Found 1 supplement
        Supplementary_Files: 2012--coherent-synchrotron--supplementary.pdf
    """
```

### Single Paper Download

```python
from download_paper import download_pdf

# Download one paper
status, pdf_path = download_pdf(
    doi="10.1038/nphys2439",
    output_dir="papers/",
    title="Coherent synchrotron emission",
    year=2012
)

print(f"Status: {status}")  # ✅ Downloaded from OpenAlex
print(f"Path: {pdf_path}")   # papers/2012/2012--coherent-synchrotron.pdf
```

### Function Signature

```python
def download_pdf(
    doi: str,
    output_dir: str,
    title: str,
    year: int
) -> Tuple[str, str]:
    """
    Download single PDF from best available source.
    
    Args:
        doi: Paper DOI
        output_dir: Save location
        title: Paper title (for filename)
        year: Publication year
    
    Returns:
        (status_message, pdf_path_or_empty)
        
    Download Priority (tries in order):
        1. Playwright DOI page       (handles JS, iframes)
        2. doi2pdf                   (fast direct)
        3. OpenAlex API              (open access)
        4. Crossref links            (publisher metadata)
        5. Unpywall API              (OA database)
        6. arXiv                     (preprints only)
        7. Scidownl                  (Sci-Hub wrapper)
        8. Sci-Hub direct            (unreliable)
        9. Playwright stealth        (fallback browser)
    
    Success Rate: ~70-80% depending on paper accessibility
    """
```

### Extract Text from PDF

```python
from download_paper import extract_text_from_pdf, extract_supplementary_from_pdf_text

# Extract all text from PDF
text = extract_text_from_pdf("papers/2012/paper.pdf", max_pages=5)

# Search for supplementary materials mentioned in PDF
if text:
    supp_info = extract_supplementary_from_pdf_text(text)
    if supp_info['has_supplementary']:
        print(f"Found: {supp_info['keywords_found']}")
```

### Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| Single PDF download | 5-30s | Depends on source and network |
| PDF validation | 50-100ms | Magic byte check |
| Text extraction | 1-2s | Per PDF, using pdfplumber |
| Batch 100 papers | 8-15 min | Includes validation & supplementary search |

---

## 3️⃣ Database Operations (`db_sqlite.py`)

### Load Database

```python
from db_sqlite import load_db

# Load all papers and citations into memory
db = load_db()

print(f"Total papers: {len(db)}")           # 17,348
print(f"Total citations: {sum(len(p.get('forward', [])) for p in db.values())}")
```

### Query Single Paper

```python
from db_sqlite import get_paper

# Get detailed paper info
paper = get_paper("10.1038/nphys2439", db)

if paper:
    print(f"Title: {paper['metadata']['title']}")
    print(f"Year: {paper['metadata']['year']}")
    print(f"Forward citations: {len(paper.get('forward', []))}")
    print(f"Backward citations: {len(paper.get('backward', []))}")
```

### Paper Data Structure

```python
paper = {
    "doi": "10.1038/nphys2439",
    "metadata": {
        "title": "Coherent synchrotron emission...",
        "year": 2012,
        "journal": "Nature Physics",
        "authors": ["Smith, J.", "Jones, K.", ...]
    },
    "forward": [
        "10.1103/PhysRevE.101.033202",  # This paper cites these
        "10.1088/1367-2630/15/1/015025",
        ...
    ],
    "backward": [
        "10.1016/j.etran.2026.100553",  # These papers cite this paper
        ...
    ],
    "classified_forward": [            # Forward with similarity scores
        {"doi": "10.1103/PhysRevE.101.033202", "coefficient": 0.35},
        ...
    ],
    "classified_backward": [],
    "last_updated": "2026-04-21"
}
```

### Insert/Update Paper

```python
from db_sqlite import upsert_paper

# Add or update paper metadata
new_paper = {
    "doi": "10.1234/example.5678",
    "metadata": {
        "title": "New Paper Title",
        "year": 2024,
        "journal": "Some Journal",
        "authors": ["Author A", "Author B"]
    },
    "forward": ["10.1038/nphys2439"],
    "backward": []
}

upsert_paper(new_paper, db)
```

### Performance Characteristics

| Operation | Time | Notes |
|-----------|------|-------|
| load_db() | 2-5s | Load 17K papers, 1.7M citations (~300MB) |
| get_paper() | 5-10ms | Single paper lookup |
| upsert_paper() | 10-50ms | Insert/update single paper |
| Database cache | 5min | Auto-cleared for memory efficiency |

---

## 4️⃣ Graph Analysis (`graph_utils.py`)

### Calculate Jaccard Similarity

```python
from graph_utils import calculate_jaccard

# Compare citation patterns of two papers
paper_a_citations = ["10.1103/PhysRevE.101.033202", "10.1088/1367-2630/15/1/015025"]
paper_b_citations = ["10.1103/PhysRevE.101.033202", "10.1016/j.etran.2026.100553"]

similarity = calculate_jaccard(paper_a_citations, paper_b_citations)
print(f"Jaccard similarity: {similarity:.3f}")  # 0.25 (1 common / 4 total unique)
```

### Function Signature

```python
def calculate_jaccard(list_a: List[str], list_b: List[str]) -> float:
    """
    Calculate Jaccard similarity coefficient between two lists.
    
    Formula: |intersection| / |union|
    
    Args:
        list_a: First list of items (e.g., DOI list)
        list_b: Second list of items
    
    Returns:
        Float between 0.0 (completely different) and 1.0 (identical)
    
    Interpretation:
        0.0 = No common elements
        0.1-0.2 = Loosely related
        0.2-0.5 = Moderately related
        0.5+ = Highly related
        1.0 = Identical lists
    
    Performance: 0.0079ms (very fast)
    """
```

### Extract Subgraph

```python
from graph_utils import extract_subgraph

# Build network around seed papers
db = load_db()
seed_dois = ["10.1038/nphys2439"]

subgraph = extract_subgraph(
    db=db,
    seeds=seed_dois,
    max_forward=50,   # Max papers forward-cited
    max_backward=50   # Max papers backward-cited
)

print(f"Nodes: {len(subgraph['nodes'])}")
print(f"Edges: {len(subgraph['edges'])}")
```

### Compute Similarity to Seeds

```python
from graph_utils import compute_jaccard_to_seeds

# Find papers similar to multiple seed papers
seeds = ["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"]
db = load_db()

# For each paper, calculate average similarity to all seeds
similarities = {}
for doi, paper in db.items():
    scores = [
        calculate_jaccard(paper.get('forward', []), db[seed].get('forward', []))
        for seed in seeds
        if seed in db
    ]
    similarities[doi] = sum(scores) / len(scores) if scores else 0.0

# Get top-10 similar papers
top_papers = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:10]
for doi, score in top_papers:
    print(f"{doi}: {score:.3f}")
```

---

## 📋 Common Workflows

### Workflow 1: Mine → Download → Analyze

```python
from fitch_citations import run_miner
from download_paper import process_doi_list
from db_sqlite import load_db
from graph_utils import calculate_jaccard

# Step 1: Mine citation network
run_miner(["10.1038/nphys2439"], depth=2, threshold=0.1)

# Step 2: Download papers
df = process_doi_list(["10.1038/nphys2439"], "papers/")
print(df)

# Step 3: Load and analyze
db = load_db()
print(f"Collected {len(db)} papers total")

# Step 4: Find similar papers
my_paper = db["10.1038/nphys2439"]
for other_doi, other_paper in db.items():
    if other_doi != "10.1038/nphys2439":
        jaccard = calculate_jaccard(
            my_paper.get('forward', []),
            other_paper.get('forward', [])
        )
        if jaccard > 0.2:
            print(f"{other_doi}: similarity {jaccard:.2f}")
```

### Workflow 2: Export Specific Papers

```python
from db_sqlite import load_db
import json

# Load database
db = load_db()

# Filter papers from specific year and field
papers_2020 = [
    doi for doi, paper in db.items()
    if paper.get('metadata', {}).get('year') == 2020
]

# Export DOI list
with open("papers_2020.txt", "w") as f:
    f.write("\n".join(papers_2020))

# Export as JSON with metadata
export_data = {
    doi: db[doi]['metadata']
    for doi in papers_2020
}

with open("papers_2020.json", "w") as f:
    json.dump(export_data, f, indent=2)

print(f"Exported {len(papers_2020)} papers from 2020")
```

### Workflow 3: Batch Operations

```python
from db_sqlite import load_db, get_paper
from download_paper import extract_text_from_pdf
import os

db = load_db()
papers_dir = "papers/"

# Process all downloaded papers
for root, dirs, files in os.walk(papers_dir):
    for pdf_file in files:
        if pdf_file.endswith('.pdf'):
            pdf_path = os.path.join(root, pdf_file)
            
            # Extract text
            text = extract_text_from_pdf(pdf_path)
            
            # Check for specific keywords
            if text and "high harmonic" in text.lower():
                print(f"Found HHG reference: {pdf_file}")
            
            # Save extracted text
            txt_path = pdf_path.replace('.pdf', '.txt')
            if not os.path.exists(txt_path):
                with open(txt_path, 'w') as f:
                    f.write(text or "")
```

---

## 🔧 Configuration & Environment Variables

### Optional Environment Variables

```bash
# Unpywall API (for open access lookup)
export UNPYWALL_EMAIL="your_email@gmail.com"

# Playwright browser
export PLAYWRIGHT_BROWSER="chromium"

# Request delays (in seconds)
export REQUEST_DELAY_MIN="2"
export REQUEST_DELAY_MAX="5"
```

### Database Configuration

```python
# Force reload database (ignores cache)
from db_sqlite import load_db
db = load_db(force_reload=True)

# Database location
# Default: academic_knowledge_graph.db
# Modify in backend.py if needed
```

---

## ⚠️ Important Notes

### 1. Rate Limiting
- Semantic Scholar API: ~1-2s per request
- Crossref API: ~0.5s per request
- Built-in delay: 1.2s between requests
- **Do not** bypass delays in production

### 2. PDF Validation
- System validates PDFs before saving
- Rejects HTML files (common captcha pages)
- Checks magic bytes and EOF markers
- **Safe from malformed downloads**

### 3. Data Persistence
- All data written to SQLite database
- Transactions are atomic
- Database locked during writes (WAL mode enabled)
- **Safe for concurrent reads**

### 4. Memory Usage
- load_db() uses ~300MB RAM
- Contains 17K papers × 100+ citations each
- **Cache auto-clears after 5 minutes**
- For large operations, process in batches

---

## 🐛 Error Handling

### Common Errors and Solutions

```python
# Error: "Database is locked"
# Cause: Multiple processes writing simultaneously
# Solution: Already handled (WAL mode enabled), just retry

# Error: "API rate limit exceeded"
# Cause: Too many requests too quickly
# Solution: Increase REQUEST_DELAY or use batch processing

# Error: "PDF validation failed"
# Cause: Downloaded file is HTML (captcha page)
# Solution: Automatic, tries next source

# Error: "No module named 'pdfplumber'"
# Cause: Dependency not installed
# Solution: pip install -r requirements.txt
```

### Graceful Degradation

```python
from download_paper import process_doi_list

# Some papers may fail - that's OK
df = process_doi_list(["10.1038/nphys2439", "invalid.doi"])

# Check which succeeded
successful = df[df['PDF_Status'].str.contains('✅', na=False)]
failed = df[~df['PDF_Status'].str.contains('✅', na=False)]

print(f"Success: {len(successful)}, Failed: {len(failed)}")

# Retry failed papers later
failed_dois = failed['DOI'].tolist()
```

---

## 📊 Performance Benchmarks

| Operation | Time | Scale |
|-----------|------|-------|
| Load database | 2-5s | 17K papers, 1.7M citations |
| Query single paper | 5-10ms | Instant lookup |
| Mine depth-2 network | 1-5h | ~500-2000 papers |
| Download 100 papers | 8-15 min | ~5-30s per PDF |
| Calculate Jaccard | 0.0079ms | Any list sizes |
| Extract subgraph | 50-500ms | Depends on size |

---

## 📚 API Reference Summary

### fitch_citations.py
```python
run_miner(seed_dois, depth=2, threshold=0.1, max_papers=1000, verbose=True)
fetch_combined_data(doi) → Dict
```

### download_paper.py
```python
process_doi_list(dois, output_base_dir) → DataFrame
download_pdf(doi, output_dir, title, year) → Tuple[str, str]
extract_text_from_pdf(pdf_path, max_pages=None) → Optional[str]
extract_supplementary_from_pdf_text(text) → Dict
is_valid_pdf(file_path) → bool
```

### db_sqlite.py
```python
load_db(force_reload=False) → Dict
get_paper(doi, db) → Optional[Dict]
upsert_paper(paper_data, db) → None
init_db() → None
```

### graph_utils.py
```python
calculate_jaccard(list_a, list_b) → float
extract_subgraph(db, seeds, max_forward, max_backward) → Dict
compute_jaccard_to_seeds(db, doi, seeds) → List[float]
```

---

## 🚀 Next Steps

1. **Clone repository** → `/home/zhiping/Projects/Academic_graph_miner/`
2. **Activate environment** → `source /home/zhiping/research-env/bin/activate`
3. **Install dependencies** → `pip install -r requirements.txt`
4. **Start coding** → `python -c "from download_paper import process_doi_list; help(process_doi_list)"`
5. **Check examples** → See "Common Workflows" section above

---

**Last Updated**: 2026-04-22  
**Version**: 1.0  
**Language**: English (AI/Developer Focus)
