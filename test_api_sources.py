#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本：验证三个 API 源的数据获取和合并
DOI 示例：10.1038/s41567-019-0584-7
"""

import sys
sys.path.insert(0, '/home/zhiping/Projects/Academic_graph_miner')

from fitch_citations import fetch_semanticscholar, fetch_crossref, fetch_opencitations, fetch_combined_data

# 测试 DOI
test_doi = "10.1038/s41567-019-0584-7"

print("=" * 80)
print(f"🔬 测试论文：{test_doi}")
print("=" * 80)

# ============================================================================
# 1. Semantic Scholar API
# ============================================================================
print("\n📊 [1] Semantic Scholar API")
print("-" * 80)

s2_data = fetch_semanticscholar(test_doi)

s2_title = s2_data.get('title', "❌ 无法获取") if s2_data else "❌ API 返回空"
s2_citations = s2_data.get('citations') if s2_data else None
s2_references = s2_data.get('references') if s2_data else None
s2_citations_count = len(s2_citations) if isinstance(s2_citations, list) else 0
s2_references_count = len(s2_references) if isinstance(s2_references, list) else 0

print(f"📄 标题：{s2_title}")
print(f"📚 Citations 数量（被引用）：{s2_citations_count}")
print(f"📚 References 数量（引用他人）：{s2_references_count}")

# ============================================================================
# 2. Crossref API
# ============================================================================
print("\n📊 [2] Crossref API")
print("-" * 80)

import time
time.sleep(1.2)  # 遵守速率限制

cr_data = fetch_crossref(test_doi)

# 处理标题（Crossref 返回列表）
cr_titles = cr_data.get('title')
cr_title = cr_titles[0] if isinstance(cr_titles, list) and cr_titles else "❌ 无法获取"

cr_references = cr_data.get('reference', [])
cr_references_count = len(cr_references) if isinstance(cr_references, list) else 0
cr_citations_count = "❌ Crossref 无被引数据"

print(f"📄 标题：{cr_title}")
print(f"📚 Citations 数量（被引用）：{cr_citations_count}")
print(f"📚 References 数量（引用他人）：{cr_references_count}")

# ============================================================================
# 3. OpenCitations API
# ============================================================================
print("\n📊 [3] OpenCitations API")
print("-" * 80)

time.sleep(1.2)  # 遵守速率限制

oc_data = fetch_opencitations(test_doi)

oc_title = "⚠️ OpenCitations 无标题数据"
oc_citations_count = len(oc_data.get('citations', []))
oc_references_count = len(oc_data.get('references', []))

print(f"📄 标题：{oc_title}")
print(f"📚 Citations 数量（被引用）：{oc_citations_count}")
print(f"📚 References 数量（引用他人）：{oc_references_count}")

# ============================================================================
# 4. 合并数据 (fetch_combined_data)
# ============================================================================
print("\n📊 [4] 合并数据 (Semantic Scholar + Crossref + OpenCitations)")
print("-" * 80)

time.sleep(1.2)  # 遵守速率限制

combined = fetch_combined_data(test_doi)

if combined:
    combined_title = combined['metadata'].get('title', "❌ 无法获取")
    combined_forward_count = len(combined.get('forward', []))
    combined_backward_count = len(combined.get('backward', []))

    print(f"📄 标题：{combined_title}")
    print(f"📚 Forward (Citations) 总数：{combined_forward_count}")
    print(f"📚 Backward (References) 总数：{combined_backward_count}")
else:
    print("❌ 无法获取合并数据")

# ============================================================================
# 5. 对比分析
# ============================================================================
print("\n📈 [5] 数据对比分析")
print("=" * 80)

print("\n📚 Citations (被引用) 数量对比：")
print(f"  Semantic Scholar：{s2_citations_count}")
print(f"  Crossref：{cr_citations_count}")
print(f"  OpenCitations：{oc_citations_count}")
if combined:
    print(f"  ✅ 合并后：{combined_forward_count} (Forward 列表)")

print("\n📚 References (引用他人) 数量对比：")
print(f"  Semantic Scholar：{s2_references_count}")
print(f"  Crossref：{cr_references_count}")
print(f"  OpenCitations：{oc_references_count}")
if combined:
    print(f"  ✅ 合并后：{combined_backward_count} (Backward 列表)")

print("\n📄 标题对比：")
print(f"  Semantic Scholar：{s2_title}")
print(f"  Crossref：{cr_title}")
if combined:
    print(f"  ✅ 最终标题：{combined_title}")

# ============================================================================
# 6. 样本数据展示
# ============================================================================
print("\n🔍 [6] 样本数据展示")
print("=" * 80)

if s2_citations_count > 0:
    print(f"\n📌 Semantic Scholar Citations 样本 (前3条)：")
    s2_cites = s2_data.get('citations', [])[:3]
    for i, cite in enumerate(s2_cites, 1):
        if isinstance(cite, dict) and 'externalIds' in cite:
            ext_ids = cite.get('externalIds', {})
            doi_val = ext_ids.get('DOI', 'N/A')
            print(f"   {i}. {doi_val}")

if oc_citations_count > 0:
    print(f"\n📌 OpenCitations Citations 样本 (前3条)：")
    oc_cites = oc_data.get('citations', [])[:3]
    for i, cite in enumerate(oc_cites, 1):
        citing = cite.get('citing', 'N/A')
        print(f"   {i}. {citing}")

print("\n" + "=" * 80)
print("✅ 测试完成！")
print("=" * 80)
