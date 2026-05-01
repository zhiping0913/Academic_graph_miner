# 🏛️ Academic Graph Miner - Codebase Guide

**Project**: Academic Graph Miner  
**Purpose**: Automated citation network mining, paper downloading, and knowledge graph visualization  
**Tech Stack**: Python 3.10+, SQLite3, Flask, NetworkX, Playwright, MarkItDown  
**Status**: ✅ Production-ready (v4.0, as of 2026-04-21)

---

## Role & Responsibilities

You are the expert on this codebase. Your responsibilities:

1. **Before answering questions**: Consult the module documentation (`MODULE_*.md` files)
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
├── Documentation (THIS)
│   ├── MODULE_DOWNLOAD_PAPER.md    → download_paper.py guide
│   ├── MODULE_DATA_BROWSER.md      → data_browser.py guide
│   ├── MODULE_DB_SQLITE.md         → Database operations
│   ├── MODULE_FITCH_CITATIONS.md   → Citation mining algorithm
│   ├── MODULE_GRAPH_UTILS.md       → Graph utilities
│   ├── ARCHITECTURE.md             → System architecture overview
│   ├── CLAUDE.md                   → This file
│   └── [Legacy docs]               → Various MD files (consolidation in progress)
│
├── Data Directories
│   ├── downloaded_papers/          → Downloaded PDF/MD files
│   ├── output/                     → Graph HTML outputs
│   └── academic_knowledge_graph.db → SQLite database (17K papers, 1.7M citations)
```

---

## 🔑 Core Concepts

### 1. Citation Network Data Model

**Papers Table**: 17,348 unique papers (by DOI)
- Metadata: title, year, journal, authors
- Indexed by DOI (primary key)

**Citations Table**: 1,746,807 directed relationships
- Format: (source_paper_id, target_doi, direction, coefficient)
- Directions: 'forward' (cites), 'backward' (cited by)
- Coefficient: NULL for raw edges, 0.0-1.0 for Jaccard-scored edges

**Paper Structure** (in-memory representation):
```python
{
    "doi": "10.1038/nphys2439",
    "metadata": {"title": "...", "year": 2012, "journal": "...", "authors": [...]},
    "forward": ["10.xxx", ...],                    # Forward (被引信息 - who cites this)
    "backward": ["10.yyy", ...],                   # Backward (参考文献 - what this cites)
    "classified_forward": [{"doi": "...", "coefficient": 0.25}, ...],
    "classified_backward": [],
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

**Storage**: Only ~3% of citations have coefficients (54K out of 1.7M) - rest are NULL

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
- `db_sqlite.init_db()` - Create schema
- `db_sqlite.load_db()` - Load 17K papers into memory (2-5s)
- `db_sqlite.get_paper(doi)` - Query single paper (5-10ms)
- `db_sqlite.upsert_paper(data)` - Insert/update (10-50ms)

### Citation Mining
- `fitch_citations.run_miner(seeds)` - Build network (1-5 hours)
- `fitch_citations.fetch_combined_data(doi)` - Fetch metadata (1-2s)

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
→ See `MODULE_DOWNLOAD_PAPER.md`: process_doi_list() example

### "How do I find similar papers?"
→ See `MODULE_GRAPH_UTILS.md`: compute_jaccard_to_seeds() example

### "How do I query the database?"
→ See `MODULE_DB_SQLITE.md`: load_db() and get_paper() examples

### "How do I understand the database schema?"
→ See `MODULE_DB_SQLITE.md`: Schema section

### "How does the mining algorithm work?"
→ See `MODULE_FITCH_CITATIONS.md`: Algorithm section

### "How do I use the REST APIs?"
→ See `MODULE_DATA_BROWSER.md`: API Endpoints section

### "Performance is slow, how do I debug?"
→ Check Performance Metrics in relevant module doc

### "I want to extend the system"
→ See `ARCHITECTURE.md`: Extension Development section

---

## 🔄 Post-Modification Update Guide

After making changes to any file, update documentation:

**Changed db_sqlite.py?**
→ Update `MODULE_DB_SQLITE.md` (especially if schema changes)

**Changed download_paper.py?**
→ Update `MODULE_DOWNLOAD_PAPER.md` (function signatures, performance)

**Changed fitch_citations.py?**
→ Update `MODULE_FITCH_CITATIONS.md` (algorithm, parameters)

**Changed web APIs?**
→ Update `MODULE_DATA_BROWSER.md` (endpoint signatures)

**Changed core architecture?**
→ Update `ARCHITECTURE.md` (data flow, module interaction)

**Added new file?**
→ Create `MODULE_NEWFILE.md` following template pattern

---

## 📊 Database Stats

Current state as of 2026-04-21:

| Metric | Value |
|--------|-------|
| Papers | 17,348 |
| Citations | 1,746,807 |
| With Jaccard coefficient | 54,691 (3.13%) |
| DB file size | ~500 MB |
| Load time | 2-5 seconds |
| Download time (100 papers) | 8-15 minutes |

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
- **Cause**: Loading 17K papers + 1.7M citations (~300MB)
- **Solution**: Only call once per server startup (cache for 5 min)

---

## 📈 Recommended Next Steps for Improvements

1. **Optimize Jaccard pre-computation**: Current 3% coverage; could precompute more
2. **Add PDF OCR**: For scanned papers (use Marker library)
3. **Implement Redis caching**: Speed up repeated similarity queries
4. **Parallel mining**: Use multiprocessing for faster BFS traversal
5. **Add authentication**: For multi-user deployments

---

## 🔗 Documentation Files

**Module Guides** (START HERE for specific questions):
- `MODULE_DOWNLOAD_PAPER.md` - 📥 Paper downloading (1,534 lines)
- `MODULE_DATA_BROWSER.md` - 📊 REST API for queries (285 lines)
- `MODULE_DB_SQLITE.md` - 💾 Database operations (202 lines)
- `MODULE_FITCH_CITATIONS.md` - 🔍 Citation mining (265 lines)
- `MODULE_GRAPH_UTILS.md` - 📐 Graph algorithms (73 lines)

**System Overview**:
- `ARCHITECTURE.md` - 🏗️ Complete system design (670 lines)

**Legacy Docs** (being consolidated):
- COEFFICIENT_STRATEGY_ANALYSIS.md
- PDF_TO_MARKDOWN_IMPLEMENTATION.md
- COMPLETION_CHECKLIST.md
- [Others] - Various implementation guides

---

## 📞 Getting Help

1. **Module-specific question?** → Read `MODULE_*.md` file
2. **Architecture question?** → Read `ARCHITECTURE.md`
3. **Performance issue?** → Check Performance Metrics in relevant module
4. **Bug report?** → Check Troubleshooting section above
5. **Feature request?** → See Recommended Next Steps section

---

## ✅ Before Committing Code

- [ ] Read relevant `MODULE_*.md` file to understand conventions
- [ ] Update module docs after changes
- [ ] Run tests: `python test_*.py`
- [ ] Check syntax: `python -m py_compile *.py`
- [ ] Verify database operations work
- [ ] Add comments for complex logic

---

## 📅 Version History

| Version | Date | Changes |
|---------|------|---------|
| 4.0 | 2026-04-21 | Added PDF→MD, supplementary detection, comprehensive docs |
| 3.0 | 2026-04-20 | Improved supplementary file finding, performance optimization |
| 2.0 | 2026-04-15 | SQLite migration, JSON compatibility maintained |
| 1.0 | 2026-04-01 | Initial release with 17K papers |

---

**Last Updated**: 2026-04-21  
**Maintainer**: AI-Assisted Development  
**Status**: ✅ Production-ready (v4.0)
