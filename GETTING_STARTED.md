# 🚀 Getting Started - 5 Minutes Installation

**For people who want to try Academic Graph Miner quickly**

---

## ⚡ Super Quick Start (Copy & Paste)

```bash
# 1. Clone repository
git clone https://github.com/zhiping0913/Academic_graph_miner.git
cd Academic_graph_miner

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies (30 seconds)
pip install -r requirements.txt

# 4. Install browser for Playwright
playwright install chromium

# Done! ✅
```

**Total time: ~2 minutes** (depends on internet speed)

---

## ✅ Verify Installation Works

```bash
python -c "import flask, pandas, networkx; print('✓ Ready to use!')"
```

If you see "✓ Ready to use!" - you're all set!

---

## 🎯 What You Just Installed

| What | Why |
|------|-----|
| **Flask** | Web API servers |
| **Pandas & NumPy** | Data processing |
| **NetworkX** | Graph algorithms |
| **Playwright** | Browser automation (PDF downloads) |
| **Beautiful Soup** | Web scraping |
| **pdfplumber** | PDF text extraction |
| **And more...** | 15+ libraries total |

---

## 🏃 Try It Out!

### Option 1: Test the Database API
```bash
python data_browser.py
# Then visit: http://localhost:5001/api/papers?page=1
```

### Option 2: Run Unit Tests
```bash
python test_download.py
```

### Option 3: Launch Interactive Graph
```bash
python graph_server.py
# Then visit: http://localhost:5000
```

---

## 🐛 Troubleshooting (2 Common Issues)

### Issue: "No module named 'flask'"
**Solution**: Make sure virtual environment is active
```bash
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows
```

### Issue: "Playwright needs chromium"
**Solution**: Install browser
```bash
playwright install chromium
```

---

## 📚 Next Steps

1. **Read documentation**: See [README.md](./README.md)
2. **Understand architecture**: See [ARCHITECTURE.md](./ARCHITECTURE.md)
3. **Learn modules**: See [CLAUDE.md](./CLAUDE.md)
4. **Try examples**: See code in `test_*.py` files

---

## 📋 Full Requirements Summary

**Python 3.10+** is required.

### Essential Libraries (All Included)
- Web: Flask
- Data: Pandas, NumPy
- Network: NetworkX
- Scraping: Requests, BeautifulSoup4
- Download: Playwright, scidownl, unpywall
- PDF: pdfplumber, MarkItDown
- Utilities: pathvalidate, python-dateutil

See [INSTALLATION.md](./INSTALLATION.md) for detailed information.

---

## 🎓 Beginner Tips

**Q: What is a virtual environment?**  
A: An isolated Python environment for this project. Prevents library conflicts.

**Q: Why install Chromium?**  
A: Playwright uses it to automate browser actions (downloading PDFs from websites).

**Q: Can I skip virtual environment?**  
A: Not recommended. It's a best practice. Takes 10 seconds to create.

**Q: What if installation fails?**  
A: Check [INSTALLATION.md](./INSTALLATION.md) troubleshooting section.

---

## ✨ Success Checklist

- [ ] Python 3.10+ installed
- [ ] Virtual environment created and activated
- [ ] requirements.txt installed
- [ ] Playwright browser installed
- [ ] Verification command ran successfully
- [ ] You can see "✓ Ready to use!"

If all checked ✅ - You're ready to use Academic Graph Miner!

---

**Time to install: ~2 minutes**  
**Difficulty: ⭐ Easy**  
**Support**: See [INSTALLATION.md](./INSTALLATION.md)
