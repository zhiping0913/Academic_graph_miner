# 📚 Dependencies Reference Guide

**Complete list of all Python libraries used in Academic Graph Miner**

---

## 📦 All Dependencies (17 Libraries)

### 🌐 Web Framework (1)

#### **Flask** (3.0.0)
```
Purpose: Create REST APIs
Used in: graph_server.py, data_browser.py, download_server.py
Why: Lightweight web framework for building HTTP APIs
Install: pip install flask
Docs: https://flask.palletsprojects.com/
```

**Example usage**:
```python
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/api/papers')
def get_papers():
    return jsonify({"papers": []})

app.run(port=5001)
```

---

### 📊 Data Processing (2)

#### **Pandas** (≥1.3.0)
```
Purpose: Data manipulation and analysis
Used in: download_paper.py, data_export.py
Why: Efficient DataFrame operations for CSV/data management
Install: pip install pandas
Docs: https://pandas.pydata.org/
```

**Example usage**:
```python
import pandas as pd

# Create report DataFrame
df = pd.DataFrame({
    'DOI': ['10.1038/nphys2439'],
    'Title': ['Paper Title'],
    'Year': [2012]
})
df.to_csv('report.csv', index=False)
```

#### **NumPy** (≥1.21.0)
```
Purpose: Numerical computing
Used in: graph_utils.py (for similarity calculations)
Why: Fast matrix/array operations
Install: pip install numpy
Docs: https://numpy.org/
```

---

### 🌐 HTTP & Web Scraping (3)

#### **Requests** (≥2.28.0)
```
Purpose: HTTP client for API calls
Used in: fitch_citations.py, download_paper.py
Why: Make HTTP requests to S2, Crossref, OpenAlex APIs
Install: pip install requests
Docs: https://requests.readthedocs.io/
```

**Example usage**:
```python
import requests

response = requests.get('https://api.semanticscholar.org/graph/v1/paper/DOI:10.1038/nphys2439')
data = response.json()
```

#### **BeautifulSoup4** (≥4.11.0)
```
Purpose: HTML/XML parsing
Used in: download_paper.py (supplementary detection)
Why: Extract data from web pages
Install: pip install beautifulsoup4
Docs: https://www.crummy.com/software/BeautifulSoup/
```

**Example usage**:
```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(html_content, 'html.parser')
links = soup.find_all('a')
```

#### **lxml** (≥4.9.0)
```
Purpose: XML/HTML processing (dependency of BeautifulSoup)
Used in: download_paper.py
Why: Fast XML parsing
Install: pip install lxml
```

---

### 🔗 Graph & Network (2)

#### **NetworkX** (≥3.0)
```
Purpose: Graph algorithms and network analysis
Used in: graph_utils.py, visualize_graph.py
Why: Build and analyze citation networks (BFS, shortest path, etc.)
Install: pip install networkx
Docs: https://networkx.org/
```

**Example usage**:
```python
import networkx as nx

G = nx.DiGraph()  # Directed graph
G.add_edge('paper1', 'paper2')  # Citation relationship
print(nx.shortest_path(G, 'paper1', 'paper2'))
```

#### **Pyvis** (≥0.3.0)
```
Purpose: Interactive network visualization
Used in: graph_server.py, visualize_graph.py
Why: Create interactive HTML graphs (Vis.js wrapper)
Install: pip install pyvis
Docs: https://pyvis.readthedocs.io/
```

**Example usage**:
```python
from pyvis.network import Network

net = Network(directed=True)
net.add_node('paper1', title='Title')
net.add_edge('paper1', 'paper2')
net.show('graph.html')
```

---

### 🤖 Browser Automation (1)

#### **Playwright** (≥1.40.0)
```
Purpose: Browser automation
Used in: download_paper.py
Why: Download PDFs from websites (handles JavaScript, anti-bot)
Install: pip install playwright
         playwright install chromium
Docs: https://playwright.dev/python/
```

**Example usage**:
```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto('https://example.com')
    pdf_buffer = page.pdf()
    browser.close()
```

⚠️ **Note**: Requires browser installation: `playwright install chromium`

---

### 📄 PDF Processing (2)

#### **pdfplumber** (≥0.10.0)
```
Purpose: PDF text extraction
Used in: download_paper.py
Why: Extract text from PDFs for supplementary detection
Install: pip install pdfplumber
Docs: https://github.com/jsvine/pdfplumber
```

**Example usage**:
```python
import pdfplumber

with pdfplumber.open('paper.pdf') as pdf:
    page = pdf.pages[0]
    text = page.extract_text()
    print('supplementary' in text.lower())
```

#### **MarkItDown** (≥0.0.1)
```
Purpose: PDF to Markdown conversion
Used in: download_paper.py
Why: Convert papers to Markdown for AI processing
Install: pip install markitdown
Docs: https://github.com/Microsoft/markitdown
```

**Example usage**:
```python
from markitdown import MarkItDown

md = MarkItDown()
result = md.convert('paper.pdf')
print(result.text_content)
```

**Alternative**: `pip install marker-pdf` (more advanced)

---

### 🔗 Academic APIs (3)

#### **unpywall** (≥0.1.0)
```
Purpose: Open access paper metadata
Used in: download_paper.py
Why: Find open access PDFs
Install: pip install unpywall
Docs: https://pypi.org/project/unpywall/
```

**Example usage**:
```python
from unpywall import Unpywall

doi = '10.1038/nphys2439'
response = Unpywall(doi)
print(response.is_open)  # Is it open access?
print(response.oa_locations)  # Where to download
```

#### **scidownl** (≥0.2.0)
```
Purpose: Sci-Hub wrapper
Used in: download_paper.py
Why: Download papers from Sci-Hub (academic repository)
Install: pip install scidownl
```

#### **doi2pdf** (≥0.0.4)
```
Purpose: Direct DOI to PDF conversion
Used in: download_paper.py
Why: Fast PDF download from DOI
Install: pip install doi2pdf
```

---

### 🛠️ Utilities (2)

#### **pathvalidate** (≥3.0.0)
```
Purpose: Filename validation and sanitization
Used in: download_paper.py
Why: Create valid filenames from paper titles
Install: pip install pathvalidate
Docs: https://pathvalidate.readthedocs.io/
```

**Example usage**:
```python
from pathvalidate import sanitize_filename

title = "Paper: A [Study] (2020)"
safe_name = sanitize_filename(title)
# Output: "Paper_A_Study_2020"
```

#### **python-dateutil** (≥2.8.0)
```
Purpose: Date/time utilities
Used in: db_sqlite.py, fitch_citations.py
Why: Parse and manipulate dates
Install: pip install python-dateutil
```

---

### ✅ Built-in (No Installation Needed)

These come with Python by default:

```python
import sqlite3         # Database
import json           # JSON handling
import csv            # CSV reading/writing
import urllib.parse   # URL utilities
import datetime       # Date/time
import pathlib        # Path handling
import typing         # Type hints
```

---

## 🔍 By Function Category

### For Mining Citations
- `requests` - API calls to S2, Crossref
- `json` - Parse responses
- `datetime` - Track update times

### For Downloading Papers
- `playwright` - Browser automation
- `requests` - HTTP downloads
- `unpywall` - Open access metadata
- `scidownl` - Sci-Hub interface
- `pathvalidate` - Safe filenames

### For PDF Processing
- `pdfplumber` - Text extraction
- `markitdown` - PDF to Markdown
- `beautifulsoup4` - HTML parsing

### For Graph Analysis
- `networkx` - Graph algorithms
- `pyvis` - Visualization
- `numpy` - Numerical operations

### For Web APIs
- `flask` - Create endpoints
- `pandas` - Data handling
- `json` - Response formatting

### For Data Export
- `pandas` - DataFrame operations
- `csv` - CSV writing
- `json` - JSON serialization

---

## 📊 Dependency Sizes & Download Time

| Package | Size | Time |
|---------|------|------|
| playwright | 50MB | 30s |
| numpy | 30MB | 15s |
| pandas | 15MB | 10s |
| Other (15+) | 25MB | 20s |
| **Total** | **~120MB** | **~2 min** |

---

## 🚀 Installation Methods

### Method 1: From requirements.txt (Recommended)
```bash
pip install -r requirements.txt
```

### Method 2: Individual packages
```bash
pip install flask pandas numpy networkx requests beautifulsoup4 \
    playwright pdfplumber markitdown unpywall pathvalidate
```

### Method 3: With setup.py
```bash
pip install -e .
```

### Method 4: Development mode (includes testing tools)
```bash
pip install -r requirements.txt pytest pytest-cov
```

---

## ⚙️ Compatibility

| Python | Supported |
|--------|-----------|
| 3.10 | ✅ Yes |
| 3.11 | ✅ Yes |
| 3.12 | ✅ Yes |
| 3.9 | ❌ No |
| 3.8 | ❌ No |

---

## 🔄 Version Management

### Pin to specific versions
```bash
# Instead of: pip install flask
# Use:
pip install flask==3.0.0
```

### Allow patch updates
```bash
pip install flask>=3.0.0,<4.0.0
```

### Update all dependencies
```bash
pip install --upgrade -r requirements.txt
```

---

## 📝 Notes

- **Optional**: `marker-pdf` (alternative PDF converter)
- **Optional**: `pytest` (for running tests)
- **Required**: Python 3.10 or higher
- **System**: Chromium browser (via Playwright)

---

**Status**: ✅ Complete  
**Last Updated**: 2026-04-21  
**Version**: 4.0
