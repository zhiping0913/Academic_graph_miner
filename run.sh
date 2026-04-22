#!/bin/bash
# 学术图谱挖掘工具 - 快速启动脚本

set -e

PYTHON_ENV="/home/zhiping/research-env/bin/python3"

# 检查 Python 环境
if [ ! -f "$PYTHON_ENV" ]; then
    echo "❌ 错误：找不到 Python 环境 $PYTHON_ENV"
    exit 1
fi

# 显示帮助信息
show_help() {
    cat << EOF
📚 学术图谱挖掘工具 - 快速启动

用法：
    $0 [命令] [选项]

命令：
    fitch       - 构建学术引用图谱
    download    - 批量下载论文
    all         - 完整工作流（图谱 + 下载）
    help        - 显示此帮助信息

选项：
    --file FILE    - 指定 DOI 列表文件（默认：doi_list.txt）
    --doi ...      - 直接指定 DOI（空格分隔）
    --output DIR   - 指定下载输出目录（默认：downloaded_papers）

示例：
    # 完整工作流
    $0 all

    # 仅下载论文
    $0 download

    # 使用自定义 DOI 文件
    $0 all --file seeds.txt

    # 直接指定 DOI
    $0 download --doi 10.1038/nphys2439 10.1103/PhysRevLett.92.185001

更多信息请查看 CLI_GUIDE.md
EOF
}

# 主逻辑
case "${1:-help}" in
    fitch)
        shift
        echo "🔗 启动：学术引用图谱构建"
        $PYTHON_ENV fitch_citations.py "$@"
        ;;
    download)
        shift
        echo "📥 启动：论文批量下载"
        $PYTHON_ENV download_paper.py "$@"
        ;;
    all)
        shift
        echo "🚀 启动：完整工作流"
        $PYTHON_ENV main.py all "$@"
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo "❌ 未知命令：$1"
        echo ""
        show_help
        exit 1
        ;;
esac
