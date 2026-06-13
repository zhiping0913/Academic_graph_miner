# 🏛️ Academic Graph Miner - Codebase Guide

**Project**: Academic Graph Miner
**Purpose**: Automated citation network mining, paper downloading, and knowledge graph visualization
**Tech Stack**: Python 3.10+, SQLite3 (split-by-year), Flask, NetworkX, Playwright, MarkItDown
**Status**: ✅ Production-ready (v5, as of 2026-06-08)

---

## Role & Responsibilities

You are the expert on this codebase. Your responsibilities:

1. **Before answering questions**: Consult the module documentation (`docs/MODULE_*.md` files)
2. **After code changes**: Update relevant module documentation
3. **Maintain consistency**: Follow conventions documented in this file
4. **Performance-aware**: Understand performance characteristics of each module
5. **Help with integration**: Guide users on how modules interact

---

## 📁 Project Structure

```
/home/zhiping/Projects/Academic_graph_miner/
├── Core Database Layer
│   ├── db_sqlite.py                (202 lines) → SQLite persistence
│   └── backend.py                  (10 lines)  → Config paths
│
├── Citation Mining Engine
│   ├── fitch_citations.py          (265 lines) → BFS citation crawler
│   └── graph_utils.py              (73 lines)  → Similarity algorithms
│
├── Paper Acquisition
│   ├── download_paper.py           (1534 lines)→ 9-source PDF downloader
│   └── data_export.py              (338 lines) → JSON/CSV/TXT export
│
├── Web Services (Flask)
│   ├── graph_server.py             (port 5000) → Interactive graph API
│   ├── data_browser.py             (port 5001) → Paper browsing API
│   └── download_server.py          (port 5003) → Async download API
│
├── Utilities
│   ├── visualize_graph.py          → Pyvis visualization
│   ├── main.py                     → CLI entry point
│   └── __init__.py
│
├── UI / Visualization
│   ├── interactive_graph.html      → Vis.js graph UI
│   ├── data_browser.html           → Paper browser UI
│   └── sub_network.html            → Static graph output
│
├── Documentation
│   ├── README.md                   → project entry point + index
│   ├── CLAUDE.md                   → this file (project conventions for Claude)
│   └── docs/
│       ├── Quick_Start_AI.md       → developer / agent walkthrough (English)
│       ├── Quick_Start_CN.md       → developer walkthrough (Chinese)
│       ├── ARCHITECTURE.md         → system architecture overview
│       ├── MODULE_DB_SQLITE.md     → database operations + split-by-year schema
│       ├── MODULE_DATA_BROWSER.md  → REST endpoints
│       ├── MODULE_DOWNLOAD_PAPER.md → 9-source PDF downloader
│       ├── MODULE_FITCH_CITATIONS.md → citation mining algorithm
│       ├── MODULE_GRAPH_UTILS.md   → NetworkX + Jaccard
│       ├── DEPENDENCIES.md         → library version pins
│       └── DOCUMENTATION_SYSTEM.md → meta-doc on the documentation layout
│
├── Data Directories
│   ├── downloaded_papers/          → Downloaded PDF/MD files
│   ├── output/                     → Graph HTML outputs
│   └── database/                   → split SQLite layout
│       ├── index.db                  144K-paper metadata index
│       ├── {year}.db × 156           per-year citation files
│       └── unknown.db                NULL-year citation file
```

---

## 🔑 Core Concepts

### 1. Citation Network Data Model

**`database/index.db` / `papers` table**: 144,015 unique papers (by DOI)
- Metadata: title, year, journal, authors
- Indexed by DOI and year

**`database/{year}.db` / `citations` table**: 13,717,945 directed relationships
- One file per source-paper year (1949–2026 + `unknown.db`)
- Format: `(source_doi, target_doi, direction, coefficient)`
- Direction values stored on disk: `'forward'` (= Citation list / incoming citers) and `'backward'` (= Reference list / outgoing references). These legacy column values are encapsulated inside `db_sqlite.py`; every public Python API and JSON response uses the words **`citation`** and **`reference`** instead.
- Coefficient: NULL for raw edges, 0.0–1.0 for Jaccard-scored edges
- Indexed on both `source_doi` and `target_doi` for fast bidirectional lookup

**Paper Structure** (in-memory representation):
```python
{
    "doi": "10.1038/nphys2439",
    "metadata": {"title": "...", "year": 2012, "journal": "...", "authors": [...]},
    "citation":  ["10.xxx", ...],                  # Citation (被引信息 - who cites this)
    "reference": ["10.yyy", ...],                  # Reference (参考文献 - what this cites)
    "classified_citation":  [{"doi": "...", "coefficient": 0.25}, ...],
    "classified_reference": [],
    "last_updated": "2026-04-21"
}
```

### 2. Jaccard Similarity Coefficient

Used to filter related papers during mining:
```
Jaccard(A, B) = |citations(A) ∩ citations(B)| / |citations(A) ∪ citations(B)|
```

**Range**: 0.0 (completely different) → 1.0 (identical citations)

**Threshold**: Only papers with Jaccard ≥ 0.1 are pursued in mining (prevents topic drift)

**Storage**: Only a small fraction of citations get a coefficient (the rest are NULL). The miner only scores edges that cross the `THRESHOLD`.

### 3. Download Priority (9 Sources)

Attempts sources in order, returns on first success:
1. Playwright DOI page ← Most reliable for paywalled papers
2. doi2pdf ← Fast direct conversion
3. OpenAlex API ← Open access links
4. Crossref API ← Publisher metadata
5. Unpywall API ← OA database
6. arXiv ← Preprints
7. Scidownl ← Sci-Hub wrapper
8. Sci-Hub direct ← Unreliable mirror
9. Playwright stealth ← Last resort browser automation

### 4. API Integration

**Semantic Scholar**: Fast, comprehensive citations
**Crossref**: Authoritative DOI service, slower
**OpenAlex, Unpywall**: Open access metadata
**arXiv**: Preprints API

All respect rate limits (1.2s delay between requests)

---

## 📊 Module Interaction Flow

```
User Input (DOI list)
  ↓
fitch_citations.py [run_miner()]
├─ Fetch from S2 + Crossref APIs
├─ Calculate Jaccard similarity
├─ Filter by threshold (≥0.1)
└─ Save to db_sqlite.py
  ↓
download_paper.py [process_doi_list()]
├─ Check if already downloaded
├─ Try 9 sources in priority order
├─ Validate PDF (magic bytes, structure)
├─ Generate Markdown (MarkItDown or Marker)
├─ Search supplements (PDF text → Datahugger)
└─ Generate CSV report
  ↓
web services [data_browser, graph_server, download_server]
├─ Query db_sqlite.py via load_db()
├─ Compute similarities via graph_utils.py
├─ Serve REST APIs
└─ Render HTML visualizations
  ↓
Output: JSON/CSV/HTML/Markdown
```

---

## 🔧 Key Functions Reference

### Database Operations
- `db_sqlite.init_db()` - Create schema (idempotent)
- `db_sqlite.get_paper(doi)` - One paper with citations (~1.5 ms)
- `db_sqlite.get_metadata(doi)` / `get_metadata_batch(dois)` - metadata only
- `db_sqlite.list_papers_paginated(year_min, year_max, search, sort_by, page, per_page)` - paginated listing (~20 ms / page)
- `db_sqlite.search_metadata(query)` - SQL LIKE search (~100 ms)
- `db_sqlite.find_citing_dois(target)` - reverse lookup (~80 ms)
- `db_sqlite.upsert_paper(data)` - Insert/update (~10–50 ms)
- `db_sqlite.load_db_year_range(min, max)` - year-scoped bulk load
- `db_sqlite.load_db()` - full library, **minutes**, avoid in hot paths
- `db_sqlite.migrate_from_legacy(path)` - one-shot import from old single-file DB

### Similarity Search
- `similarity_search.find_similar(seed_doi, year_min, year_max, top_n, direction, workers)` - parallel Jaccard ranking across year DBs (~3 s full-library)
- CLI: `python similarity_search.py SEED_DOI [--year-min] [--year-max] [--top] [--output doi,year,title,journal,similarity]`

### Citation Mining
- `fitch_citations.run_miner(seeds, force_update=False)` - Build network (depth + threshold are module-level constants)
- `fitch_citations.fetch_combined_data(doi)` - Fetch metadata (1–2 s)

### Paper Downloading
- `download_paper.process_doi_list(dois, output_dir)` - Batch download
- `download_paper.download_pdf(doi, output_dir, title, year)` - Single PDF
- `download_paper.pdf_to_markdown(pdf_path, md_path)` - Convert PDF
- `download_paper.download_supplementary_materials(...)` - Get supplements

### Graph Analysis
- `graph_utils.calculate_jaccard(list_a, list_b)` - Similarity (0.0079ms)
- `graph_utils.extract_subgraph(db, seeds, max_fwd, max_bwd)` - Subgraph
- `graph_utils.compute_jaccard_to_seeds(db, node_doi, seeds)` - Multi-similarity

### Data Export
- `data_export.export_to_json(dois, file)` - Full structure
- `data_export.export_to_csv(dois, file)` - Spreadsheet format
- `data_export.export_to_txt(dois, file, key_list)` - Text format

### Web APIs (3 Flask servers)
- `graph_server.py:5000` - POST `/api/graph` → Network visualization
- `data_browser.py:5001` - GET `/api/papers?...` → Search/filter papers
- `download_server.py:5003` - POST `/api/download-start` → Async downloads

---

## 📋 Coding Conventions

### Naming
- DOI strings: lowercase, e.g., `"10.1038/nphys2439"`
- File names: `{year}--{sanitized_title}.{ext}`, e.g., `2012--coherent-synchrotron.pdf`
- Functions: snake_case, descriptive, e.g., `extract_supplementary_from_pdf()`
- Classes: CamelCase (rare in this project)

### Documentation
- Each module starts with docstring explaining purpose
- Functions have parameter types and return types
- Examples provided for non-obvious functions
- Complex algorithms have inline comments

### Error Handling
- API failures: Log + return None (graceful degradation)
- File I/O: Check existence before reading
- Database: Let sqlite3 raise exceptions (atomic transactions)
- Network: Respect rate limits (1.2s delay)

### Performance Priorities
1. Batch operations over individual (10K papers: 1 load vs. 10K get_paper calls)
2. Caching (5-minute DB cache in data_browser)
3. Lazy evaluation (compute similarity only when needed)
4. Parallelization (download_paper supports multiple sources)

### Testing
- Test files: `test_*.py` and `run_test_*.py` in root
- Coverage: Core modules (db, download, graph) well-tested
- Integration: End-to-end workflows tested

---

## 🚀 Quick Operations

### Start Mining
```bash
source /home/zhiping/research-env/bin/activate
python main.py fitch --file doi_list.txt
```

### Download Papers
```bash
python main.py download --file doi_list.txt --output papers/
```

### Launch Web Services
```bash
# Terminal 1: Graph server
python graph_server.py

# Terminal 2: Data browser
python data_browser.py

# Terminal 3: Download manager
python download_server.py
```

### Access Web UIs
- Graph: http://localhost:5000
- Data: http://localhost:5001
- Downloads: http://localhost:5003

---

## 🔍 How to Help Users

### "How do I download papers?"
→ See `docs/MODULE_DOWNLOAD_PAPER.md`: process_doi_list() example

### "How do I find similar papers?"
→ See `docs/MODULE_GRAPH_UTILS.md`: compute_jaccard_to_seeds() example

### "How do I query the database?"
→ See `docs/MODULE_DB_SQLITE.md`: load_db() and get_paper() examples

### "How do I understand the database schema?"
→ See `docs/MODULE_DB_SQLITE.md`: Schema section

### "How does the mining algorithm work?"
→ See `docs/MODULE_FITCH_CITATIONS.md`: Algorithm section

### "How do I use the REST APIs?"
→ See `docs/MODULE_DATA_BROWSER.md`: API Endpoints section

### "Performance is slow, how do I debug?"
→ Check Performance Metrics in relevant module doc

### "I want to extend the system"
→ See `docs/ARCHITECTURE.md`: Extension Development section

---

## 🔄 Post-Modification Update Guide

After making changes to any file, update documentation:

**Changed db_sqlite.py?**
→ Update `docs/MODULE_DB_SQLITE.md` (especially if schema changes)

**Changed download_paper.py?**
→ Update `docs/MODULE_DOWNLOAD_PAPER.md` (function signatures, performance)

**Changed fitch_citations.py?**
→ Update `docs/MODULE_FITCH_CITATIONS.md` (algorithm, parameters)

**Changed web APIs?**
→ Update `docs/MODULE_DATA_BROWSER.md` (endpoint signatures)

**Changed core architecture?**
→ Update `docs/ARCHITECTURE.md` (data flow, module interaction)

**Added new file?**
→ Create `docs/MODULE_NEWFILE.md` following template pattern

---

## 📊 Database Stats

Current state as of 2026-06-08:

| Metric | Value |
|--------|-------|
| Papers (`index.db`) | 144,015 |
| Citations (across `{year}.db` × 156) | 13,717,945 |
| Year DBs on disk | 156 (1949–2026 + `unknown.db`) |
| Total DB footprint | ~2.6 GB |
| `get_paper(doi)` | ~1.5 ms |
| `list_papers_paginated()` per 50-row page | ~20 ms |
| `similarity_search` full-library scan | ~3 s (8 worker processes) |
| Download time (100 papers) | 8–15 minutes |

---

## 🛠️ Troubleshooting Common Issues

### "Database locked" error
- **Cause**: Multiple processes writing simultaneously
- **Solution**: Use SQLite WAL mode (already enabled in _connect())

### API rate limiting
- **Cause**: Too many requests to S2/Crossref
- **Solution**: Increase REQUEST_DELAY in fitch_citations.py

### PDF validation failures
- **Cause**: HTML file passed as PDF (from captcha)
- **Solution**: is_valid_pdf() catches these automatically

### Memory issues with load_db()
- **Cause**: Full library is 144K papers + 13.7M citations (several GB)
- **Solution**: Don't call `load_db()` in hot paths. Use `load_db_year_range`,
  `list_papers_paginated`, `get_metadata_batch`, or `get_paper` instead.

---

## 📈 Recommended Next Steps for Improvements

1. **Optimize Jaccard pre-computation**: Current 3% coverage; could precompute more
2. **Add PDF OCR**: For scanned papers (use Marker library)
3. **Implement Redis caching**: Speed up repeated similarity queries
4. **Parallel mining**: Use multiprocessing for faster BFS traversal
5. **Add authentication**: For multi-user deployments

---

## 🔗 Documentation Files

**Quick-start walkthroughs**:
- `docs/Quick_Start_AI.md` — developer / agent walkthrough (English)
- `docs/Quick_Start_CN.md` — developer walkthrough (Chinese)

**Module guides** (consult before answering module-specific questions):
- `docs/MODULE_DB_SQLITE.md` — split-by-year SQLite layout + helpers
- `docs/MODULE_DATA_BROWSER.md` — REST endpoints
- `docs/MODULE_DOWNLOAD_PAPER.md` — 9-source PDF downloader
- `docs/MODULE_FITCH_CITATIONS.md` — BFS citation mining
- `docs/MODULE_GRAPH_UTILS.md` — NetworkX + Jaccard helpers

**System-wide**:
- `docs/ARCHITECTURE.md` — full data flow + module interactions
- `docs/DEPENDENCIES.md` — library version pins
- `docs/DOCUMENTATION_SYSTEM.md` — meta-doc

---

## 📞 Getting Help

1. **Module-specific question?** → Read `docs/MODULE_*.md` file
2. **Architecture question?** → Read `docs/ARCHITECTURE.md`
3. **Performance issue?** → Check Performance Metrics in relevant module
4. **Bug report?** → Check Troubleshooting section above
5. **Feature request?** → See Recommended Next Steps section

---

## ✅ Before Committing Code

- [ ] Read relevant `docs/MODULE_*.md` file to understand conventions
- [ ] Update module docs after changes
- [ ] Run tests: `python test_*.py`
- [ ] Check syntax: `python -m py_compile *.py`
- [ ] Verify database operations work
- [ ] Add comments for complex logic

---

## 📅 Version History

| Version | Date | Changes |
|---------|------|---------|
| 5.0 | 2026-06-08 | Split single DB into `database/index.db` + `{year}.db × 156`; new `similarity_search.py` (parallel Jaccard + CLI); `data_browser` rewritten to use SQL pagination — no in-memory full-DB cache; docs consolidated under `docs/` |
| 4.0 | 2026-04-21 | Added PDF→MD, supplementary detection, comprehensive docs |
| 3.0 | 2026-04-20 | Improved supplementary file finding, performance optimization |
| 2.0 | 2026-04-15 | SQLite migration, JSON compatibility maintained |
| 1.0 | 2026-04-01 | Initial release |

---

**Last Updated**: 2026-06-08  
**Maintainer**: AI-Assisted Development  
**Status**: ✅ Production-ready (v4.0)
