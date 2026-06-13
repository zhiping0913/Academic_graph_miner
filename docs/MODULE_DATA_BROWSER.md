# 📊 Data Browser Module Reference

**File**: `data_browser.py`
**Purpose**: Flask REST API for browsing papers, ranking by similarity to a seed,
performing reverse-citation lookups, and exporting selected DOIs.
**Status**: Production-ready (rewritten 2026-06-08 for the split-by-year DB layout).

---

## 🎯 Quick Start

### Launch the server

```bash
source /home/zhiping/research-env/bin/activate
python data_browser.py
# Server running on http://localhost:5001
```

The static HTML UI is served at `/`; the REST endpoints are under `/api/...`.

### Smallest possible probe

```bash
# First 50 papers from the default year (current calendar year)
curl 'http://localhost:5001/api/papers?per_page=50&page=1'
```

---

## 🧱 Design notes

- **No in-memory full-DB cache**. The previous implementation held all 144K
  papers (and citations) in RAM behind a 5-minute cache. The current version
  serves every endpoint from `db_sqlite` helpers directly. There is no
  `get_cached_db()` function anymore.
- **Default year**: `DEFAULT_YEAR = datetime.now().year` (currently 2026). When
  the caller doesn't supply `year_min` / `year_max`, the plain listing only
  reads papers from that one year via SQL `LIMIT / OFFSET`.
- **Similarity ranking** (`ref_doi`) is delegated to
  `similarity_search.find_similar`, which scans every year DB in parallel.
- **Reverse lookup** (`/api/citing-papers`) uses
  `db_sqlite.find_citing_dois`, which queries every year DB in parallel
  (each is indexed on `target_doi`).

---

## 🔌 API endpoints

### `GET /api/papers` — listing + similarity ranking

| Parameter | Type | Default | Notes |
|---|---|---|---|
| `page` | int | 1 | 1-based |
| `per_page` | int | 50 | clamped to [10, 500] |
| `search` | str | "" | matches against title OR doi (case-insensitive) |
| `year_min` | int | `DEFAULT_YEAR` | inclusive lower bound |
| `year_max` | int | `DEFAULT_YEAR` | inclusive upper bound |
| `ref_doi` | str | "" | if set: enter similarity-ranking mode |
| `similarity_min` | float | 0 | only honored in similarity mode |
| `sort_by` | str | `year_desc` | `year_desc` / `year_asc` / `title_asc`; in similarity mode also `similarity_desc` / `similarity_asc` |

**Plain listing path** (no `ref_doi`):
- Calls `db_sqlite.list_papers_paginated(year_min, year_max, search, sort_by, page, per_page)`.
- Fetches `(citation, reference)` counts for the returned 50 DOIs via
  `db_sqlite.get_citation_counts` — no full neighbor lists are loaded.
- Typical latency: **~20 ms / page**.

**Similarity path** (`ref_doi` set):
- Calls `similarity_search.find_similar(ref_doi, year_min, year_max,
  top_n=max(per_page*5, 200), direction="both")`.
- Applies `search` / `similarity_min` filters on top of the ranked list, then
  paginates locally.
- Typical latency for a 30-edge seed against the full library: **~3 s**.

Response shape (both paths):

```json
{
  "status": "success",
  "total": 1815,
  "total_pages": 37,
  "page": 1,
  "per_page": 50,
  "year_range": [2026, 2026],
  "papers": [
    {
      "doi": "10.1063/5.0303752",
      "title": "Attosecond MeV γ-ray pulse compression …",
      "year": 2026,
      "journal": "Physics of Plasmas",
      "authors_count": 7,
      "citation_count": 38,
      "reference_count": 24,
      "similarity": 0.1045        // present only in similarity mode
    }
  ]
}
```

---

### `GET /api/search-papers` — autocomplete

| Parameter | Type | Notes |
|---|---|---|
| `search` | str | minimum 2 chars; matches DOI prefix first, then title substring |

Uses `db_sqlite.search_metadata(query, limit=20)`. Returns up to 20 metadata
rows: `{doi, title, year, journal}`. Latency: **~100 ms** against the 144K-paper
`index.db`.

---

### `GET /api/citing-papers` — reverse citation lookup

| Parameter | Type | Notes |
|---|---|---|
| `doi` | str | target DOI; must exist in the DB |

Calls `db_sqlite.find_citing_dois(target, direction='reference')` to find every
paper whose `reference` (Reference) list contains `target` — i.e. every paper
that actually cites the target — then bulk-loads metadata and citation counts
for those citers. Returns sorted by year DESC.

Latency: **~80 ms** thanks to the `idx_cit_tgt` index on each year DB and the
threaded scan across files.

Response:

```json
{
  "status": "success",
  "total": 34,
  "papers": [
    { "doi": "...", "title": "...", "year": 2023,
      "journal": "...", "authors_count": 3,
      "citation_count": 12, "reference_count": 45 },
    ...
  ]
}
```

---

### `GET /api/reference-papers` — target's own bibliography

| Parameter | Type | Notes |
|---|---|---|
| `doi` | str | target DOI |

Returns the metadata + counts for every DOI in the target's `reference` list
that also exists in the DB. Uses `get_paper` + `get_metadata_batch` +
`get_citation_counts`. Latency: **~40 ms**.

---

### `POST /api/fetch-paper` — pull a missing DOI from upstream APIs

Body: `{"doi": "..."}`.

- If the DOI already exists, returns the stored paper.
- Otherwise calls `fitch_citations.fetch_combined_data(doi)`, persists with
  `db_sqlite.upsert_paper`, and returns the new record.

There is no cache to invalidate — subsequent reads see the new row immediately.

---

### `POST /api/export` — bulk export

Body:

```json
{ "dois": ["10.xxx", "10.yyy"],
  "format": "json" | "csv" | "txt-doi" | "txt-detail" }
```

Streams a temp file back as `Content-Disposition: attachment`. Filenames are
timestamped: `papers_YYYYMMDD_HHMMSS.{ext}`.

---

## 📈 Performance reference

| Operation | Old (single-DB, in-memory cache) | Current |
|---|---|---|
| First open / listing | ~5 s (loads 144K papers) | **~20 ms** (one page from `index.db`) |
| Search box (autocomplete) | scanned cached dict | **~100 ms** (SQL `LIKE`) |
| Similarity ranking | not feasible (OOM risk) | **~3 s** (parallel scoring across 156 year DBs) |
| Reverse citation lookup | scanned cached dict | **~80 ms** |

---

## 🧩 Imports — which `db_sqlite` helpers this module uses

```python
from db_sqlite import (
    get_paper,
    upsert_paper,
    get_metadata,
    get_metadata_batch,
    search_metadata,
    get_citation_counts,
    find_citing_dois,
    list_papers_paginated,
)
from similarity_search import find_similar
```

If you want to add a new endpoint, prefer reusing these helpers over writing
ad-hoc SQL — they handle the multi-file routing for you.

---

## 🛠️ Extending

- **New filter on the listing**: add a clause inside
  `db_sqlite.list_papers_paginated` (it already does SQL year + search +
  sort); keep the endpoint thin.
- **New similarity mode**: pass `direction="citation"` or `"reference"` to
  `find_similar` for co-citation / bibliographic-coupling variants.
- **Caching**: not currently needed for paginated reads. If you do add a
  cache, key on the full query string and keep a short TTL (60 s).

---

## 🧪 Smoke-testing

```bash
# Start the server in the background
python data_browser.py >/tmp/db.log 2>&1 &

# Plain listing — current year
curl -s 'http://localhost:5001/api/papers?per_page=3' | jq .total

# Similarity ranking
curl -s 'http://localhost:5001/api/papers?ref_doi=10.1038%2Fnphys2439&per_page=5' \
    | jq '.papers[] | {doi, similarity}'

# Reverse lookup
curl -s 'http://localhost:5001/api/citing-papers?doi=10.1038%2Fnphys2439' | jq .total
```
