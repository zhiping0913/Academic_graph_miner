# Quick Start (Developer / AI agents)

**Target**: AI agents and developers working with this codebase programmatically.
**Audience**: assumes Python literacy and basic familiarity with SQLite + Flask.
**Authoritative module docs**: `docs/MODULE_*.md` — read those for full APIs.

---

## 1. Install

Requires Python 3.10+ (tested on 3.12).

```bash
# Use the dedicated research virtualenv on this host
source /home/zhiping/research-env/bin/activate

# Or roll a fresh venv:
python -m venv venv && source venv/bin/activate

pip install -r requirements.txt
playwright install chromium      # only needed for the Playwright download paths
```

Verify:

```bash
python -c "import flask, networkx, pandas, sqlite3; print('ok')"
```

Key runtime dependencies:

| Library | Why |
|---|---|
| `flask` | three small REST servers (browser / graph / downloads) |
| `requests`, `beautifulsoup4`, `lxml` | API + HTML scraping |
| `playwright` | last-resort browser automation for PDF fetch |
| `pdfplumber`, `markitdown` | PDF → text + Markdown |
| `networkx`, `pyvis` | subgraph extraction + interactive viz |
| `unpywall`, `scidownl`, `doi2pdf` | additional download sources |
| `pathvalidate`, `python-dateutil` | utilities |

---

## 2. Repository layout

```
Academic_graph_miner/
├── db_sqlite.py            persistence layer (split-by-year SQLite)
├── similarity_search.py    parallel Jaccard ranking + CLI
├── fitch_citations.py      BFS citation miner (Semantic Scholar + Crossref + OpenCitations)
├── download_paper.py       9-source PDF downloader + supplementary discovery
├── graph_utils.py          NetworkX-based subgraph + Jaccard helpers
├── data_export.py          JSON / CSV / TXT export helpers
├── data_browser.py         Flask :5001  paper browsing + similarity API
├── graph_server.py         Flask :5000  interactive citation-graph API
├── download_server.py      Flask :5003  async download queue
├── main.py                 thin CLI dispatcher (fitch / download / all)
├── backend.py              path config
├── database/               split SQLite layout (see below)
│   ├── index.db                     paper metadata only
│   ├── {year}.db                    citations whose source paper is from {year}
│   └── unknown.db                   citations for NULL-year papers
└── docs/                   this directory
```

---

## 3. Database — split-by-year SQLite

All database access goes through **`db_sqlite.py`**. The legacy single-file
`academic_knowledge_graph.db` has been split into `database/index.db` (paper
metadata) plus one `{year}.db` per publication year (citations).

Current scale: **144,015 papers / 13,717,945 citations** across 156 year DBs.

### Public API (preserved from the legacy single-file shape)

```python
from db_sqlite import (
    load_db,                      # {doi: paper_dict}  full library
    get_paper,                    # one paper_dict by DOI
    upsert_paper,                 # insert/update one paper + its citations
    save_db,                      # batch upsert
    is_expired,                   # metadata-age check
    DB_PATH,                      # path to database/ directory
)
```

`paper_dict` shape:

```python
{
    "doi": "10.1038/nphys2439",
    "metadata": {
        "title":   "Coherent synchrotron emission ...",
        "year":    2012,
        "journal": "Nature Physics",
        "authors": ["...", ...],
    },
    "citation":             ["10.xxx", ...],   # papers citing this one (incoming)   — "Citation"
    "reference":            ["10.yyy", ...],   # this paper's references (outgoing)  — "Reference"
    "classified_citation":  [{"doi": "...", "coefficient": 0.31}, ...],
    "classified_reference": [...],
    "last_updated": "2026-06-08",
}
```

### Fast helpers added for the split layout

```python
from db_sqlite import (
    load_db_year_range,           # year-scoped bulk load (rows + citations)
    list_papers_paginated,        # SQL LIMIT/OFFSET listing; metadata only
    get_metadata,                 # one paper, metadata only
    get_metadata_batch,           # bulk metadata by DOI list
    search_metadata,              # SQL LIKE on doi + title; ranked
    get_citation_counts,          # batched {doi: {citation, reference}}
    find_citing_dois,             # reverse lookup: who cites target_doi
    list_available_years,         # year-DB files on disk
)
```

Pick the right helper:

| Need | Use |
|---|---|
| Full `{doi: paper_dict}` (rare; slow) | `load_db()` |
| One paper + its citations | `get_paper(doi)` |
| One paper, metadata only | `get_metadata(doi)` |
| Bulk metadata for known DOIs | `get_metadata_batch(dois)` |
| Paginated UI listing | `list_papers_paginated(...)` |
| Autocomplete / search box | `search_metadata(query, limit=20)` |
| Counts only (no neighbor lists) | `get_citation_counts(dois)` |
| Who cites X? | `find_citing_dois(target_doi)` (default `direction='reference'`) |

### One-shot legacy migration

If a legacy `academic_knowledge_graph.db` still exists at the project root:

```bash
python db_sqlite.py migrate [path/to/legacy.db]
```

Idempotent: re-running `INSERT OR REPLACE`s everything.

---

## 4. Similarity ranking — `similarity_search.py`

Parallel Jaccard scoring across every year DB. Each year is scored in its own
worker process, then per-year top-N heaps are merged.

### Library

```python
from similarity_search import find_similar

hits = find_similar(
    seed_doi="10.1016/j.cnsns.2026.109994",
    year_min=2020,     # optional inclusive lower bound
    year_max=2026,     # optional inclusive upper bound
    top_n=50,
    direction="both",  # "citation" | "reference" | "both"
    workers=None,      # default min(cpu_count, 8)
)
# hits = [{doi, year, title, journal, similarity, citation_count}, ...]
```

`direction="both"` (default) takes the union of `citation + reference` as the
neighborhood. `"citation"` matches only citers (Citation list); `"reference"`
matches only references (Reference list).

### CLI

```bash
# Just DOIs (default)
python similarity_search.py 10.1016/j.cnsns.2026.109994 --top 20

# Three-column TSV with header
python similarity_search.py 10.1016/j.cnsns.2026.109994 \
    --top 20 --output doi,year,title --header

# Restrict candidate years + show similarity column
python similarity_search.py 10.1016/j.cnsns.2026.109994 \
    --year-min 2020 --year-max 2026 \
    --output similarity,doi,title
```

Valid `--output` fields: `doi`, `year`, `title`, `journal`, `similarity`
(comma-separated, order preserved). Output is TSV.

Reference timings on this host (144K papers / 156 year DBs):

| Operation | Time |
|---|---|
| `find_similar` full-library scan, 30-edge seed, 8 workers | ~3 s |
| `find_similar` year-scoped (2020–2026) | ~1 s |

---

## 5. Citation mining — `fitch_citations.py`

BFS crawler over Semantic Scholar + Crossref (+ OpenCitations as a fallback for
both `citation` and `reference` directions).

### Library

```python
from fitch_citations import run_miner, fetch_combined_data

# Build / extend the network around a seed list. depth + threshold are
# module-level constants (MAX_DEPTH=2, THRESHOLD=0.1) inside fitch_citations.py.
run_miner(seeds=["10.1038/nphys2439"], force_update=False)

# Fetch metadata + citation/reference DOI lists for a single paper
paper = fetch_combined_data("10.1038/nphys2439")
```

`run_miner(seeds, force_update=False)` walks the seeds, fetches each paper's
`citation` + `reference` lists, computes Jaccard against seeds, and queues
neighbors above `THRESHOLD` for the next depth level. Everything is persisted
via `upsert_paper`.

### CLI

```bash
# Read DOIs from a file (default: doi_list.txt)
python fitch_citations.py --file my_dois.txt

# Pass DOIs inline
python fitch_citations.py --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

# Re-fetch even if local cache is still within UPDATE_DAYS
python fitch_citations.py --file my_dois.txt --force-update
```

Tunable constants at the top of `fitch_citations.py`: `THRESHOLD` (Jaccard
filter, default 0.1), `MAX_DEPTH` (2), `UPDATE_DAYS` (1000), `REQUEST_DELAY`
(1.2 s — respect API rate limits).

---

## 6. PDF acquisition — `download_paper.py`

Tries up to 9 sources in priority order; returns on first success and validates
the result (magic bytes + structure).

### Library

```python
from download_paper import process_doi_list, download_pdf

# Batch — returns a pandas DataFrame report
df = process_doi_list(
    dois=["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"],
    output_base_dir="downloaded_papers/",
)
print(df[["DOI", "PDF_Status", "PDF_Path", "Supplementary_Status"]])

# Single paper — returns (status_message, pdf_path_or_empty_string)
status, path = download_pdf(
    doi="10.1038/nphys2439",
    output_dir="downloaded_papers/",
    title="Coherent synchrotron emission",
    year="2012",
)
```

Source order: Playwright DOI page → doi2pdf → OpenAlex → Crossref → Unpywall →
arXiv → Scidownl → Sci-Hub direct → Playwright stealth. After download, the
module also extracts text (`pdfplumber`), converts to Markdown (`markitdown`),
and searches for supplementary materials.

### CLI

```bash
python download_paper.py --file my_dois.txt --output downloaded_papers
python download_paper.py --doi 10.1038/nphys2439
```

---

## 7. Top-level CLI — `main.py`

Thin dispatcher around the three workflows:

```bash
python main.py fitch    --file seeds.txt
python main.py download --file seeds.txt --output papers/
python main.py all      --file seeds.txt --output papers/    # fitch then download
```

---

## 8. Web services

Three independent Flask apps, each safe to run standalone:

| Script | Port | Purpose |
|---|---|---|
| `data_browser.py` | 5001 | paginated paper browsing, search, seed-based similarity ranking, citing/reference lookups, export |
| `graph_server.py` | 5000 | interactive citation-graph rendering |
| `download_server.py` | 5003 | async download queue |

Run any of them with `python <script>.py`.

### `data_browser.py` endpoints (current)

| Endpoint | Notes |
|---|---|
| `GET /api/papers?page=1&per_page=50` | SQL-paginated; defaults to current year only (~20 ms / page) |
| `GET /api/papers?ref_doi=…` | delegates to `similarity_search.find_similar`; full-library Jaccard ranking (~3 s) |
| `GET /api/search-papers?search=…` | SQL `LIKE` on title + DOI (~100 ms) |
| `GET /api/citing-papers?doi=…` | parallel reverse lookup (~80 ms) |
| `GET /api/reference-papers?doi=…` | target's own `reference` list + batched metadata (~40 ms) |
| `POST /api/fetch-paper` | pulls missing DOI from upstream APIs, persists via `upsert_paper` |
| `POST /api/export` | JSON / CSV / TXT export of a selected DOI list |

No endpoint loads the full 144K-paper DB anymore.

---

## 9. Graph & export helpers

`graph_utils.py`:

```python
from graph_utils import calculate_jaccard, extract_subgraph, compute_jaccard_to_seeds

# Jaccard over any two DOI lists
sim = calculate_jaccard(["10.a/b", "10.c/d"], ["10.c/d", "10.e/f"])  # 0.333…

# Build a NetworkX DiGraph centered on seeds
db = load_db()                  # or per-year load if scope is tight
G = extract_subgraph(db, seed_dois=["10.1038/nphys2439"],
                     max_citation_dist=1, max_reference_dist=1)
G.number_of_nodes(), G.number_of_edges()
```

`data_export.py`:

```python
from data_export import export_to_json, export_to_csv, export_to_txt

export_to_json(["10.1038/nphys2439"], "out.json")
export_to_csv(["10.1038/nphys2439"], "out.csv")
export_to_txt(["10.1038/nphys2439"], "out.txt",
              key_list=["doi", "title", "year", "journal"])
```

Run `python data_export.py --help` for the CLI form.

---

## 10. End-to-end workflows

### A. From seeds to ranked similar papers (no PDF download)

```bash
echo "10.1038/nphys2439" > seeds.txt
python fitch_citations.py --file seeds.txt

# Pick a seed and rank the rest of the library against it
python similarity_search.py 10.1038/nphys2439 \
    --year-min 2018 --top 50 --output doi,year,title --header
```

### B. Browse + export a curated DOI list, then bulk download

```bash
python data_browser.py &        # http://localhost:5001
# Pick papers in the UI, export as TXT (one DOI per line) → selected.txt

python download_paper.py --file selected.txt --output downloaded_papers/
```

### C. Find papers that cite a target (reverse lookup)

```python
from db_sqlite import find_citing_dois, get_metadata_batch

citers = find_citing_dois("10.1038/nphys2439")  # default direction='reference'
meta = get_metadata_batch(citers)
for doi in citers:
    m = meta[doi]["metadata"]
    print(m["year"], doi, m["title"])
```

---

## 11. Common pitfalls

- **Don't open `database/*.db` directly.** Everything routes through
  `db_sqlite.py` — the split layout means you'd silently miss citations from
  other years. Use the helpers in §3.
- **`load_db()` is expensive (~minutes for the full 144K-paper DB).** Almost
  every caller has a year-scoped helper available; use it.
- **Naming**. The Python API and JSON responses use **`citation`** (incoming —
  papers citing this one; 被引) and **`reference`** (outgoing — papers this one
  cites; 参考文献). The underlying SQLite `direction` column still stores the
  legacy values `'forward'` (= `citation`) and `'backward'` (= `reference`);
  that translation happens inside `db_sqlite.py` and never leaks out. Nothing
  outside that module should mention `forward` / `backward`.
- **API rate limits.** `fitch_citations.py` sleeps `REQUEST_DELAY = 1.2 s`
  between API calls. Don't lower this in production — Semantic Scholar /
  Crossref will throttle aggressively.
- **PDF validity.** `is_valid_pdf()` rejects HTML masquerading as PDF
  (captchas, error pages). On failure, the downloader falls through to the
  next source.

---

## 12. Further reading

| Doc | When to read |
|---|---|
| `docs/ARCHITECTURE.md` | Full system overview + data flow |
| `docs/MODULE_DB_SQLITE.md` | DB schema + helper APIs + perf |
| `docs/MODULE_FITCH_CITATIONS.md` | Mining algorithm + tuning |
| `docs/MODULE_DOWNLOAD_PAPER.md` | All 9 download sources + validators |
| `docs/MODULE_DATA_BROWSER.md` | REST endpoints |
| `docs/MODULE_GRAPH_UTILS.md` | Jaccard + subgraph algorithms |
| `docs/DEPENDENCIES.md` | Library version pins |
