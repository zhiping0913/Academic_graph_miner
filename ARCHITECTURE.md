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

- **数据库**: 17,348篇论文，1,746,807条引用关系
- **下载源**: 9种并行备选
- **API集成**: Semantic Scholar, Crossref, OpenAlex, Unpywall
- **Web界面**: 3个Flask服务 + 3个HTML前端

---

## 🔧 核心模块

### 1. 数据库层 - `db_sqlite.py`

**职责**: SQLite数据操作和持久化

**数据模型**:
```
papers表:
  id          INTEGER PRIMARY KEY
  doi         TEXT UNIQUE
  title       TEXT
  year        INTEGER
  journal     TEXT
  authors     TEXT (JSON array)
  last_updated TEXT

citations表:
  source_id    INTEGER (FK papers.id)
  target_doi   TEXT
  direction    TEXT (forward/backward)
  coefficient  REAL (Jaccard or NULL)
  PRIMARY KEY: (source_id, target_doi, direction)
```

**关键函数**:
```python
init_db()              # 初始化数据库schema
get_paper(doi)         # 获取单篇论文（含引用关系）
upsert_paper(paper)    # 插入/更新论文
load_db()              # 加载全部论文到内存 Dict
save_db(db)            # 批量保存
is_expired(ts, days)   # 检查缓存有效期
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
    "forward": ["10.aaaa", "10.bbbb"],           # 该论文引用的DOI
    "backward": ["10.cccc"],                    # 引用该论文的DOI
    "classified_forward": [                     # 有Jaccard系数的
        {"doi": "10.aaaa", "coefficient": 0.25}
    ],
    "classified_backward": [
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
   ├─ 提取forward和backward引用列表
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

extract_subgraph(db, seeds, max_forward_dist, max_backward_dist) -> nx.DiGraph
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
      "max_forward_dist": 1,
      "max_backward_dist": 1,
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

**API端点**:
```
GET /api/papers
  参数:
    - page: int (页码)
    - per_page: int (每页数量)
    - search: str (搜索关键词)
    - year_min/year_max: int (年份范围)
    - ref_doi: str (参考DOI)
    - similarity_min: float (最小相似度)
    - sort_by: str (year/title/similarity)
  功能: 分页查询论文列表

GET /api/citing-papers
  参数: doi (要查询的论文DOI)
  功能: 获取所有引用该论文的文章

GET /api/search-papers
  参数: q (搜索词)
  功能: 自动完成搜索

POST /api/fetch-paper
  参数: doi
  功能: 实时获取缺失的论文

POST /api/export
  参数: dois (DOI列表), format (json/csv/txt)
  功能: 导出论文数据
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
- **CSV**: 表格形式（DOI, 标题, 年份, 作者, forward引用, backward引用）
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
SQLite Database
├── papers: 17,348条论文记录
├── citations: 1,746,807条引用关系
└── 增量更新机制
    ├─ 新论文自动插入
    ├─ 缓存更新检查
    └─ 重复去重处理

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
    print(f"前向引用: {len(paper['forward'])}")
    print(f"有系数引用: {len(paper['classified_forward'])}")

# 更新论文
new_paper = {
    "doi": "10.xxxxx",
    "metadata": {"title": "...", "year": 2021, ...},
    "forward": [...],
    "backward": [...]
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
    max_forward_dist=1,
    max_backward_dist=1
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
