#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
学术图谱挖掘工具 - 主启动脚本
集成论文引用图谱构建 (fitch_citations.py) 和批量下载 (download_paper.py)
"""

import argparse
import sys
import os
import subprocess
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(
        description="学术图谱挖掘工具 - 构建和下载学术引用网络",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
主要功能：
  1. fitch   - 构建学术引用图谱（基于 DOI 列表）
  2. download - 批量下载论文 PDF

示例用法：
  # 构建图谱
  python main.py fitch

  # 下载论文
  python main.py download

  # 使用指定的 DOI 文件
  python main.py fitch --file seeds.txt
  python main.py download --file seeds.txt

  # 直接指定 DOI
  python main.py fitch --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001
  python main.py download --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

  # 一站式操作（先构建图谱，再下载）
  python main.py all --file doi_list.txt

查看帮助：
  python main.py fitch --help
  python main.py download --help
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # ===== fitch 子命令 =====
    fitch_parser = subparsers.add_parser("fitch", help="构建学术引用图谱")
    fitch_parser.add_argument(
        "--file",
        type=str,
        default="doi_list.txt",
        help="DOI 列表文件（默认：doi_list.txt）"
    )
    fitch_parser.add_argument(
        "--doi",
        nargs="+",
        help="直接指定 DOI"
    )

    # ===== download 子命令 =====
    download_parser = subparsers.add_parser("download", help="批量下载论文")
    download_parser.add_argument(
        "--file",
        type=str,
        default="doi_list.txt",
        help="DOI 列表文件（默认：doi_list.txt）"
    )
    download_parser.add_argument(
        "--doi",
        nargs="+",
        help="直接指定 DOI"
    )
    download_parser.add_argument(
        "--output",
        type=str,
        default="downloaded_papers",
        help="输出目录（默认：downloaded_papers）"
    )

    # ===== all 子命令 =====
    all_parser = subparsers.add_parser("all", help="完整工作流（图谱 + 下载）")
    all_parser.add_argument(
        "--file",
        type=str,
        default="doi_list.txt",
        help="DOI 列表文件（默认：doi_list.txt）"
    )
    all_parser.add_argument(
        "--output",
        type=str,
        default="downloaded_papers",
        help="输出目录（默认：downloaded_papers）"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # 检查必要文件
    if not os.path.exists(args.file if hasattr(args, 'file') else "doi_list.txt"):
        default_file = getattr(args, 'file', 'doi_list.txt')
        print(f"⚠️  警告：文件 {default_file} 不存在")
        print(f"📝 请创建 {default_file}，每行一个 DOI")
        sys.exit(1)

    # 执行子命令
    if args.command == "fitch":
        print("\n" + "=" * 60)
        print("🔗 启动：学术引用图谱构建")
        print("=" * 60 + "\n")

        cmd = ["python3", "fitch_citations.py"]
        if hasattr(args, 'file') and args.file != "doi_list.txt":
            cmd.extend(["--file", args.file])
        if hasattr(args, 'doi') and args.doi:
            cmd.append("--doi")
            cmd.extend(args.doi)

        subprocess.run(cmd)

    elif args.command == "download":
        print("\n" + "=" * 60)
        print("📥 启动：论文批量下载")
        print("=" * 60 + "\n")

        cmd = ["python3", "download_paper.py"]
        if hasattr(args, 'file') and args.file != "doi_list.txt":
            cmd.extend(["--file", args.file])
        if hasattr(args, 'doi') and args.doi:
            cmd.append("--doi")
            cmd.extend(args.doi)
        cmd.extend(["--output", args.output])

        subprocess.run(cmd)

    elif args.command == "all":
        print("\n" + "=" * 60)
        print("🚀 启动：完整工作流")
        print("=" * 60)
        print("✓ 第一步：构建学术引用图谱")
        print("✓ 第二步：批量下载论文")
        print("=" * 60 + "\n")

        # 第一步：构建图谱
        print("\n📍 [1/2] 开始构建学术引用图谱...\n")
        cmd1 = ["python3", "fitch_citations.py", "--file", args.file]
        result1 = subprocess.run(cmd1)

        if result1.returncode == 0:
            print("\n✅ 图谱构建完成！")
            # 第二步：下载论文
            print("\n📍 [2/2] 开始批量下载论文...\n")
            cmd2 = ["python3", "download_paper.py", "--file", args.file, "--output", args.output]
            result2 = subprocess.run(cmd2)

            if result2.returncode == 0:
                print("\n" + "=" * 60)
                print("✅ 所有操作完成！")
                print("=" * 60)
                print(f"📁 已下载论文：{args.output}/")
            else:
                print("\n❌ 下载失败，请检查错误信息")
                sys.exit(1)
        else:
            print("\n❌ 图谱构建失败，请检查错误信息")
            sys.exit(1)

if __name__ == "__main__":
    main()
