#!/usr/bin/env python3
"""
示例：使用新增下载方案测试

这个脚本演示如何使用 download_paper.py 中的各种下载方案。
"""

from download_paper import (
    download_via_openalex,
    download_via_crossref_links,
    download_via_unpywall,
    download_via_arxiv,
    download_via_doi2pdf,
    download_via_scidownl,
    download_via_scihub_direct,
    download_via_playwright_stealth,
    PLAYWRIGHT_AVAILABLE,
    get_paper_metadata,
    process_doi_list
)

def test_single_method():
    """测试单个下载方法"""
    doi = "10.1088/1367-2630/15/1/015025"
    output_path = f"/tmp/{doi.replace('/', '_')}.pdf"

    print(f"测试 DOI: {doi}")
    print(f"输出路径: {output_path}\n")

    # 获取元数据
    title, year = get_paper_metadata(doi)
    print(f"论文标题: {title}")
    print(f"出版年份: {year}\n")

    methods = [
        ("OpenAlex", download_via_openalex),
        ("CrossRef Links", download_via_crossref_links),
        ("Unpywall", download_via_unpywall),
        ("arXiv", download_via_arxiv),
        ("DOI2PDF", download_via_doi2pdf),
        ("scidownl", download_via_scidownl),
        ("Sci-Hub Direct", download_via_scihub_direct),
    ]

    if PLAYWRIGHT_AVAILABLE:
        methods.append(("Playwright Stealth", download_via_playwright_stealth))

    for method_name, method_func in methods:
        print(f"尝试 {method_name}...", end=" ")
        try:
            if method_func(doi, output_path):
                print(f"✅ 成功")
                return output_path
            else:
                print(f"❌ 失败")
        except Exception as e:
            print(f"❌ 异常: {str(e)[:50]}")

    print("\n❌ 所有方法均失败")
    return None

def test_batch_download():
    """测试批量下载"""
    dois = [
        "10.1088/1367-2630/15/1/015025",  # Physics paper
        "10.1038/s41586-020-03053-2",      # Nature paper
        # "10.48550/arXiv.2312.00000",     # arXiv preprint
    ]

    print("开始批量下载...\n")
    df = process_doi_list(dois, output_base_dir="downloaded_papers_test")
    print("\n下载完成！")
    print(df)

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        test_batch_download()
    else:
        test_single_method()

    print("\n提示: 使用 'python test_download.py batch' 进行批量下载测试")
