#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Flask server for interactive paper downloading with real-time progress tracking.
Usage: python download_server.py  (then open http://localhost:5003)
"""

import os
import json
import threading
import queue
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file
from backend import OUTPUT_PATH
from download_paper import (
    get_paper_metadata,
    download_pdf,
    check_paper_already_exists,
    download_supplementary_materials
)

app = Flask(__name__, static_folder=OUTPUT_PATH)

# 全局变量用于跟踪下载任务
download_tasks = {}
task_queue = queue.Queue()


@app.route('/')
def index():
    """返回下载管理器页面"""
    return render_template_string(HTML_TEMPLATE)


@app.route('/api/download-start', methods=['POST'])
def start_download():
    """启动下载任务

    Request body:
    {
        "dois": ["10.1038/nphys2439", ...],
        "output_dir": "downloaded_papers"
    }
    """
    try:
        data = request.get_json()
        dois = data.get('dois', [])
        output_dir = data.get('output_dir', 'downloaded_papers')

        if not dois:
            return jsonify({'status': 'error', 'message': '请提供至少一个 DOI'}), 400

        # 清理 DOI 列表
        dois = [d.strip().lower() for d in dois if d.strip()]

        if not dois:
            return jsonify({'status': 'error', 'message': '无效的 DOI 列表'}), 400

        # 创建任务
        task_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        os.makedirs(output_dir, exist_ok=True)

        # 在后台线程中执行下载
        thread = threading.Thread(
            target=download_worker,
            args=(task_id, dois, output_dir)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'status': 'success',
            'task_id': task_id,
            'message': f'开始下载 {len(dois)} 篇论文'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/download-progress/<task_id>', methods=['GET'])
def get_progress(task_id):
    """获取下载进度

    Returns:
    {
        "status": "processing" | "completed" | "error",
        "total": 10,
        "completed": 5,
        "papers": [
            {
                "doi": "10.xxxx/xxx",
                "title": "...",
                "year": 2021,
                "pdf_status": "✅ Downloaded",
                "supplementary": true,
                "file_size": 1.5,
                "timestamp": "2026-04-21 12:30:45"
            },
            ...
        ]
    }
    """
    if task_id not in download_tasks:
        return jsonify({
            'status': 'error',
            'message': '任务不存在'
        }), 404

    task_data = download_tasks[task_id]
    return jsonify(task_data)


@app.route('/api/download-report/<task_id>', methods=['GET'])
def get_report(task_id):
    """获取下载报告（CSV）"""
    if task_id not in download_tasks:
        return jsonify({
            'status': 'error',
            'message': '任务不存在'
        }), 404

    task_data = download_tasks[task_id]
    report_path = task_data.get('report_path')

    if report_path and os.path.exists(report_path):
        return send_file(
            report_path,
            as_attachment=True,
            download_name=f'download_report_{task_id}.csv'
        )
    else:
        return jsonify({
            'status': 'error',
            'message': '报告不存在'
        }), 404


def download_worker(task_id, dois, output_dir):
    """后台下载工作线程"""
    try:
        # 初始化任务数据
        download_tasks[task_id] = {
            'status': 'processing',
            'total': len(dois),
            'completed': 0,
            'papers': [],
            'output_dir': output_dir,
            'report_path': None,
            'start_time': datetime.now().isoformat()
        }

        results = []

        for idx, doi in enumerate(dois):
            try:
                # 获取元数据
                title, year = get_paper_metadata(doi)

                # 检查是否已下载
                existing = check_paper_already_exists(output_dir, year, title, doi)
                is_already_downloaded = existing is not None

                # 下载 PDF
                pdf_status, pdf_path = download_pdf(doi, output_dir, title, year)

                # 下载补充材料
                supp_status, supp_files = download_supplementary_materials(
                    doi, output_dir, title, year
                )

                # 获取文件大小
                file_size = 0
                if pdf_path and os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path) / (1024 * 1024)

                # 判断下载是否成功
                success = pdf_path is not None and os.path.exists(pdf_path)

                paper_result = {
                    'doi': doi,
                    'title': title,
                    'year': int(year) if year else None,
                    'pdf_status': pdf_status,
                    'pdf_path': pdf_path if pdf_path else None,
                    'supplementary': bool(supp_files),
                    'supplementary_status': supp_status,
                    'supplementary_files': supp_files,
                    'file_size': round(file_size, 1),
                    'success': success,
                    'already_downloaded': is_already_downloaded,
                    'timestamp': datetime.now().isoformat()
                }

                results.append(paper_result)

            except Exception as e:
                results.append({
                    'doi': doi,
                    'title': 'N/A',
                    'year': None,
                    'pdf_status': f'❌ Error: {str(e)[:100]}',
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                })

            # 更新任务进度
            download_tasks[task_id]['papers'] = results
            download_tasks[task_id]['completed'] = idx + 1

        # 生成报告
        report_path = os.path.join(output_dir, f'download_report_{task_id}.csv')
        generate_report(results, report_path)

        # 标记任务完成
        download_tasks[task_id]['status'] = 'completed'
        download_tasks[task_id]['report_path'] = report_path
        download_tasks[task_id]['end_time'] = datetime.now().isoformat()

    except Exception as e:
        download_tasks[task_id]['status'] = 'error'
        download_tasks[task_id]['error'] = str(e)


def generate_report(results, output_path):
    """生成下载报告 CSV"""
    import csv
    try:
        with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'DOI', 'Title', 'Year', 'PDF_Status', 'PDF_Path',
                'File_Size_MB', 'Supplementary', 'Supplementary_Files',
                'Success', 'Already_Downloaded', 'Timestamp'
            ])
            writer.writeheader()
            for paper in results:
                writer.writerow({
                    'DOI': paper.get('doi', ''),
                    'Title': paper.get('title', ''),
                    'Year': paper.get('year', ''),
                    'PDF_Status': paper.get('pdf_status', ''),
                    'PDF_Path': paper.get('pdf_path', ''),
                    'File_Size_MB': paper.get('file_size', ''),
                    'Supplementary': paper.get('supplementary', False),
                    'Supplementary_Files': '; '.join(paper.get('supplementary_files', [])),
                    'Success': paper.get('success', False),
                    'Already_Downloaded': paper.get('already_downloaded', False),
                    'Timestamp': paper.get('timestamp', '')
                })
        print(f"✓ Report saved: {output_path}")
    except Exception as e:
        print(f"✗ Failed to save report: {e}")


# HTML 模板
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>论文下载管理器</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', 'Microsoft YaHei', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2em;
            margin-bottom: 10px;
        }

        .header p {
            opacity: 0.9;
            font-size: 0.95em;
        }

        .controls {
            padding: 30px;
            background: #f9f9f9;
            border-bottom: 1px solid #eee;
        }

        .control-group {
            margin-bottom: 20px;
        }

        .control-group label {
            display: block;
            margin-bottom: 10px;
            font-weight: 600;
            color: #333;
        }

        .input-section {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        textarea {
            flex: 1;
            min-width: 300px;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            resize: vertical;
            min-height: 120px;
        }

        input[type="text"] {
            flex: 1;
            min-width: 200px;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-size: 0.95em;
        }

        input[type="text"]:focus,
        textarea:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 5px rgba(102, 126, 234, 0.2);
        }

        .button-group {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }

        button {
            padding: 12px 25px;
            border: none;
            border-radius: 5px;
            font-size: 0.95em;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            flex: 1;
            min-width: 150px;
        }

        .btn-primary:hover:not(:disabled) {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }

        .btn-primary:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .btn-secondary {
            background: white;
            color: #667eea;
            border: 1px solid #667eea;
        }

        .btn-secondary:hover {
            background: #f5f5f5;
        }

        .status-bar {
            padding: 20px 30px;
            background: #f0f0f0;
            border-bottom: 1px solid #eee;
            display: none;
        }

        .status-bar.active {
            display: block;
        }

        .progress-info {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .progress-text {
            font-weight: 600;
            color: #333;
        }

        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 0.85em;
            font-weight: 600;
        }

        .papers-container {
            padding: 30px;
            max-height: 70vh;
            overflow-y: auto;
        }

        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #999;
        }

        .empty-state-icon {
            font-size: 3em;
            margin-bottom: 20px;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 20px;
        }

        thead {
            background: #f5f5f5;
        }

        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            border-bottom: 2px solid #ddd;
        }

        td {
            padding: 15px;
            border-bottom: 1px solid #eee;
        }

        tr:hover {
            background: #f9f9f9;
        }

        .status-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.85em;
            font-weight: 600;
        }

        .status-success {
            background: #e8f5e9;
            color: #2e7d32;
        }

        .status-warning {
            background: #fff3e0;
            color: #f57c00;
        }

        .status-error {
            background: #ffebee;
            color: #c62828;
        }

        .status-info {
            background: #e3f2fd;
            color: #1565c0;
        }

        .year-cell {
            font-weight: 600;
            color: #667eea;
        }

        .title-cell {
            max-width: 400px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            cursor: help;
        }

        .file-size-cell {
            text-align: right;
            font-family: 'Courier New', monospace;
            color: #666;
        }

        .tooltip {
            position: relative;
            display: inline-block;
            cursor: help;
            border-bottom: 1px dotted #667eea;
        }

        .tooltip .tooltiptext {
            visibility: hidden;
            background-color: #333;
            color: white;
            text-align: left;
            border-radius: 6px;
            padding: 8px 12px;
            position: absolute;
            z-index: 1;
            bottom: 125%;
            left: 0;
            width: 300px;
            font-size: 0.85em;
            white-space: normal;
        }

        .tooltip:hover .tooltiptext {
            visibility: visible;
        }

        .toolbar {
            padding: 20px 30px;
            background: #f9f9f9;
            border-top: 1px solid #eee;
            display: none;
            gap: 10px;
            flex-wrap: wrap;
        }

        .toolbar.active {
            display: flex;
        }

        .stats {
            padding: 20px 30px;
            background: #f5f5f5;
            border-bottom: 1px solid #eee;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 20px;
            display: none;
        }

        .stats.active {
            display: grid;
        }

        .stat-item {
            text-align: center;
        }

        .stat-value {
            font-size: 2em;
            font-weight: 700;
            color: #667eea;
        }

        .stat-label {
            font-size: 0.9em;
            color: #666;
            margin-top: 5px;
        }

        .toast {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #333;
            color: white;
            padding: 15px 25px;
            border-radius: 5px;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.3s ease-out;
            z-index: 1000;
        }

        .toast.success {
            background: #4caf50;
        }

        .toast.error {
            background: #f44336;
        }

        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 1.5em;
            }

            table {
                font-size: 0.85em;
            }

            th, td {
                padding: 10px;
            }

            .title-cell {
                max-width: 200px;
            }

            textarea {
                min-height: 80px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📥 论文下载管理器</h1>
            <p>批量下载学术论文，实时跟踪下载进度</p>
        </div>

        <div class="controls">
            <div class="control-group">
                <label for="doiInput">DOI 列表 (每行一个)</label>
                <textarea id="doiInput" placeholder="粘贴 DOI 列表，每行一个，例如：
10.1038/nphys2439
10.1103/PhysRevLett.92.185001
10.3390/physics2010007"></textarea>
            </div>

            <div class="control-group">
                <label for="outputDir">输出目录</label>
                <input type="text" id="outputDir" value="downloaded_papers" placeholder="输出目录路径">
            </div>

            <div class="button-group">
                <button class="btn-primary" id="startBtn" onclick="startDownload()">
                    🚀 开始下载
                </button>
                <button class="btn-secondary" id="clearBtn" onclick="clearInput()">
                    🗑️ 清空
                </button>
                <button class="btn-secondary" id="downloadReportBtn" onclick="downloadReport()" style="display: none;">
                    📊 下载报告
                </button>
            </div>
        </div>

        <div class="status-bar" id="statusBar">
            <div class="progress-info">
                <span class="progress-text" id="progressText">初始化...</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill" style="width: 0%;">0%</div>
            </div>
        </div>

        <div class="stats" id="stats">
            <div class="stat-item">
                <div class="stat-value" id="statTotal">0</div>
                <div class="stat-label">总论文数</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statSuccess">0</div>
                <div class="stat-label">成功</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statAlready">0</div>
                <div class="stat-label">已存在</div>
            </div>
            <div class="stat-item">
                <div class="stat-value" id="statSupp">0</div>
                <div class="stat-label">有补充文件</div>
            </div>
        </div>

        <div class="papers-container" id="papersContainer">
            <div class="empty-state">
                <div class="empty-state-icon">📋</div>
                <div>粘贴 DOI 列表并点击"开始下载"来启动下载任务</div>
            </div>
        </div>

        <div class="toolbar" id="toolbar">
            <button class="btn-secondary" id="downloadReportBtn2" onclick="downloadReport()">
                📊 下载报告
            </button>
            <button class="btn-secondary" id="refreshBtn" onclick="refreshTable()">
                🔄 刷新
            </button>
        </div>
    </div>

    <script>
        let currentTaskId = null;
        let autoRefreshInterval = null;

        async function startDownload() {
            const doiInput = document.getElementById('doiInput').value.trim();
            const outputDir = document.getElementById('outputDir').value.trim();

            if (!doiInput) {
                showToast('请粘贴 DOI 列表', 'error');
                return;
            }

            const dois = doiInput.split('\\n')
                .map(d => d.trim())
                .filter(d => d && !d.startsWith('#'));

            if (dois.length === 0) {
                showToast('未找到有效的 DOI', 'error');
                return;
            }

            try {
                document.getElementById('startBtn').disabled = true;

                const response = await fetch('/api/download-start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ dois, output_dir: outputDir })
                });

                const data = await response.json();

                if (data.status === 'success') {
                    currentTaskId = data.task_id;
                    showToast(`✅ ${data.message}`, 'success');

                    // 显示进度条
                    document.getElementById('statusBar').classList.add('active');
                    document.getElementById('stats').classList.add('active');
                    document.getElementById('toolbar').classList.add('active');
                    document.getElementById('papersContainer').innerHTML = '';

                    // 自动刷新进度
                    autoRefreshInterval = setInterval(() => {
                        refreshProgress();
                    }, 1000);

                    // 立即刷新一次
                    refreshProgress();
                } else {
                    showToast(`❌ ${data.message}`, 'error');
                }
            } catch (error) {
                showToast(`错误: ${error.message}`, 'error');
            } finally {
                document.getElementById('startBtn').disabled = false;
            }
        }

        async function refreshProgress() {
            if (!currentTaskId) return;

            try {
                const response = await fetch(`/api/download-progress/${currentTaskId}`);
                const data = await response.json();

                if (data.status === 'error') {
                    clearInterval(autoRefreshInterval);
                    showToast('任务已结束或出错', 'error');
                    return;
                }

                // 更新进度条
                const { total, completed, papers, status } = data;
                const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

                document.getElementById('progressFill').style.width = percent + '%';
                document.getElementById('progressFill').textContent = percent + '%';
                document.getElementById('progressText').textContent =
                    `进度: ${completed}/${total} - ${status === 'completed' ? '✅ 已完成' : '⏳ 下载中...'}`;

                // 更新表格
                renderTable(papers);

                // 更新统计信息
                updateStats(papers);

                // 如果完成，停止自动刷新
                if (status === 'completed') {
                    clearInterval(autoRefreshInterval);
                    document.getElementById('downloadReportBtn').style.display = 'inline-block';
                    document.getElementById('downloadReportBtn2').style.display = 'inline-block';
                }
            } catch (error) {
                console.error('更新进度失败:', error);
            }
        }

        function renderTable(papers) {
            if (papers.length === 0) return;

            let html = `
                <table>
                    <thead>
                        <tr>
                            <th>年份</th>
                            <th>标题</th>
                            <th>下载状态</th>
                            <th>文件大小</th>
                            <th>补充文件</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            papers.forEach(paper => {
                const year = paper.year || 'N/A';
                const title = paper.title || 'N/A';
                const titlePreview = title.length > 50 ? title.substring(0, 50) + '...' : title;

                let statusClass = 'status-info';
                let statusIcon = '⏳';

                if (paper.success) {
                    statusClass = paper.already_downloaded ? 'status-warning' : 'status-success';
                    statusIcon = '✅';
                } else if (paper.error) {
                    statusClass = 'status-error';
                    statusIcon = '❌';
                }

                const suppBadge = paper.supplementary
                    ? '<span class="status-badge status-success">✅ 有</span>'
                    : '<span class="status-badge">无</span>';

                const fileSize = paper.file_size ? paper.file_size.toFixed(1) + ' MB' : '-';

                html += `
                    <tr>
                        <td class="year-cell">${year}</td>
                        <td class="title-cell">
                            <span class="tooltip">
                                ${titlePreview}
                                <span class="tooltiptext">${title}</span>
                            </span>
                        </td>
                        <td>
                            <span class="status-badge ${statusClass}">
                                ${statusIcon} ${paper.pdf_status}
                            </span>
                        </td>
                        <td class="file-size-cell">${fileSize}</td>
                        <td>${suppBadge}</td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
            `;

            document.getElementById('papersContainer').innerHTML = html;
        }

        function updateStats(papers) {
            const total = papers.length;
            const success = papers.filter(p => p.success && !p.already_downloaded).length;
            const already = papers.filter(p => p.already_downloaded).length;
            const supp = papers.filter(p => p.supplementary).length;

            document.getElementById('statTotal').textContent = total;
            document.getElementById('statSuccess').textContent = success;
            document.getElementById('statAlready').textContent = already;
            document.getElementById('statSupp').textContent = supp;
        }

        function refreshTable() {
            if (currentTaskId) {
                refreshProgress();
            }
        }

        async function downloadReport() {
            if (!currentTaskId) {
                showToast('没有可用的报告', 'error');
                return;
            }

            try {
                window.location.href = `/api/download-report/${currentTaskId}`;
                showToast('📊 报告下载开始', 'success');
            } catch (error) {
                showToast(`错误: ${error.message}`, 'error');
            }
        }

        function clearInput() {
            document.getElementById('doiInput').value = '';
            document.getElementById('doiInput').focus();
        }

        function showToast(message, type = 'info') {
            const toast = document.createElement('div');
            toast.className = `toast ${type}`;
            toast.textContent = message;
            document.body.appendChild(toast);
            setTimeout(() => {
                toast.style.animation = 'slideIn 0.3s ease-out reverse';
                setTimeout(() => document.body.removeChild(toast), 300);
            }, 3000);
        }

        // 页面加载时的初始化
        window.addEventListener('beforeunload', () => {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
            }
        });
    </script>
</body>
</html>"""


if __name__ == '__main__':
    print("🌐 Starting Paper Download Manager at http://localhost:5003")
    print("📊 Open in browser to download papers with real-time progress tracking")
    app.run(debug=False, port=5003, threaded=True)
