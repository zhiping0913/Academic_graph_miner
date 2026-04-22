#!/bin/bash
# 启动数据浏览器
# Usage: ./start_data_browser.sh

set -e

echo "🌐 启动学术论文数据浏览器..."
echo ""

PYTHON_ENV="/home/zhiping/research-env/bin/python3"

# 检查 Python 环境
if [ ! -f "$PYTHON_ENV" ]; then
    echo "❌ 错误：找不到 Python 环境 $PYTHON_ENV"
    exit 1
fi

# 检查依赖
echo "📦 检查依赖..."
$PYTHON_ENV -c "import flask" 2>/dev/null || {
    echo "⚠️  Flask 未安装，正在安装..."
    $PYTHON_ENV -m pip install flask >/dev/null 2>&1
}

echo ""
echo "✅ 启动数据浏览器服务..."
echo ""
echo "📍 访问地址: http://localhost:5001"
echo "📍 按 Ctrl+C 停止服务"
echo ""

$PYTHON_ENV data_browser.py
