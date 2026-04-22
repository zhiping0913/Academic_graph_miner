# 📥 Installation Guide - Academic Graph Miner

**Version**: 4.0  
**Last Updated**: 2026-04-21

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Installation Steps

```bash
# 1. Clone the repository
git clone https://github.com/zhiping0913/Academic_graph_miner.git
cd Academic_graph_miner

# 2. Create a virtual environment (recommended)
python -m venv venv

# 3. Activate the virtual environment
# On macOS/Linux:
source venv/bin/activate

# On Windows:
venv\Scripts\activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Install browser for Playwright
playwright install chromium

# 6. Verify installation
python -c "import flask, pandas, networkx; print('✓ Installation successful!')"
```

---

## 📦 Dependencies Breakdown

### Core Libraries (Required)

| Library | Version | Purpose |
|---------|---------|---------|
| **Flask** | 3.0.0 | Web framework for REST APIs |
| **Pandas** | ≥1.3.0 | Data manipulation and analysis |
| **NumPy** | ≥1.21.0 | Numerical computing |
| **Requests** | ≥2.28.0 | HTTP client for APIs |
| **BeautifulSoup4** | ≥4.11.0 | HTML/XML parsing |
| **NetworkX** | ≥3.0 | Graph algorithms and analysis |
| **Playwright** | ≥1.40.0 | Browser automation |
| **pdfplumber** | ≥0.10.0 | PDF text extraction |

### API & Download Libraries

| Library | Version | Purpose |
|---------|---------|---------|
| **unpywall** | ≥0.1.0 | Open access paper metadata |
| **scidownl** | ≥0.2.0 | Sci-Hub wrapper |
| **doi2pdf** | ≥0.0.4 | DOI to PDF conversion |

### Processing & Visualization

| Library | Version | Purpose |
|---------|---------|---------|
| **pyvis** | ≥0.3.0 | Network graph visualization |
| **MarkItDown** | ≥0.0.1 | PDF to Markdown conversion |
| **marker-pdf** | ≥0.3.0 | Alternative PDF processor (optional) |

### Utilities

| Library | Version | Purpose |
|---------|---------|---------|
| **pathvalidate** | ≥3.0.0 | Filename validation |
| **python-dateutil** | ≥2.8.0 | Date utilities |
| **lxml** | ≥4.9.0 | XML processing |

### Built-in (No Installation Needed)

- **sqlite3** - Database (included in Python)
- **json** - JSON handling
- **csv** - CSV processing
- **urllib** - URL handling
- **datetime** - Date/time utilities

---

## 🔧 Detailed Installation

### 1. System Requirements

**Minimum:**
- CPU: 2 cores
- RAM: 2GB
- Disk: 5GB (for dependencies + data)

**Recommended:**
- CPU: 4+ cores
- RAM: 8GB+
- Disk: 20GB+ (for paper downloads)

---

### 2. Python Version Check

```bash
python --version
# Should output: Python 3.10.x or higher
```

If you have multiple Python versions:
```bash
python3.10 --version
# Use python3.10 instead of python
```

---

### 3. Create Virtual Environment

**Why virtual environment?**
- Isolates project dependencies
- Prevents version conflicts
- Easy to remove/recreate

```bash
# Create
python -m venv venv

# Activate
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Verify (should see (venv) in prompt)
which python  # or: where python (Windows)
```

---

### 4. Install Dependencies

**Option A: From requirements.txt (Recommended)**
```bash
pip install -r requirements.txt
```

**Option B: Install manually**
```bash
# Core
pip install flask pandas numpy

# Web scraping
pip install requests beautifulsoup4 lxml

# APIs
pip install unpywall scidownl doi2pdf playwright

# Graph analysis
pip install networkx pyvis

# PDF processing
pip install pdfplumber markitdown

# Utilities
pip install pathvalidate python-dateutil

# Testing (optional)
pip install pytest pytest-cov
```

**Option C: Upgrade to latest versions**
```bash
pip install --upgrade -r requirements.txt
```

---

### 5. Browser Setup for Playwright

Playwright needs a browser to run automation:

```bash
# Install Chromium (recommended)
playwright install chromium

# Or install all browsers
playwright install

# Verify
python -c "from playwright.sync_api import sync_playwright; print('✓ Playwright ready')"
```

---

### 6. Verify Installation

```bash
# Test imports
python << 'EOF'
import flask
import pandas
import networkx
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import pdfplumber

print("✓ All imports successful!")
print(f"Flask: {flask.__version__}")
print(f"Pandas: {pandas.__version__}")
print(f"NetworkX: {networkx.__version__}")
