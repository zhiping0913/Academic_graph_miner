#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试脚本：验证新的 Playwright 下载方法和 PDF 验证逻辑
"""

import sys
import os
sys.path.insert(0, '/home/zhiping/Projects/Academic_graph_miner')

from download_paper import (
    is_valid_pdf,
    is_valid_pdf_response,
    check_paper_already_exists
)

print("=" * 70)
print("🧪 论文下载系统改进测试")
print("=" * 70)

# 测试 1: PDF 验证逻辑
print("\n✅ 测试 1: PDF 验证逻辑")
print("-" * 70)

import tempfile
import shutil

test_dir = tempfile.mkdtemp()
print(f"临时目录: {test_dir}")

# 创建测试文件
test_cases = [
    {
        "name": "有效的 PDF",
        "content": b'%PDF-1.4\n' + b'1 0 obj\n<</Type/Catalog>>\nendobj\n' + b'xref\n0 1\n0000000000 65535 f\ntrailer\n<</Size 1 /Root 1 0 R>>\nstartxref\n0\n' + b'%%EOF\n' + (b'x' * 200),  # 填充到 >= 200 字节
        "expected": True
    },
    {
        "name": "HTML 伪装成 PDF",
        "content": b'<html><head><title>Captcha</title></head><body>' + (b'x' * 200) + b'</body></html>',
        "expected": False
    },
    {
        "name": "太小的 PDF",
        "content": b'%PDF',
        "expected": False
    },
    {
        "name": "JavaScript 文件",
        "content": b'<script type="text/javascript">window.location="...";</script>' + (b'x' * 200),
        "expected": False
    },
    {
        "name": "PDF 但无 EOF 标记（小文件）",
        "content": b'%PDF-1.4\n' + (b'x' * 200),
        "expected": False
    },
]

results = []
for test in test_cases:
    filepath = os.path.join(test_dir, f"test_{len(results)}.pdf")
    with open(filepath, 'wb') as f:
        f.write(test['content'])

    result = is_valid_pdf(filepath)
    status = "✅" if result == test['expected'] else "❌"
    results.append(result == test['expected'])

    print(f"{status} {test['name']}: {result} (预期: {test['expected']})")

# 测试 2: 已下载检查功能
print("\n✅ 测试 2: 已下载文件检查")
print("-" * 70)

# 创建已下载的文件
downloaded_dir = tempfile.mkdtemp()
existing_file = os.path.join(downloaded_dir, "2021--Test Paper Title.pdf")
with open(existing_file, 'wb') as f:
    f.write(b'%PDF-1.4\n' + b'content' * 100 + b'\n%%EOF\n')

found = check_paper_already_exists(downloaded_dir, "2021", "Test Paper Title", "10.xxxx/test")
status = "✅" if found else "❌"
print(f"{status} 发现已下载的文件: {os.path.basename(found) if found else 'Not found'}")
results.append(found is not None)

# 清理
shutil.rmtree(test_dir)
shutil.rmtree(downloaded_dir)

# 总结
print("\n" + "=" * 70)
print("📊 测试结果总结")
print("=" * 70)
passed = sum(results)
total = len(results)
percentage = (passed / total * 100) if total > 0 else 0

print(f"通过: {passed}/{total} ({percentage:.1f}%)")

if passed == total:
    print("✅ 所有测试通过！改进已生效。")
    sys.exit(0)
else:
    print(f"❌ {total - passed} 个测试失败")
    sys.exit(1)
