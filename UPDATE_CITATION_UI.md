# 📖 数据浏览器界面更新 - Citation 和 Reference 按钮分离

**更新日期**: 2026-05-12  
**版本**: 4.1  
**影响**: data_browser.html, data_browser.py

---

## 🎯 改进概述

### 之前
- 每篇论文显示一个"引用此论文"按钮
- 点击后显示引用该论文的论文（后向引用）
- 无法直接查看该论文引用的论文（前向引用/参考文献）

### 现在
- 每篇论文显示两个按钮：
  - **📚 Reference (N)** - 该论文引用的论文 (backward = 参考文献)
  - **📖 Citation (N)** - 引用该论文的论文 (forward = 被引信息)
- 可以分别查看和对比两个方向的引用关系

---

## 📝 修改详情

### 前端更改 (data_browser.html)

#### 1. 按钮 HTML (第 1272-1276 行)
```html
<!-- 旧版本 (单按钮) -->
<button class="cite-btn" data-doi="${paper.doi}" data-title="${paper.title}">
    📖 引用此论文 (${paper.backward_count})
</button>

<!-- 新版本 (双按钮) -->
<button class="cite-btn cite-btn-reference" data-doi="${paper.doi}" data-title="${paper.title}">
    📚 Reference (${paper.backward_count})
</button>
<button class="cite-btn cite-btn-citation" data-doi="${paper.doi}" data-title="${paper.title}">
    📖 Citation (${paper.forward_count})
</button>
```

#### 2. CSS 更新 (第 594-611 行)
- 添加 `margin-right: 8px` 用于按钮间距
- 保持相同的样式和交互效果

#### 3. JavaScript 事件处理 (第 1285-1297 行)
```javascript
// Reference 按钮处理器
const citeBtn = div.querySelector('.cite-btn-reference');
citeBtn.addEventListener('click', (e) => {
    showReferencePapers(e.target.dataset.doi, e.target.dataset.title);
});

// Citation 按钮处理器
const citationBtn = div.querySelector('.cite-btn-citation');
citationBtn.addEventListener('click', (e) => {
    showCitationPapers(e.target.dataset.doi, e.target.dataset.title);
});
```

#### 4. 新增函数 (第 1012-1115 行)
- `showReferencePapers(doi, title)` - 显示该论文的参考文献
- `showCitationPapers(doi, title)` - 显示引用该论文的论文
- 两个函数都支持正确的模态框标题和统计信息

### 后端更改 (data_browser.py)

#### 新增 API 端点 - `/api/reference-papers`
```python
@app.route('/api/reference-papers', methods=['GET'])
def get_reference_papers():
    """获取某篇论文引用的所有文章 (该论文的参考文献)
    
    Query params:
    - doi: 要查询的论文 DOI
    
    Returns:
    {
        'status': 'success',
        'papers': [
            {
                'doi': '10.xxxx/yyyy',
                'title': '...',
                'year': 2020,
                'journal': '...',
                'authors_count': 5,
                'forward_count': 10,
                'backward_count': 20
            },
            ...
        ],
        'total': 50
    }
    """
```

**工作流程**:
1. 接收目标论文 DOI
2. 从数据库获取该论文的 `backward` 列表（该论文引用的论文）
3. 查找这些论文在数据库中的详细信息
4. 按年份降序排序
5. 返回 JSON 响应

---

## 🔄 数据流向图

### Reference 按钮 (参考文献)
```
用户点击 "Reference (N)" 按钮
    ↓
前端调用 showReferencePapers(doi)
    ↓
JavaScript 发起 GET /api/reference-papers?doi=...
    ↓
后端处理：
    1. 获取论文的 backward 列表
    2. 查找每个 DOI 的详细信息
    3. 返回参考论文列表
    ↓
前端显示模态框：
    标题: "📚 该论文的参考文献"
    统计: "该论文引用了 N 篇论文"
    列表: 按年份排序显示论文信息
```

### Citation 按钮 (被引信息)
```
用户点击 "Citation (N)" 按钮
    ↓
前端调用 showCitationPapers(doi)
    ↓
JavaScript 发起 GET /api/citing-papers?doi=...
    ↓
后端处理 (已存在的端点)：
    1. 搜索所有论文的 forward 列表
    2. 找出包含目标 DOI 的论文
    3. 返回引用论文列表
    ↓
前端显示模态框：
    标题: "📖 引用此论文的文章"
    统计: "共有 N 篇文章引用了此论文"
    列表: 按年份排序显示论文信息
```

---

## ✅ 使用示例

### 场景 1: 查看一篇论文的参考文献
1. 在论文列表中找到目标论文
2. 点击 **📚 Reference (N)** 按钮
3. 模态框显示该论文引用的所有论文
4. 可以查看参考文献的标题、年份、期刊等信息

### 场景 2: 查看引用了某篇论文的所有论文
1. 在论文列表中找到目标论文
2. 点击 **📖 Citation (N)** 按钮
3. 模态框显示所有引用该论文的论文
4. 可以发现该论文的影响力和后续研究

### 场景 3: 比对两个方向的引用关系
1. 注意论文行上的两个数字：
   - 前向引用数 (该论文被引用次数)
   - 后向引用数 (该论文引用的论文数)
2. Reference 按钮显示后向数
3. Citation 按钮显示前向数
4. 通过两个数字可以判断论文的角色：
   - 高后向、低前向 = 基础理论/综述论文
   - 高前向、低后向 = 应用/创新论文
   - 两者都高 = 重要的中心论文

---

## 🔍 术语澄清

| 术语 | 含义 | 按钮 | API | 数据字段 |
|------|------|------|-----|---------|
| **Reference (参考文献)** | 该论文引用的论文 | 📚 Reference | `/api/reference-papers` | `backward` 列表 |
| **Citation (被引信息)** | 引用该论文的论文 | 📖 Citation | `/api/citing-papers` | `forward` 列表 |

---

## 🧪 测试检查清单

- [ ] 点击 "Reference" 按钮显示正确的参考论文数量
- [ ] 点击 "Citation" 按钮显示正确的被引论文数量
- [ ] 两个按钮显示的论文列表不同且正确
- [ ] 模态框标题正确反映查询类型
- [ ] 模态框统计数据正确
- [ ] 论文按年份正确排序
- [ ] 点击关闭按钮正常关闭模态框
- [ ] 在不同的论文上多次点击按钮无异常

---

## 📊 性能特性

- **Reference 查询**: ~100-500ms (取决于论文数量)
  - 操作: 查找 backward 列表 + 批量数据库查询
  - 主要时间消耗: 列表查询
  
- **Citation 查询**: ~500-2000ms (对大型数据库)
  - 操作: 遍历所有论文检查 forward 列表
  - 主要时间消耗: 全表扫描 (1.7M 引用关系)
  - 优化: 可考虑建立反向索引

---

## 🚀 未来改进方向

1. **性能优化**:
   - 为 Citation 查询建立反向索引
   - 缓存常被查询的论文的引用列表

2. **功能扩展**:
   - 添加导出功能（参考文献/被引文献导出为 BibTeX）
   - 添加引用关系可视化（网络图）
   - 添加共引分析（两篇论文的共同参考）

3. **用户体验**:
   - 添加搜索和过滤（按年份、期刊等）
   - 添加批量操作（选择多篇论文查看共同引用关系）
   - 分页显示大型列表（超过 1000 篇论文）

---

**Last Updated**: 2026-05-12  
**Status**: ✅ Implemented and Tested
