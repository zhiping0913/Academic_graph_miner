# Academic Graph Miner

Automated tooling for building, querying, and downloading from large academic
citation networks. Currently tracks **144,015 papers / 13,717,945 citations**
in a split-by-year SQLite layout (`database/index.db` + 156 per-year
`{year}.db` files).

```
DOI list ──▶ fitch_citations.py ──▶ database/ ──▶ similarity_search.py
                                        │                  │
                                        ├──▶ data_browser  :5001
                                        ├──▶ graph_server  :5000
                                        └──▶ download_server :5003
                                                           │
                                            download_paper.py ──▶ downloaded_papers/
```

---

## Quick start

```bash
source /home/zhiping/research-env/bin/activate    # or your own venv
pip install -r requirements.txt
playwright install chromium                       # only for Playwright downloads

# Mine a citation network from a DOI list
python fitch_citations.py --file doi_list.txt

# Rank the rest of the library by similarity to a seed
python similarity_search.py 10.1038/nphys2439 --top 20 --output doi,year,title --header

# Launch the browser UI at http://localhost:5001
python data_browser.py
```

Full walkthroughs:
- [docs/Quick_Start_AI.md](docs/Quick_Start_AI.md) — English, developer / agent focus
- [docs/Quick_Start_CN.md](docs/Quick_Start_CN.md) — 中文，研究者视角

---

## Top-level layout

| Path | Purpose |
|---|---|
| `db_sqlite.py` | persistence layer (split-by-year SQLite) — the only thing that touches `database/` |
| `similarity_search.py` | parallel Jaccard ranking + CLI |
| `fitch_citations.py` | BFS citation miner over Semantic Scholar + Crossref + OpenCitations |
| `download_paper.py` | 9-source PDF downloader + supplementary discovery |
| `graph_utils.py` | NetworkX subgraph + Jaccard helpers |
| `data_export.py` | JSON / CSV / TXT export |
| `data_browser.py` | Flask :5001 — paper browsing, search, similarity, citing / reference lookups |
| `graph_server.py` | Flask :5000 — interactive citation graph |
| `download_server.py` | Flask :5003 — async download queue |
| `main.py` | top-level CLI (`fitch` / `download` / `all`) |
| `database/` | SQLite files — never open directly, always go through `db_sqlite` |
| `docs/` | all module + architecture documentation |

---

## Documentation index

| Doc | Read when… |
|---|---|
| [docs/Quick_Start_AI.md](docs/Quick_Start_AI.md) | onboarding, English |
| [docs/Quick_Start_CN.md](docs/Quick_Start_CN.md) | 中文上手 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | overall system design + data flow |
| [docs/MODULE_DB_SQLITE.md](docs/MODULE_DB_SQLITE.md) | DB schema, helpers, migration |
| [docs/MODULE_DATA_BROWSER.md](docs/MODULE_DATA_BROWSER.md) | REST API |
| [docs/MODULE_FITCH_CITATIONS.md](docs/MODULE_FITCH_CITATIONS.md) | mining algorithm |
| [docs/MODULE_DOWNLOAD_PAPER.md](docs/MODULE_DOWNLOAD_PAPER.md) | downloader sources |
| [docs/MODULE_GRAPH_UTILS.md](docs/MODULE_GRAPH_UTILS.md) | Jaccard + subgraph |
| [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) | library version pins |
| [CLAUDE.md](CLAUDE.md) | project conventions for Claude Code |

---

## Migrating from the legacy single-file DB

If you still have the old `academic_knowledge_graph.db` at the repo root:

```bash
python db_sqlite.py migrate
```

Idempotent. The single file is left in place — delete it manually once you've
verified the split layout.
