# 🏗️ Academic Graph Miner - 系统架构指南

**完成日期**: 2026-04-21  
**版本**: 4.0  
**状态**: 生产就绪

---

## 📋 目录

1. [系统概览](#系统概览)
2. [核心模块](#核心模块)
3. [数据流](#数据流)
4. [API文档](#api文档)
5. [函数参考](#函数参考)
6. [快速开始](#快速开始)
7. [扩展开发](#扩展开发)

---

## 🎯 系统概览

### 项目目标

从学术DOI列表出发，自动化：
- 📊 构建引用网络图谱（图谱挖掘）
- 📥 批量下载论文PDF及补充文件
- 🔗 计算论文间相似度（Jaccard系数）
- 🎨 可视化知识图谱（交互式Web界面）
- 💾 导出/查询学术数据（JSON/CSV/TXT）

### 技术栈

| 层 | 技术 | 用途 |
|----|------|------|
| **后端** | Python 3.10+ | 核心逻辑 |
| **API** | Flask | Web服务 |
| **数据库** | SQLite3 | 持久化存储 |
| **图论** | NetworkX | 图论计算 |
| **可视化** | Vis.js | 交互图谱 |
| **下载** | Playwright, Requests | 论文获取 |
| **处理** | BeautifulSoup, pdfplumber | 数据提取 |

### 系统规模

- **数据库**: 144,015篇论文，13,717,945条引用关系（按年份拆分到 156 个 SQLite 文件）
- **下载源**: 9种并行备选
- **API集成**: Semantic Scholar, Crossref, OpenAlex, Unpywall, OpenCitations
- **Web界面**: 3个Flask服务 + 3个HTML前端
- **相似度搜索**: `similarity_search.py` 多进程并行 Jaccard，命令行 + 库调用

---

## 🔧 核心模块

### 1. 数据库层 - `db_sqlite.py`

**职责**: SQLite数据操作和持久化（按年份拆分的多文件布局）

**存储布局** (v5)：
```
database/
├── index.db          所有论文的元数据（papers 表）
├── {year}.db         该年份论文对应的引用关系（每年一个文件）
└── unknown.db        年份缺失的论文
```

**数据模型**:
```
index.db / papers 表:
  id           INTEGER PRIMARY KEY
  doi          TEXT UNIQUE
  title        TEXT
  year         INTEGER
  journal      TEXT
  authors      TEXT (JSON array)
  last_updated TEXT

{year}.db / citations 表:
  source_doi   TEXT
  target_doi   TEXT
  direction    TEXT ('forward' = Citation list / 被引; 'backward' = Reference list / 参考文献)
                    -- 公开 API 用 citation/reference；磁盘列值保留旧名，映射发生在 db_sqlite.py
  coefficient  REAL (Jaccard or NULL)
  PRIMARY KEY: (source_doi, target_doi, direction)
  索引: idx_cit_src(source_doi, direction)
       idx_cit_tgt(target_doi, direction)
```

跨文件的「外键」是 DOI 字符串本身——不存在跨文件的整数 ID 引用，路由由 `_year_key(year)` 完成。

**关键函数**:
```python
init_db()                       # 初始化 index.db schema（年份 DB 延迟创建）
get_paper(doi)                  # 单篇论文（元数据 + 引用）
upsert_paper(paper)             # 插入/更新；自动处理年份迁移
load_db()                       # 全库加载（昂贵，慎用）
load_db_year_range(min, max)    # 按年份区间批量加载
list_papers_paginated(...)      # SQL LIMIT/OFFSET 分页列表（UI 用）
get_metadata(doi)               # 仅元数据查询
get_metadata_batch(dois)        # 批量元数据
search_metadata(query)          # 标题 / DOI 模糊搜索
get_citation_counts(dois)       # 批量 citation/reference 计数
find_citing_dois(target_doi)    # 反向查询：谁引用了 X
list_available_years()          # 磁盘上的年份 DB 列表
migrate_from_legacy(path)       # 从单文件迁移
is_expired(ts, days)            # 检查缓存有效期
```

**返回格式** - JSON格式的论文对象:
```python
{
    "doi": "10.xxxxx",
    "metadata": {
        "title": "Paper Title",
        "year": 2021,
        "journal": "Nature Physics",
        "authors": ["Author1", "Author2"]
    },
    "citation":  ["10.aaaa", "10.bbbb"],         # 引用该论文的 DOI（被引）
    "reference": ["10.cccc"],                    # 该论文引用的 DOI（参考文献）
    "classified_citation": [                     # 有 Jaccard 系数的
        {"doi": "10.aaaa", "coefficient": 0.25}
    ],
    "classified_reference": [
        {"doi": "10.cccc", "coefficient": 0.15}
    ],
    "last_updated": "2026-04-21"
}
```

### 2. 图谱挖掘 - `fitch_citations.py`

**职责**: 从种子论文递归构建引用网络

**核心算法** (BFS + Jaccard过滤):
```
1. 初始化队列 ← seed DOIs
2. 对每个论文：
   ├─ 调用S2/Crossref API获取元数据
   ├─ 提取 citation（被引）和 reference（参考文献）列表
   ├─ 计算与队列中论文的Jaccard相似度
   ├─ 若相似度 >= THRESHOLD → 加入队列进行深层挖掘
   └─ 保存到SQLite
3. 直到深度达到 MAX_DEPTH
```

**关键参数**:
```python
THRESHOLD = 0.1           # Jaccard相似度阈值（>0.1才追踪）
MAX_DEPTH = 3             # 最大搜索深度（防止图爆炸）
UPDATE_DAYS = 1000        # 缓存有效期
REQUEST_DELAY = 1.2       # API请求间隔（秒）
```

**关键函数**:
```python
run_miner(seeds: List[str]) -> None
    # 主挖掘循环
    
fetch_combined_data(doi: str) -> Optional[Dict]
    # 融合S2和Crossref API获取完整元数据
    # 返回: {"title": ..., "citations": [...], "references": [...]}
```

### 3. 论文下载 - `download_paper.py`

**职责**: 多源论文下载和补充文件识别

**下载优先级** (从快到慢):
```
1. Playwright DOI页面    ✨ 最优先（绕过反爬虫）
2. doi2pdf               快速直接
3. OpenAlex API          开放获取链接
4. Crossref API          出版商信息
5. Unpywall API          OA数据库
6. arXiv                 预印本
7. Scidownl              Sci-Hub脚本
8. Sci-Hub直接           Sci-Hub镜像
9. Playwright反爬虫      最后手段
```

**特殊处理**:
```
✅ PDF验证: 检查文件大小、魔法数字、结构
✅ HTML检测: 过滤验证页面、404错误
✅ Markdown生成: PDF→MD（MarkItDown优先）
✅ 补充文件: 识别supplementary并下载
✅ 缓存检查: 避免重复下载
```

**关键函数**:
```python
process_doi_list(dois: List[str], output_dir: str) -> pd.DataFrame
    # 批量处理，返回下载报告

download_pdf(doi, output_dir, title, year) -> Tuple[str, str]
    # 返回: (状态信息, PDF路径)

download_supplementary_materials(doi, output_dir, title, year, pdf_path)
    # 查找并下载补充文件
    
check_paper_already_exists(output_dir, year, title, doi) -> Optional[str]
    # 检查文件是否已下载，若缺MD则自动生成

pdf_to_markdown(pdf_path, md_path) -> bool
    # 使用MarkItDown或Marker转换
```

**文件命名规则**:
```
{year}--{sanitized_title}.pdf
{year}--{sanitized_title}.md
{year}--{sanitized_title}--supplementary.pdf
```

### 4. 图论工具 - `graph_utils.py`

**职责**: 图论计算和相似度分析

**关键函数**:
```python
calculate_jaccard(list_a: List, list_b: List) -> float
    # 计算Jaccard相似度: |A∩B| / |A∪B|
    # 范围: 0.0 - 1.0

extract_subgraph(db, seeds, max_citation_dist, max_reference_dist) -> nx.DiGraph
    # 提取种子论文周围的子图
    # 返回: NetworkX有向图，含节点属性和边权重

compute_jaccard_to_seeds(db, node_doi, seeds) -> List[Dict]
    # 计算单个论文到多个种子的相似度
    # 返回: [{"doi": ..., "jaccard": 0.25}, ...]
```

### 5. Web服务层

#### 5.1 图谱服务 - `graph_server.py` (端口5000)

**API端点**:
```
POST /api/graph
  请求:
    {
      "seed_dois": ["10.1038/nphys2439", ...],
      "max_citation_dist": 1,
      "max_reference_dist": 1,
      "include_metadata": true
    }
  响应:
    {
      "nodes": [
        {"id": "10.xxxxx", "label": "Title", "title": "Author1, 2021", ...}
      ],
      "edges": [
        {"from": "10.xxxxx", "to": "10.yyyyy", "weight": 0.25}
      ],
      "stats": {"nodes": 45, "edges": 128}
    }

POST /api/save-graph
  请求: {"html_content": "..."}
  功能: 保存当前图为HTML文件

POST /api/fetch-paper
  请求: {"doi": "10.xxxxx"}
  功能: 动态获取论文并更新数据库
```

#### 5.2 数据浏览 - `data_browser.py` (端口5001)

**API端点**（所有端点都直接走 `db_sqlite` 的接口，不再依赖 in-memory 全库缓存）：
```
GET /api/papers
  参数:
    - page, per_page    (SQL LIMIT/OFFSET 分页)
    - search            (DOI / 标题模糊)
    - year_min, year_max (默认当年, e.g. 2026)
    - ref_doi           (有值则走 similarity_search.find_similar 全库 Jaccard)
    - similarity_min, sort_by
  功能: 默认只列当年论文（~20ms），有 ref_doi 时返回全库相似度排序（~3s）

GET /api/citing-papers?doi=…
  反向查询：谁引用了 doi（用 find_citing_dois 并行扫所有年份 DB，~80ms）

GET /api/reference-papers?doi=…
  目标论文自身的 reference（参考文献）列表 + 批量元数据

GET /api/search-papers?search=…
  自动补全（SQL LIKE，~100ms）

POST /api/fetch-paper
  实时通过 Semantic Scholar / Crossref 拉取缺失论文并 upsert

POST /api/export
  导出 JSON / CSV / TXT
```

#### 5.3 下载管理 - `download_server.py` (端口5003)

**API端点**:
```
POST /api/download-start
  请求:
    {
      "dois": ["10.xxxxx", ...],
      "output_dir": "papers/"
    }
  返回: {"task_id": "abc123"}
  功能: 启动后台下载

GET /api/download-progress/<task_id>
  返回:
    {
      "status": "downloading",
      "progress": 45,
      "current": {"doi": "...", "status": "downloading"},
      "stats": {"total": 100, "success": 45, "failed": 0}
    }

GET /api/download-report/<task_id>
  返回: CSV格式的下载报告
```

### 6. 数据导出 - `data_export.py`

**支持格式**:
- **JSON**: 完整的论文对象（含所有引用关系）
- **CSV**: 表格形式（DOI, 标题, 年份, 作者, citations 列表, references 列表）
- **TXT**: 纯文本列表或详细格式

**关键函数**:
```python
export_to_json(dois, output_file) -> None
    # 导出完整JSON结构

export_to_csv(dois, output_file) -> None
    # 导出CSV表格（含引用列表）

export_to_txt(dois, output_file, key_list=None) -> None
    # key_list: ['doi'] (默认) 或 ['doi', 'title', 'year', ...]
    
migrate(json_file=None, direction='json_to_sqlite') -> None
    # JSON ↔ SQLite 迁移
```

---

## 📊 数据流

### 完整工作流

```
输入: DOI列表
   ↓
[步骤1] 图谱挖掘 (fitch_citations.py)
   ├─ 调用S2/Crossref API
   ├─ 计算Jaccard相似度
   ├─ 递归构建网络
   └─ 存储→SQLite
   ↓
[步骤2] 论文下载 (download_paper.py)
   ├─ 检查缓存
   ├─ 多源并行下载PDF
   ├─ 提取Markdown
   └─ 下载补充文件
   ↓
[步骤3] 数据访问
   ├─ 交互图谱 (graph_server.py)
   ├─ 数据浏览 (data_browser.py)
   ├─ 下载管理 (download_server.py)
   └─ 数据导出 (data_export.py)
   ↓
输出: JSON/CSV/可视化图谱
```

### 数据存储

```
SQLite Databases (database/)
├── index.db
│   └── papers: 144,015 条论文记录
├── {year}.db × 156
│   └── citations: 共 13,717,945 条引用关系
└── 增量更新机制
    ├─ 新论文自动插入（按年份路由到对应 {year}.db）
    ├─ 年份变更时自动迁移 citations 到新文件
    └─ 缓存更新检查 + 去重

磁盘文件
├── {year}--{title}.pdf (原始论文)
├── {year}--{title}.md (Markdown转换)
├── {year}--{title}--supplementary.pdf (补充文件)
└── download_report.csv (下载报告)
```

---

## 🔌 API文档

### 通用约定

**响应格式**:
```json
{
  "success": true,
  "data": {...},
  "error": null,
  "timestamp": "2026-04-21T12:34:56"
}
```

**错误处理**:
```json
{
  "success": false,
  "data": null,
  "error": "Error message",
  "error_code": 400
}
```

### 认证

无需认证（本地服务）

### 限流

- API调用: 无限制
- 外部API: 1.2秒/请求（防止被限制）

---

## 📚 函数参考

### 数据库操作

```python
from db_sqlite import load_db, get_paper, upsert_paper

# 加载整个数据库
db = load_db()  # Dict[str, paper_data]

# 查询单篇论文
paper = get_paper("10.1038/nphys2439")
if paper:
    print(paper["metadata"]["title"])
    print(f"被引数 (Citation): {len(paper['citation'])}")
    print(f"有系数被引: {len(paper['classified_citation'])}")

# 更新论文
new_paper = {
    "doi": "10.xxxxx",
    "metadata": {"title": "...", "year": 2021, ...},
    "citation": [...],
    "reference": [...]
}
upsert_paper(new_paper)
```

### 图论计算

```python
from graph_utils import calculate_jaccard, extract_subgraph

# 计算相似度
similarity = calculate_jaccard(
    ["ref1", "ref2", "ref3"],
    ["ref2", "ref3", "ref4"]
)  # 返回 0.5

# 提取子图
G = extract_subgraph(
    db=db,
    seed_dois=["10.1038/nphys2439"],
    max_citation_dist=1,
    max_reference_dist=1
)
# 返回 NetworkX DiGraph
print(f"节点: {G.number_of_nodes()}")
print(f"边: {G.number_of_edges()}")
```

### 论文下载

```python
from download_paper import process_doi_list, download_pdf

# 批量下载
report = process_doi_list(
    dois=["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"],
    output_base_dir="papers/"
)
# 返回 DataFrame，包含下载状态、文件大小等

# 单篇下载
status, pdf_path = download_pdf(
    doi="10.1038/nphys2439",
    output_dir="papers/",
    title="My Paper",
    year=2012
)
print(f"状态: {status}")
print(f"文件: {pdf_path}")
```

### 数据导出

```python
from data_export import export_to_json, export_to_csv, export_to_txt

# 导出JSON
export_to_json(
    dois=["10.1038/nphys2439"],
    output_file="export.json"
)

# 导出CSV
export_to_csv(
    dois=["10.1038/nphys2439"],
    output_file="export.csv"
)

# 导出纯DOI列表
export_to_txt(
    dois=["10.1038/nphys2439"],
    output_file="dois.txt",
    key_list=["doi"]
)
```

### 图谱挖掘

```python
from fitch_citations import run_miner, fetch_combined_data

# 构建图谱
run_miner(seeds=["10.1038/nphys2439"])  # 耗时1-5小时

# 获取单篇论文数据
paper_data = fetch_combined_data("10.1038/nphys2439")
print(f"标题: {paper_data['title']}")
print(f"引用数: {len(paper_data['citations'])}")
```

---

## 🚀 快速开始

### 1. 安装

```bash
cd /home/zhiping/Projects/Academic_graph_miner
source /home/zhiping/research-env/bin/activate
```

### 2. 准备DOI列表

```bash
echo "10.1038/nphys2439" > doi_list.txt
echo "10.1103/PhysRevE.101.033202" >> doi_list.txt
```

### 3. 构建图谱

```bash
python main.py fitch --file doi_list.txt
```

### 4. 下载论文

```bash
python main.py download --file doi_list.txt --output papers/
```

### 5. 启动服务

```bash
# 端口5000: 交互图谱
python graph_server.py

# 端口5001: 数据浏览
python data_browser.py

# 端口5003: 下载管理
python download_server.py
```

### 6. 访问

- 图谱: http://localhost:5000
- 数据: http://localhost:5001
- 下载: http://localhost:5003

---

## 🔨 扩展开发

### 添加新的下载源

```python
# 在 download_paper.py 中添加

def download_via_my_source(doi: str, output_path: str) -> bool:
    """自定义下载方法"""
    try:
        # 实现下载逻辑
        pdf_content = fetch_from_my_api(doi)
        with open(output_path, 'wb') as f:
            f.write(pdf_content)
        
        # 验证
        return is_valid_pdf(output_path)
    except Exception as e:
        print(f"Error: {e}")
        return False

# 在 download_funcs 列表中注册
download_funcs = [
    ("my_source", download_via_my_source),  # 新增
    # 其他...
]
```

### 自定义相似度计算

```python
# 在 graph_utils.py 中扩展

def calculate_custom_similarity(paper1, paper2, method="jaccard"):
    """支持多种相似度计算方法"""
    if method == "jaccard":
        return calculate_jaccard(...)
    elif method == "cosine":
        return cosine_similarity(...)
    elif method == "custom":
        # 你的算法
        return custom_algorithm(...)
```

### 添加新的导出格式

```python
# 在 data_export.py 中添加

def export_to_custom(dois: List[str], output_file: str):
    """导出为自定义格式"""
    data = []
    for doi in dois:
        paper = get_paper(doi)
        # 转换为你的格式
        data.append(transform_to_custom(paper))
    
    # 保存
    with open(output_file, 'w') as f:
        # 写入逻辑
        pass
```

---

## 📝 最佳实践

1. **缓存管理**: 定期检查`last_updated`字段，过期数据重新获取
2. **错误处理**: 所有外部API调用都有重试机制
3. **性能优化**: 使用内存缓存而非重复查询
4. **并发控制**: 下载时使用线程池，避免并发过高
5. **数据备份**: 定期导出JSON备份
6. **版本控制**: 使用git管理核心代码，排除数据库文件

---

## 🐛 常见问题

**Q: 如何加速图谱构建?**  
A: 调低 `THRESHOLD` 参数或减少 `MAX_DEPTH`，但这会减少覆盖范围。

**Q: 如何处理论文下载失败?**  
A: 系统会自动尝试9个备选源，可手动重试或使用备用API。

**Q: 如何更新已下载的论文信息?**  
A: 删除对应的数据库记录或设置 `UPDATE_DAYS=0` 强制更新。

**Q: 如何集成自己的数据源?**  
A: 参考"扩展开发"部分，添加新的函数并注册到列表中。

---

**版本**: 4.0 (2026-04-21)  
**维护**: AI-Assisted  
**状态**: ✅ 生产就绪
