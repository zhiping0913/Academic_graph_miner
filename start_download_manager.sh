#!/bin/bash
# 启动论文下载管理器

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 检查虚拟环境
if [ ! -d "/home/zhiping/research-env" ]; then
    echo "❌ 错误: 研究环境 /home/zhiping/research-env 不存在"
    exit 1
fi

echo "🚀 启动论文下载管理器..."
echo "📊 访问地址: http://localhost:5002"
echo ""

# 运行服务器
/home/zhiping/research-env/bin/python3 download_server.py
