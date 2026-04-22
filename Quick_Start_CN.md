# 📚 Academic Graph Miner - 快速入门指南

欢迎使用 Academic Graph Miner！这是一个强大的学术文献网络分析工具。本指南将帮助你快速上手。

---

## 🚀 系统概览

Academic Graph Miner 包含四个核心功能：

```
┌─────────────────────────────────────────────────────────┐
│                 Academic Graph Miner                     │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  1️⃣  获取论文引用关系网络                                 │
│      ↓ fitch_citations.py                               │
│                                                           │
│  2️⃣  交互式查看论文相似关系                               │
│      ↓ data_browser.py (localhost:5001)                │
│                                                           │
│  3️⃣  可视化论文引用关系图谱                               │
│      ↓ graph_server.py (localhost:5000)                │
│                                                           │
│  4️⃣  批量下载论文 PDF                                    │
│      ↓ download_paper.py / download_server.py          │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

---

## 📖 详细使用步骤

### 第一步：准备论文 DOI 列表

创建一个文本文件 `my_dois.txt`，每行一个 DOI：

```
10.1038/nphys2439
10.1103/PhysRevE.101.033202
10.1088/1367-2630/15/1/015025
```

💡 **提示**：可以从 arXiv、Semantic Scholar 或 Crossref 找到 DOI

---

## 1️⃣ 获取论文引用关系网络

### 工作流程

以你给定的种子论文为起始点，系统会：
1. ✅ 抓取它引用的论文列表（forward references）
2. ✅ 抓取引用它的论文列表（backward references）
3. ✅ 计算相似度（Jaccard 系数）
4. ✅ 过滤相似度高于阈值的论文
5. 🔄 将筛选后的论文加入下一轮搜索

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--file` | DOI 列表文件 | `my_dois.txt` |
| `--depth` | 搜索深度 | `2` |
| `--threshold` | Jaccard 相似度阈值 | `0.1` |
| `--max-papers` | 最大论文数 | `1000` |

### 执行命令

```bash
# 激活 Python 环境
source /home/zhiping/research-env/bin/activate

# 运行引用关系爬虫
python fitch_citations.py --file my_dois.txt --depth 2 --threshold 0.1
```

### 数据存储

✅ 所有抓取的数据自动保存到 `academic_knowledge_graph.db`

```
academic_knowledge_graph.db
├── Papers Table (17,348 篇论文)
│   ├── DOI
│   ├── Title
│   ├── Year
│   └── Authors
└── Citations Table (1,746,807 个引用关系)
    ├── source_paper_id
    ├── target_doi
    └── Jaccard Coefficient
```

**性能指标**：
- 单次查询：1-5 小时（取决于搜索深度和网络速度）
- 数据库大小：~500 MB
- 加载时间：2-5 秒

---

## 2️⃣ 交互式查看论文相似关系

### 启动数据浏览器

```bash
python data_browser.py
```

然后在浏览器中打开：**http://localhost:5001**

### 功能说明

#### 📌 功能 1：按相似度筛选论文

![Data Browser Demo](images/data-browser-1.png)

1. 在 **参考论文** 输入框输入你感兴趣的论文 DOI
2. 设置 **Jaccard 相似度阈值**（如 0.1，范围 0.0-1.0）
3. 点击 **筛选** 按钮
4. 系统会显示所有与该论文相似度高于阈值的论文

**相似度说明**：
- Jaccard = |相同引用|  /  |总引用|
- 0.0 = 完全不同
- 1.0 = 引用完全相同

#### 📌 功能 2：一键导出 DOI 列表

![Export Function](images/data-browser-2.png)

1. 在页面中选择你感兴趣的论文（勾选复选框）
2. 点击 **导出** 按钮
3. 系统自动生成 DOI 列表文本文件
4. 可用于后续的论文下载或进一步分析

**导出格式**：
```
10.1038/nphys2439
10.1103/PhysRevE.101.033202
10.1088/1367-2630/15/1/015025
```

---

## 3️⃣ 可视化论文引用关系图谱

### 启动图谱服务器

```bash
python graph_server.py
```

然后在浏览器中打开：**http://localhost:5000**

### 功能说明

#### 📌 功能 1：构建论文引用网络

![Graph Builder](images/graph-server-1.png)

1. 在 **起始论文** 输入框输入 DOI
2. 设置 **网络深度**（1-3，建议 2）
3. 点击 **构建图谱**
4. 系统会显示该论文的引用网络关系

**图谱说明**：
- 🔵 **蓝色节点** = 论文（大小代表被引用次数）
- ➡️ **箭头** = 引用方向
- 🟠 **橙色节点** = 目标论文（起始点）
- 📏 **距离** = 引用关系强度

#### 📌 功能 2：动态添加论文

![Add Papers](images/graph-server-2.png)

1. 在 **新增论文** 输入框输入新的论文 DOI
2. 点击 **添加**
3. 点击 **刷新图谱**
4. 新论文及其关系会动态加入网络

**好处**：
- ✅ 快速对比多篇论文的引用关系
- ✅ 发现论文之间的隐藏联系
- ✅ 识别研究领域的核心论文

---

## 4️⃣ 下载论文 PDF

### 方式一：命令行批量下载

#### 准备 DOI 列表

```bash
# 创建文件 download_list.txt
cat > download_list.txt << 'EOF'
10.1038/nphys2439
10.1103/PhysRevE.101.033202
EOF
```

#### 执行下载

```bash
python download_paper.py --file download_list.txt --output papers/
```

**参数说明**：

| 参数 | 说明 | 示例 |
|------|------|------|
| `--file` | DOI 列表文件 | `download_list.txt` |
| `--output` | 输出目录 | `papers/` |
| `--year-based` | 按年份分类 | 自动创建 `2020/`, `2021/` 等 |

#### 下载过程

系统会尝试从以下来源依次下载论文：

```
1. Playwright (浏览器自动化) ⭐⭐⭐⭐⭐ 最可靠
2. doi2pdf 快速直接转换
3. OpenAlex API 开放获取链接
4. Crossref 出版商元数据
5. Unpywall API 开放获取数据库
6. arXiv 预印本
7. Scidownl (Sci-Hub 包装器)
8. Sci-Hub 直接访问
9. Playwright Stealth 隐身模式
```

#### 下载结果

```
papers/
├── 2012/
│   ├── 2012--Coherent synchrotron emission....pdf
│   └── 2012--Another paper....pdf
├── 2020/
│   └── 2020--Recent paper....pdf
└── download_report.csv
```

**报告说明** (`download_report.csv`)：

| 列 | 说明 |
|----|------|
| DOI | 论文编号 |
| Title | 论文标题 |
| Year | 发表年份 |
| PDF_Status | 下载状态 |
| PDF_Path | PDF 文件路径 |
| File_Size_MB | 文件大小 |
| Supplementary_Status | 补充材料查找状态 |
| Supplementary_Files | 补充材料列表 |

### 方式二：网页交互式下载

#### 启动下载服务器

```bash
python download_server.py
```

然后在浏览器中打开：**http://localhost:5003**

#### 使用方法

![Download Server](images/download-server.png)

1. **输入 DOI**：在文本框中输入论文 DOI
2. **选择目录**：选择保存论文的目录
3. **开始下载**：点击 **下载** 按钮
4. **实时监控**：查看下载进度和状态

**下载功能**：
- ✅ 自动验证 PDF 格式（防止被骗 HTML 文件）
- ✅ 自动检测补充材料
- ✅ 断点续传支持
- ⚠️ 成功率因出版商防护措施而异

---

## ⚙️ 环境设置

### 激活研究环境

```bash
source /home/zhiping/research-env/bin/activate
python --version  # 验证激活
```

### 安装依赖

```bash
pip install -r requirements.txt
```

### 浏览器驱动（仅需一次）

```bash
playwright install chromium
```

---

## 📊 完整工作流示例

### 场景：研究激光等离子体相互作用中的高次谐波生成

```bash
# 1️⃣ 准备种子论文
echo "10.1038/nphys2439" > seed_papers.txt
echo "10.1103/PhysRevE.101.033202" >> seed_papers.txt

# 2️⃣ 激活环境
source /home/zhiping/research-env/bin/activate

# 3️⃣ 构建引用网络（约 1-2 小时）
python fitch_citations.py --file seed_papers.txt --depth 2

# 4️⃣ 启动数据浏览器查看相似论文
python data_browser.py
# 打开 http://localhost:5001，筛选 Jaccard > 0.2 的论文

# 5️⃣ 启动图谱服务器可视化
python graph_server.py
# 打开 http://localhost:5000，构建论文网络

# 6️⃣ 导出感兴趣的论文 DOI 列表
# （在 data_browser 中勾选并导出）

# 7️⃣ 下载论文
python download_paper.py --file selected_papers.txt --output research/papers/

# 8️⃣ 查看下载报告
cat research/papers/download_report.csv
```

---

## 🔍 常见问题

### Q1: 为什么有些论文下载失败？

**A**: 很多论文网站有复杂的防自动化登录措施。系统已尽力尝试多个渠道，但成功率无法 100%。

✅ **解决方案**：
- 尝试从论文作者官网下载
- 查看 ResearchGate 或 arXiv 版本
- 通过机构 VPN 访问
- 直接向作者请求（通常会回应）

### Q2: 相似度阈值应该设置多少？

**A**: 取决于你的需求：

| 阈值 | 含义 | 适用场景 |
|------|------|---------|
| 0.1-0.2 | 宽松筛选 | 探索相关领域 |
| 0.2-0.3 | 中等筛选 | 找到相似论文 |
| 0.3-0.5 | 严格筛选 | 发现密切相关 |
| >0.5 | 非常严格 | 找几乎相同的 |

### Q3: 如何优化搜索性能？

**A**：
- ✅ 减少搜索深度（`--depth 1` 而非 `3`）
- ✅ 使用较高的相似度阈值（`0.2` 而非 `0.05`）
- ✅ 限制论文数量（`--max-papers 500`）
- ✅ 使用更强大的网络连接

### Q4: 数据库会自动更新吗？

**A**: 不会。数据库是静态的，每次运行 `fitch_citations.py` 时才会更新。要更新，重新运行爬虫即可。

---

## 📞 获取帮助

### 查看详细文档

```bash
# 下载模块文档
ls /home/zhiping/Projects/Academic_graph_miner/MODULE_*.md

# 查看特定模块
cat MODULE_DOWNLOAD_PAPER.md    # 论文下载
cat MODULE_FITCH_CITATIONS.md   # 引用爬虫
cat MODULE_GRAPH_UTILS.md       # 图算法
```

### 检查日志

```bash
# 查看下载日志
tail -100 download_paper.py.log

# 查看爬虫日志
tail -100 fitch_citations.py.log
```

---

## 🎯 下一步行动

1. ✅ **准备论文列表** → 保存到 `my_dois.txt`
2. ✅ **运行爬虫** → `python fitch_citations.py --file my_dois.txt`
3. ✅ **启动服务** → 打开浏览器访问三个 UI
4. ✅ **导出感兴趣的论文** → 从 data_browser 导出
5. ✅ **下载 PDF** → `python download_paper.py --file selected.txt`
6. ✅ **分析结果** → 在 `research/papers/` 中查看

---

## 📚 相关资源

- **arXiv**: https://arxiv.org - 获取 arXiv ID
- **Semantic Scholar**: https://semanticscholar.org - 查找论文和引用
- **Crossref**: https://www.crossref.org - 验证 DOI
- **OpenAlex**: https://openalex.org - 开放获取元数据

---

**💡 祝你使用愉快！如有问题，欢迎反馈。**

---

*最后更新: 2026-04-22*  
*版本: 2.0*  
*语言: 中文 (Chinese)*
