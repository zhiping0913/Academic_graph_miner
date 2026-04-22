#!/usr/bin/env python3
"""
测试下载指定的论文
"""

from download_paper import process_doi_list

if __name__ == "__main__":
    # 要测试的 DOI 列表
    test_dois = [
        "10.1038/nphys2439",
        "10.1103/PhysRevLett.92.185001",
        "10.1103/PhysRevE.101.033202"
    ]

    print("=" * 60)
    print("🚀 开始下载测试论文")
    print("=" * 60)
    print(f"待下载论文数: {len(test_dois)}\n")

    for doi in test_dois:
        print(f"  • {doi}")

    print("\n" + "=" * 60 + "\n")

    df_result = process_doi_list(test_dois, output_base_dir="test_papers")

    print("\n" + "=" * 60)
    print("📊 下载结果汇总")
    print("=" * 60)
    print(df_result.to_string())
    print("\n✅ 测试完成！")
