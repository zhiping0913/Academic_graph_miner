# 📥 Download Paper Module Reference

**File**: `download_paper.py` (1,748 lines)  
**Purpose**: Multi-source parallel PDF downloader with supplementary material detection  
**Status**: Production-ready  
**Note**: PDF to Markdown conversion removed (handled by separate program)

---

## 🎯 Quick Start

### Basic Usage

```python
from download_paper import process_doi_list, download_pdf

# Batch download 
dois = ["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"]
df_report = process_doi_list(dois, output_base_dir="papers/")
print(df_report)  # DataFrame with download status, file sizes, paths

# Single download
status, pdf_path = download_pdf(
    doi="10.1038/nphys2439",
    output_dir="papers/",
    title="My Paper Title",
    year=2012
)
print(f"Status: {status}")
print(f"File: {pdf_path}")
```

---

## 🔧 Core Functions

### Primary Entry Points

#### `process_doi_list(dois: List[str], output_base_dir: str = "papers/") -> pd.DataFrame`

**Purpose**: Batch-process a list of DOIs, downloading PDFs and supplements with progress tracking

**Parameters**:
- `dois` (List[str]): List of DOI strings, e.g., ["10.1038/nphys2439", ...]
- `output_base_dir` (str, optional): Base output directory (default: "papers/")

**Returns**: `pd.DataFrame` with columns:
```
DOI, Title, Year, PDF_Status, PDF_Path, File_Size_MB, 
Supplementary_Status, Supplementary_Files
```


**Behavior**:
1. Pre-scan: Check if PDF already exists (skip if found)
2. Download: Attempt 9 sources in priority order
3. Validate: Verify PDF structure (magic bytes, %%EOF marker)
4. Supplements: Search PDF text + fetch from Datahugger
5. Report: Generate CSV with all results

**Example**:
```python
df = process_doi_list(
    ["10.1038/nphys2439"],
    output_base_dir="my_papers/"
)
print(df[['DOI', 'Title', 'PDF_Path', 'File_Size_MB', 'Supplementary_Status']])
```

---

### Universal PDF Downloader (NEW in v4.1)

#### `download_pdf_from_url(pdf_url: str, output_path: str, source_name: str = "unknown", use_playwright: bool = True) -> bool`

**Purpose**: Unified PDF downloader with HTTP + Playwright fallback for protected URLs

**Parameters**:
- `pdf_url` (str): Direct URL to PDF file
- `output_path` (str): Where to save the PDF
- `source_name` (str): Download source name for logging (e.g., "crossref_links", "openalex")
- `use_playwright` (bool): Enable Playwright fallback (default: True)

**Strategy**:
```
1. Try Direct HTTP (FAST - works for ~95% of papers)
   └─ If success: Save and return ✓

2. If HTTP fails (403/protected):
   └─ Load URL in headless browser (Playwright)
   └─ Extract session cookies
   └─ Retry HTTP download with cookies
   └─ If success: Save and return ✓

3. If both fail: Return False
```

**Returns**: `True` if download succeeded, `False` otherwise

**Used by**:
- `download_via_crossref_links()` - Crossref API PDF links
- `download_via_openalex()` - OpenAlex OA URLs
- `download_single_supplementary()` - Supplementary materials

**Benefits** (v4.1 refactoring):
- ✅ Eliminates code duplication (3 functions consolidated)
- ✅ Consistent error handling and retry logic
- ✅ Unified logging for all PDF downloads
- ✅ Automatic fallback for protected URLs
- ✅ Better success rate for gated content

**Example**:
```python
from download_paper import download_pdf_from_url

# Works for open access
success = download_pdf_from_url(
    pdf_url="https://doi.org/10.1038/nphys2439.pdf",
    output_path="/tmp/paper.pdf",
    source_name="openalex",
    use_playwright=True
)

# Also works for APS/Springer with session cookies
# (transparent to caller)
```

---

#### `download_pdf(doi: str, output_dir: str, title: str, year: int) -> Tuple[str, str]`

**Purpose**: Download a single PDF with fallback sources

**Parameters**:
- `doi` (str): Paper DOI
- `output_dir` (str): Where to save PDF
- `title` (str): Paper title (used for naming)
- `year` (int): Publication year

**Returns**: `(status_message, pdf_path_or_empty_string)`
- status_message examples:
  - "✅ Downloaded from Playwright"
  - "✅ Downloaded from doi2pdf"
  - "❌ Failed: All sources exhausted"

**Download Priority** (tries in order):
```
1. Playwright DOI page     ← Handles JS/iframes, Anti-bot bypass
2. doi2pdf                 ← Fast direct conversion
3. OpenAlex API            ← Open access links
4. Crossref links          ← Publisher metadata
5. Unpywall API            ← OA database
6. arXiv                   ← Preprints
7. Scidownl                ← Sci-Hub wrapper
8. Sci-Hub direct          ← Direct mirror (unreliable)
9. Playwright stealth      ← Fallback browser automation with stealth
```

**⚠️ Playwright Capabilities & Limitations**:
- ✅ Handles JavaScript-heavy pages (React, Vue, Svelte, etc.)
- ✅ Processes iframes and dynamic content loading
- ✅ Bypasses simple anti-bot (user-agent, headers, delays)
- ✅ Clicks interactive elements ("View PDF", download buttons)
- ❌ Cannot bypass institutional/paywall authentication (login required)
- ❌ Cannot access IP-restricted content
- ❌ Cannot handle Cloudflare verification that requires user interaction

**Common failure scenarios**:
1. **Paywall-only papers**: No open access mirror → Requires institutional login
2. **Gated supplements**: Supplementary files behind paywall
3. **Time-limited access**: PDF link expired or preview period ended
4. **Geographic restrictions**: Content blocked outside institution network

**Alternative solutions for inaccessible papers**:
- Request via institutional VPN or network
- Check author's ResearchGate, website, or GitHub
- Request directly from authors (most respond within days)
- Look for earlier pre-prints or conference proceedings
- Check arXiv or bioRxiv for preprints

**Behavior**:
- Returns immediately on first successful download
- Validates PDF (magic bytes, structure)
- Sanitizes filename: `{year}--{sanitized_title}.pdf`
- Detects duplicates (returns existing path)

**Example**:
```python
status, pdf_path = download_pdf(
    doi="10.1038/nphys2439",
    output_dir="papers/",
    title="Coherent synchrotron emission",
    year=2012
)
if pdf_path:
    print(f"Downloaded to: {pdf_path}")
```

---

### PDF Validation & Processing

#### `is_valid_pdf(file_path: str) -> bool`

**Purpose**: Validate PDF file integrity (prevent HTML/fake PDFs)

**Checks**:
- File size ≥ 200 bytes (reject tiny files)
- Magic bytes: starts with `%PDF` (hexadecimal 25 50 44 46)
- Structure: contains `%%EOF` or `endobj` markers
- HTML detection: rejects if contains `<html>`, `<body>`, `<script>` tags

**Returns**: True if valid PDF, False otherwise

**Example**:
```python
if is_valid_pdf("paper.pdf"):
    print("✓ Valid PDF")
else:
    print("✗ Invalid or HTML file")
```

---

#### `check_paper_already_exists(output_dir: str, year: int, title: str, doi: str) -> Optional[str]`

**Purpose**: Smart deduplication - check if PDF already exists

**Logic**:
1. Check if `{year}--{sanitized_title}.pdf` exists
   - If NO → return None (needs downloading)
   - If YES → return PDF path

**Returns**: 
- Full path to PDF if found
- None if PDF doesn't exist

**Example**:
```python
existing_path = check_paper_already_exists(
    output_dir="papers/",
    year=2012,
    title="Coherent synchrotron emission",
    doi="10.1038/nphys2439"
)
if existing_path:
    print(f"Already have: {existing_path}")
else:
    print("Need to download")
```

---

### Supplementary Materials

#### `download_supplementary_materials(doi: str, output_dir: str, title: str, year: int, pdf_path: str)`

**Purpose**: Find and download supplementary materials (supporting info, datasets)

**Strategy** (3-tier approach):
1. **PDF text analysis** (<1s): Search PDF for keywords
   - Keywords: "supplementary", "supporting information", "additional data", "appendix", "extended data"
2. **Public platforms** (1-10s): Datahugger + BeautifulSoup
3. **Playwright** (30-60s): Last resort for extraction

**Returns**: `List[str]` of downloaded supplement paths

**File naming**:
- `{year}--{title}--supplementary.pdf`
- `{year}--{title}--supporting-info.pdf`

**Example**:
```python
supplements = download_supplementary_materials(
    doi="10.1038/nphys2439",
    output_dir="papers/",
    title="Coherent synchrotron emission",
    year=2012,
    pdf_path="papers/2012--coherent....pdf"
)
print(f"Downloaded {len(supplements)} supplements")
```

---

#### `extract_supplementary_from_pdf(pdf_path: str) -> List[str]`

**Purpose**: Extract supplementary file links from PDF using text analysis

**Method**:
1. Extract all text from PDF using pdfplumber
2. Search for supplementary keywords
3. Return URLs/DOIs found

**Returns**: `List[str]` of URLs/DOIs

**Performance**: <1 second per PDF (100x faster than Playwright)

---

#### `extract_text_from_pdf(pdf_path: str) -> str`

**Purpose**: Fast PDF text extraction using pdfplumber

**Returns**: Full text content of PDF

---

### Helper Functions

#### `sanitize_filename(title: str) -> str`

**Purpose**: Make title safe for filesystem

**Operations**:
- Removes special characters
- Truncates to 200 chars max
- Replaces spaces with underscores

**Example**:
```python
sanitize_filename("My Paper: A Study [2020]")
# Returns: "My_Paper_A_Study_2020"
```

---

#### `extract_text_from_pdf(pdf_path: str) -> str`

**Purpose**: Extract full text from PDF for keyword searching

**Implementation**: Uses pdfplumber

**Returns**: String of all text

---

## 📊 File Naming Convention

All downloaded files follow this pattern:

```
{year}--{sanitized_title}.pdf              # Main PDF
{year}--{sanitized_title}--supplementary.pdf  # Supplements
download_report.csv                        # Summary report
```

**Example**:
```
2012--Coherent synchrotron emission from electron nanobunches formed in relativistic laser-plasma interactions.pdf
2012--Coherent synchrotron emission from electron nanobunches formed in relativistic laser-plasma interactions--supplementary.pdf
```

**Note**: PDF to Markdown conversion is handled by a separate program, not this module.

---

## 🌐 API Sources (Priority Order)

| Source | Speed | Reliability | Auth | Method | Notes |
|--------|-------|-------------|------|--------|-------|
| Playwright DOI | Slow | ⭐⭐⭐⭐⭐ | No | Browser | Handles iframes, JS rendering |
| doi2pdf | Fast | ⭐⭐⭐⭐ | No | HTTP | Direct conversion |
| OpenAlex | Fast | ⭐⭐⭐⭐⭐ | No | **HTTP + Playwright** | API query + browser for protected URLs |
| Crossref | Fast | ⭐⭐⭐ | No | HTTP | Publisher metadata |
| Unpywall | Fast | ⭐⭐⭐⭐ | Email | HTTP | OA database |
| arXiv | Very Fast | ⭐⭐⭐⭐⭐ | No | HTTP | Preprints only |
| Scidownl | Medium | ⭐⭐⭐ | No | HTTP | Sci-Hub wrapper |
| Sci-Hub Direct | Fast | ⭐⭐ | No | HTTP | Unreliable, blacklisted |
| Playwright Stealth | Slow | ⭐⭐⭐ | No | Browser | Last resort |

### OpenAlex Strategy (Enhanced):
1. **Query API**: Get OA links from OpenAlex (fixed gzip issue)
2. **Try HTTP**: Fast path for most OA papers
3. **Use Playwright**: If HTTP returns 403, establish browser session
4. **Retry with cookies**: Some publishers require session cookies

**Recent Fix**: OpenAlex API was returning gzip-compressed responses. Fixed by setting `Accept-Encoding: identity`. Playwright fallback for protected URLs like APS journals.

---

## ⚙️ Configuration

### Headers for HTTP Requests

```python
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)...',
    'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
    # ... comprehensive browser headers
}
REQUEST_DELAY = (2, 5)  # Random delay between requests (seconds)
```

### Environment Variables (Optional)

```bash
# Unpywall API (recommended for OA papers)
export UNPYWALL_EMAIL="your_email@gmail.com"

# Playwright configuration
export PLAYWRIGHT_BROWSER="chromium"
```

---

## 📈 Performance Metrics

| Operation | Time | Notes |
|-----------|------|-------|
| PDF download (avg) | 5-30s | Depends on source |
| PDF validation | 50-100ms | Magic byte check |
| Supplementary detection (PDF) | <1s | Text search |
| Supplementary detection (web) | 1-10s | Playwright fallback |
| Batch 100 papers | 8-15 mins | Download only |

---

## 🔍 CSV Report Columns

The output DataFrame contains:

```
DOI                      - Paper DOI
Title                    - Paper title
Year                     - Publication year
PDF_Status               - Download status message
PDF_Path                 - Path to downloaded PDF
File_Size_MB             - PDF file size in MB
Supplementary_Status     - Supplementary finding status
Supplementary_Files      - List of supplement paths
```

---

## 🐛 Common Issues & Solutions

### Problem: "All sources exhausted"
- **Cause**: Paper not freely available, all APIs rate-limited or blocked
- **Solution**: Try manually, paper may require institutional access

### Problem: PDF shows as 0.0MB
- **Cause**: Downloaded file is HTML (fake PDF from captcha page)
- **Solution**: validation catches these; check error message in CSV

### Problem: Supplementary not found
- **Cause**: Either no supplements exist or they're embedded in PDF body
- **Solution**: Check PDF manually; system only finds external links

---

## 🚀 Advanced Usage

### Custom Download with Retry

```python
from download_paper import download_pdf
import time

max_retries = 3
for attempt in range(max_retries):
    status, path = download_pdf(
        doi="10.1038/nphys2439",
        output_dir="papers/",
        title="Paper",
        year=2012
    )
    if path:
        print(f"Success: {path}")
        break
    else:
        print(f"Attempt {attempt+1}/{max_retries} failed: {status}")
        time.sleep(5)  # Wait before retry
```

### Batch Processing with Error Handling

```python
from download_paper import process_doi_list
import pandas as pd

dois = ["10.1038/nphys2439", "invalid_doi", "10.1103/PhysRevE.101.033202"]

df = process_doi_list(dois, output_base_dir="papers/")

# Analyze results
successful = df[df['Download_Status'] == 'success']
failed = df[df['Download_Status'] == 'failed']

print(f"✓ Success: {len(successful)}")
print(f"✗ Failed: {len(failed)}")

# Retry failed papers
if len(failed) > 0:
    failed_dois = failed['DOI'].tolist()
    df_retry = process_doi_list(failed_dois, output_base_dir="papers/")
```

---

## 📚 Related Modules

- **db_sqlite.py**: Store downloaded paper metadata in database
- **fitch_citations.py**: Identify papers to download via citation mining
- **data_browser.py**: Web interface to manage downloads
- **download_server.py**: REST API for async downloads

---

**Last Updated**: 2026-04-22  
**Version**: 4.0  
**Status**: ✅ Production-ready (PDF to Markdown conversion removed)

