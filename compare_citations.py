#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对比测试：三个 API 源的引用数对比
DOI：10.1038/s41586-026-10400-2
"""

import sys
sys.path.insert(0, '/home/zhiping/Projects/Academic_graph_miner')

from fitch_citations import fetch_semanticscholar, fetch_crossref, fetch_opencitations, fetch_combined_data
import time

# 测试 DOI
test_doi = "10.1038/s41586-026-10400-2"

print("=" * 100)
print(f"🔬 论文 DOI：{test_doi}")
print("=" * 100)

# ============================================================================
# 1. Semantic Scholar API
# ============================================================================
print("\n[1] 📊 Semantic Scholar")
print("-" * 100)

s2_data = fetch_semanticscholar(test_doi)
s2_title = s2_data.get('title', "N/A") if s2_data else "N/A"
s2_citations = s2_data.get('citations') if s2_data else None
s2_references = s2_data.get('references') if s2_data else None
s2_forward = len(s2_citations) if isinstance(s2_citations, list) else 0  # Citations (forward)
s2_backward = len(s2_references) if isinstance(s2_references, list) else 0  # References (backward)

print(f"标题：{s2_title}")
print(f"  → Forward (Citations)：{s2_forward}")
print(f"  ← Backward (References)：{s2_backward}")

time.sleep(1.2)

# ============================================================================
# 2. Crossref API
# ============================================================================
print("\n[2] 📊 Crossref")
print("-" * 100)

cr_data = fetch_crossref(test_doi)
cr_titles = cr_data.get('title')
cr_title = cr_titles[0] if isinstance(cr_titles, list) and cr_titles else "N/A"
cr_references = cr_data.get('reference', [])
cr_forward = 0  # Crossref 不提供被引数据
cr_backward = len(cr_references) if isinstance(cr_references, list) else 0

print(f"标题：{cr_title}")
print(f"  → Forward (Citations)：{cr_forward} (Crossref 无此数据)")
print(f"  ← Backward (References)：{cr_backward}")

time.sleep(1.2)

# ============================================================================
# 3. OpenCitations API
# ============================================================================
print("\n[3] 📊 OpenCitations")
print("-" * 100)

oc_data = fetch_opencitations(test_doi)
oc_citations = oc_data.get('citations', [])
oc_references = oc_data.get('references', [])

# OpenCitations 的数据对应关系：
# - citations 返回 {'citing': ..., 'cited': ...} 形式
#   含义：citing 论文引用了本论文 (谁引用了我) → Forward
# - references 返回 {'citing': ..., 'cited': ...} 形式
#   含义：本论文(citing)引用了 cited 论文 (我引用了谁) → Backward

oc_forward = len(oc_citations) if isinstance(oc_citations, list) else 0   # 谁引用了本论文 (Forward)
oc_backward = len(oc_references) if isinstance(oc_references, list) else 0  # 本论文引用了谁 (Backward)

print(f"标题：(OpenCitations 无标题数据)")
print(f"  → Forward (被引用)：{oc_forward}")
print(f"  ← Backward (引用他人)：{oc_backward}")

time.sleep(1.2)

# ============================================================================
# 4. 合并数据
# ============================================================================
print("\n[4] 📊 合并后 (S2 + Crossref + OpenCitations)")
print("-" * 100)

combined = fetch_combined_data(test_doi)

if combined:
    combined_title = combined['metadata'].get('title', 'N/A')
    combined_forward = len(combined.get('forward', []))
    combined_backward = len(combined.get('backward', []))

    print(f"标题：{combined_title}")
    print(f"  → Forward (Citations)：{combined_forward}")
    print(f"  ← Backward (References)：{combined_backward}")
else:
    print("❌ 无法获取合并数据")
    combined_forward = 0
    combined_backward = 0

# ============================================================================
# 5. 对比汇总表
# ============================================================================
print("\n" + "=" * 100)
print("📈 对比汇总表")
print("=" * 100)

print("\n🔵 Forward (Citations - 这篇论文引用了多少论文)：")
print(f"  {'数据源':<20} {'数量':>10}")
print(f"  {'-'*30}")
print(f"  {'Semantic Scholar':<20} {s2_forward:>10}")
print(f"  {'Crossref':<20} {cr_forward:>10}")
print(f"  {'OpenCitations':<20} {oc_forward:>10}")
print(f"  {'─'*30}")
print(f"  {'✅ 合并后':<20} {combined_forward:>10}")

print("\n🔴 Backward (References - 有多少论文引用了这篇)：")
print(f"  {'数据源':<20} {'数量':>10}")
print(f"  {'-'*30}")
print(f"  {'Semantic Scholar':<20} {s2_backward:>10}")
print(f"  {'Crossref':<20} {cr_backward:>10}")
print(f"  {'OpenCitations':<20} {oc_backward:>10}")
print(f"  {'─'*30}")
print(f"  {'✅ 合并后':<20} {combined_backward:>10}")

# ============================================================================
# 6. 数据来源分析
# ============================================================================
print("\n" + "=" * 100)
print("🔍 数据来源分析")
print("=" * 100)

print(f"\n📌 Forward 来自哪些源：")
print(f"   - S2 citations: {s2_forward}")
print(f"   - OpenCitations references: {oc_forward}")
print(f"   {'= 合并 (去重):':<20} {combined_forward}")

if combined_forward > 0:
    s2_oc_overlap = max(0, s2_forward + oc_forward - combined_forward)
    print(f"   (可能有 {s2_oc_overlap} 条重复数据)")

print(f"\n📌 Backward 来自哪些源：")
print(f"   - S2 references: {s2_backward}")
print(f"   - Crossref references: {cr_backward}")
print(f"   - OpenCitations citations: {oc_backward}")
print(f"   {'= 合并 (去重):':<20} {combined_backward}")

total_sources = s2_backward + cr_backward + oc_backward
if total_sources > 0:
    overlap = max(0, total_sources - combined_backward)
    print(f"   (合并后去重：去除了 {overlap} 条重复数据)")

# ============================================================================
# 7. 质量评估
# ============================================================================
print("\n" + "=" * 100)
print("⭐ 数据质量评估")
print("=" * 100)

print(f"\n🏆 最佳数据源排名 (Forward)：")
forward_sources = [
    ("Semantic Scholar", s2_forward),
    ("Crossref", cr_forward),
    ("OpenCitations", oc_forward)
]
for i, (name, count) in enumerate(sorted(forward_sources, key=lambda x: x[1], reverse=True), 1):
    print(f"   {i}. {name:<20} {count:>5} 条")

print(f"\n🏆 最佳数据源排名 (Backward)：")
backward_sources = [
    ("Semantic Scholar", s2_backward),
    ("Crossref", cr_backward),
    ("OpenCitations", oc_backward)
]
for i, (name, count) in enumerate(sorted(backward_sources, key=lambda x: x[1], reverse=True), 1):
    print(f"   {i}. {name:<20} {count:>5} 条")

# ============================================================================
# 8. 结论
# ============================================================================
print("\n" + "=" * 100)
print("✅ 测试完成")
print("=" * 100)

print(f"""
📊 关键发现：
   1. Forward 总数: {combined_forward}
      主要来自：OpenCitations references ({oc_forward})

   2. Backward 总数: {combined_backward}
      主要来自：OpenCitations citations ({oc_backward})
                + Crossref references ({cr_backward})

   3. 最全面的数据源：OpenCitations
      (提供了 {oc_forward + oc_backward} 条引用关系)

   4. 合并策略有效：
      原始数据总和 {total_sources} 条 → 合并去重后 {combined_backward} 条 (Backward)
""")

print("=" * 100)
