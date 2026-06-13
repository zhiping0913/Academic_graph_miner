# 快速入门（中文）

**适用人群**：使用 Academic Graph Miner 的研究人员。
**前置要求**：Python 3.10+、命令行基础。
**所有详细模块文档**：见 `docs/MODULE_*.md`。

---

## 1. 安装

```bash
# 推荐使用本机已有的研究环境
source /home/zhiping/research-env/bin/activate

# 或者新建虚拟环境
python -m venv venv && source venv/bin/activate

pip install -r requirements.txt
playwright install chromium      # Playwright 下载源用得到，可后装
```

验证：

```bash
python -c "import flask, networkx, pandas, sqlite3; print('ok')"
```

---

## 2. 系统总览

```
┌─────────────────────────────────────────────────────────────┐
│                  Academic Graph Miner                       │
├─────────────────────────────────────────────────────────────┤
│  1. 引用挖掘   fitch_citations.py    → BFS 抓引用关系       │
│  2. 数据库     db_sqlite.py          → 分年份 SQLite        │
│  3. 相似度排序 similarity_search.py  → 并行 Jaccard + CLI   │
│  4. PDF 下载   download_paper.py     → 9 个来源逐个尝试     │
│  5. 网页服务   data_browser  :5001                          │
│                graph_server  :5000                          │
│                download_server :5003                        │
└─────────────────────────────────────────────────────────────┘
```

当前规模：**144,015 篇论文 / 13,717,945 条引用**，分布在 156 个年份数据库中。

---

## 3. 数据库（按年份拆分）

老的 `academic_knowledge_graph.db` 已经被拆成了 `database/` 目录：

```
database/
├── index.db        所有论文的元数据（DOI、年份、标题、期刊、作者）
├── {year}.db       该年份论文对应的引用关系（每年一个文件）
└── unknown.db      年份缺失的论文
```

**所有数据库访问都必须经过 `db_sqlite.py`**，不要直接打开 `.db` 文件。

### 常用函数

```python
from db_sqlite import (
    get_paper,                    # 按 DOI 取一篇论文（含引用）
    upsert_paper,                 # 插入或更新一篇论文
    load_db_year_range,           # 按年份区间批量加载
    list_papers_paginated,        # 分页列出元数据（用于 UI）
    search_metadata,              # 标题 / DOI 模糊搜索
    get_metadata,                 # 单篇元数据
    get_metadata_batch,           # 批量元数据
    get_citation_counts,          # 批量引用计数
    find_citing_dois,             # 反向查询：谁引用了 X
)
```

### 从旧的单文件数据库迁移

如果项目根目录还存在 `academic_knowledge_graph.db`：

```bash
python db_sqlite.py migrate
```

幂等，可以重复运行。

---

## 4. 准备种子论文

新建 `seeds.txt`，每行一个 DOI：

```
10.1038/nphys2439
10.1103/PhysRevE.101.033202
10.1088/1367-2630/15/1/015025
```

DOI 可以从 arXiv、Semantic Scholar、Crossref 获取。

---

## 5. 引用网络挖掘 `fitch_citations.py`

从种子出发，逐层抓取 citation（被引：谁引用了它）和 reference（参考文献：它引用了谁）列表，用 Jaccard 相似度筛选下一轮的邻居。

```bash
# 从文件读 DOI
python fitch_citations.py --file seeds.txt

# 直接传 DOI
python fitch_citations.py --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

# 强制刷新本地缓存
python fitch_citations.py --file seeds.txt --force-update
```

可在 `fitch_citations.py` 文件头部调参：

| 常量 | 默认 | 含义 |
|---|---|---|
| `THRESHOLD` | 0.1 | Jaccard 阈值，低于则跳过 |
| `MAX_DEPTH` | 2 | 最大搜索深度 |
| `UPDATE_DAYS` | 1000 | 本地缓存有效期（天） |
| `REQUEST_DELAY` | 1.2 | API 请求间隔（秒），勿降低 |

抓取的数据会写入 `database/`。

---

## 6. 相似度排序 `similarity_search.py`

给定一篇种子论文，并行扫描所有年份数据库，按 Jaccard 相似度返回最相关的若干篇。

### 命令行

```bash
# 默认：只输出 DOI，每行一个，共 50 条
python similarity_search.py 10.1016/j.cnsns.2026.109994

# 指定年份范围、输出多列、显示表头
python similarity_search.py 10.1016/j.cnsns.2026.109994 \
    --year-min 2020 --year-max 2026 \
    --top 30 \
    --output doi,year,title --header

# 只输出标题
python similarity_search.py 10.1016/j.cnsns.2026.109994 --output title
```

`--output` 接受的字段：`doi`、`year`、`title`、`journal`、`similarity`（逗号分隔，顺序保留）。输出格式为 TSV。

| 参数 | 默认 | 说明 |
|---|---|---|
| `--year-min` / `--year-max` | 不限 | 候选论文年份区间（含端点） |
| `--top` | 50 | 返回条数 |
| `--direction` | `both` | `citation` / `reference` / `both` |
| `--workers` | min(cpu, 8) | 并行进程数 |
| `--include-unknown` | 否 | 是否同时扫 `unknown.db` |

### 在 Python 里调用

```python
from similarity_search import find_similar

hits = find_similar(
    seed_doi="10.1016/j.cnsns.2026.109994",
    year_min=2020, year_max=2026,
    top_n=20, direction="both",
)
for h in hits:
    print(f"{h['similarity']:.3f}  {h['year']}  {h['doi']}  {h['title']}")
```

在本机上对一篇有 30 条邻居的 2026 年种子做全库扫描约 **3 秒**。

---

## 7. 网页界面

每个服务都是独立的 Flask 应用，可以分别启动：

| 脚本 | 端口 | 功能 |
|---|---|---|
| `python data_browser.py` | 5001 | 论文浏览、搜索、相似度排序、引用 / 被引查询、导出 |
| `python graph_server.py` | 5000 | 引用网络可视化 |
| `python download_server.py` | 5003 | 异步下载队列 |

### data_browser 几个细节

- 首次打开默认只加载**当前年**（实测 ~20 ms），翻页是 SQL 分页，不再一次性加载全库。
- 在「参考论文」里填一个 DOI 后，会自动调用 `similarity_search.find_similar` 做全库相似度排序（~3 s）。
- 自动补全搜索框走 SQL `LIKE`，毫秒级。
- 「Citation」「Reference」按钮分别查的是 citation（被引）/ reference（参考文献）列表。

---

## 8. PDF 批量下载 `download_paper.py`

依次尝试 9 个下载源，第一个成功即返回；下载后会验证 PDF 是否有效（魔数 + 结构），并在 PDF 文本里搜索补充材料。

```bash
# 从文件
python download_paper.py --file my_dois.txt --output downloaded_papers/

# 直接传 DOI
python download_paper.py --doi 10.1038/nphys2439

# 用 main.py 也可以
python main.py download --file my_dois.txt --output downloaded_papers/
```

下载源优先级：
1. Playwright DOI 页面（最可靠）
2. doi2pdf
3. OpenAlex API
4. Crossref 链接
5. Unpywall API
6. arXiv
7. Scidownl
8. Sci-Hub 直连
9. Playwright stealth

成功率因出版商防护而异，预计 ~70–80%。

输出目录结构：

```
downloaded_papers/
├── 2012/
│   └── 2012--coherent-synchrotron.pdf
├── 2024/
│   └── 2024--xxx.pdf
└── download_report.csv         # 每篇论文的状态、路径、补充材料
```

---

## 9. 一站式流程（顶层 CLI）

```bash
python main.py fitch    --file seeds.txt
python main.py download --file seeds.txt --output downloaded_papers/
python main.py all      --file seeds.txt --output downloaded_papers/
```

`all` = 先 fitch 再 download。

---

## 10. 完整示例：HHG 研究

```bash
# 1. 种子论文
echo "10.1038/nphys2439"       > seeds.txt
echo "10.1103/PhysRevE.101.033202" >> seeds.txt

# 2. 激活环境
source /home/zhiping/research-env/bin/activate

# 3. 抓取引用网络（约 1–2 小时，取决于种子规模）
python fitch_citations.py --file seeds.txt

# 4. 对每篇种子做一次全库相似度排序，导出 top-50 DOI
for seed in $(cat seeds.txt); do
    python similarity_search.py "$seed" --year-min 2015 --top 50 \
        > "ranked_${seed//\//_}.txt"
done

# 5. 启动浏览器界面挑选
python data_browser.py &     # http://localhost:5001
# 在 UI 里勾选 → 导出 selected.txt

# 6. 批量下载 PDF
python download_paper.py --file selected.txt --output downloaded_papers/

# 7. 看报告
cat downloaded_papers/download_report.csv
```

---

## 11. 常见问题

**Q1：为什么 `load_db()` 这么慢？**
A：现在全库有 144K 篇论文，`load_db()` 会读所有 156 个年份数据库（几分钟级）。日常请使用：
- `load_db_year_range(min, max)` — 限定年份
- `get_paper(doi)` — 只取一篇
- `list_papers_paginated(...)` — UI 分页

**Q2：相似度阈值怎么选？**

| Jaccard 范围 | 含义 | 适用 |
|---|---|---|
| 0.05–0.10 | 宽松 | 探索新领域 |
| 0.10–0.20 | 中等（fitch 默认） | 一般用途 |
| 0.20–0.40 | 严格 | 找密切相关 |
| > 0.40 | 极严 | 近重复检测 |

**Q3：有些论文下载失败怎么办？**
A：出版商防护无法 100% 绕过。可以：
- 通过机构 VPN 访问后重试
- 查 ResearchGate / arXiv 预印本版本
- 直接给作者发邮件

**Q4：API 报速率限制？**
A：调高 `fitch_citations.py` 里的 `REQUEST_DELAY`（默认 1.2 秒）。

**Q5：怎么反向查「谁引用了某篇论文」？**

```python
from db_sqlite import find_citing_dois
citers = find_citing_dois("10.1038/nphys2439")  # 默认 direction='reference'
```

或者在 data_browser 网页里点 "Citing"。

**Q6：数据库锁了怎么办？**
A：已启用 SQLite WAL 模式，多读单写。如果偶发 "database is locked"，重试即可；持续锁定通常是有进程在长事务里卡住，`fuser database/*.db` 看一下。

---

## 12. 文档索引

| 我想… | 看哪个 |
|---|---|
| 完整系统架构 | `docs/ARCHITECTURE.md` |
| 数据库 schema + 接口 | `docs/MODULE_DB_SQLITE.md` |
| 引用挖掘算法 | `docs/MODULE_FITCH_CITATIONS.md` |
| 下载 9 个源的细节 | `docs/MODULE_DOWNLOAD_PAPER.md` |
| REST API | `docs/MODULE_DATA_BROWSER.md` |
| 图算法 / 相似度 | `docs/MODULE_GRAPH_UTILS.md` |
| 依赖库版本 | `docs/DEPENDENCIES.md` |
| 项目惯例（给 AI） | 项目根 `CLAUDE.md` |
| 英文开发者文档 | `docs/Quick_Start_AI.md` |

---

## 13. 相关资源

- arXiv: <https://arxiv.org>
- Semantic Scholar: <https://semanticscholar.org>
- Crossref: <https://www.crossref.org>
- OpenAlex: <https://openalex.org>
- Unpaywall: <https://unpaywall.org>
