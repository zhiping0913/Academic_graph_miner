#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Browser - Flask API for browsing and exporting papers from academic_knowledge_graph.db
"""

import json
import os
import tempfile
import csv
from datetime import datetime
from flask import Flask, jsonify, send_file, request
from backend import OUTPUT_PATH, DB_PATH
from db_sqlite import load_db, get_paper, upsert_paper
from data_export import export_to_json, export_to_csv, export_to_txt
from graph_utils import calculate_jaccard
from fitch_citations import fetch_combined_data

app = Flask(__name__, static_folder=OUTPUT_PATH)

# 缓存数据库
_db_cache = None
_db_cache_time = None
_CACHE_DURATION = 300  # 5分钟缓存


def get_cached_db():
    """获取缓存的数据库（每5分钟重新加载一次）"""
    global _db_cache, _db_cache_time
    import time

    current_time = time.time()
    if _db_cache is None or (current_time - _db_cache_time > _CACHE_DURATION):
        print("📦 加载数据库到缓存...")
        _db_cache = load_db()
        _db_cache_time = current_time
        print(f"✓ 缓存完成: {len(_db_cache)} 篇论文")

    return _db_cache


@app.route('/api/papers', methods=['GET'])
def get_papers_list():
    """获取论文列表（支持分页和相似度过滤）

    Query params:
    - page: 页码（默认 1）
    - per_page: 每页数量（默认 50，最大 500）
    - search: 搜索关键词
    - year_min: 最小年份
    - year_max: 最大年份
    - ref_doi: 参考论文 DOI（用于相似度计算）
    - similarity_min: 最小相似度 (0-1)
    - sort_by: 排序方式 (similarity_desc/asc, year_desc/asc, title_asc)
    """
    try:
        # 获取分页参数
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(500, max(10, int(request.args.get('per_page', 50))))
        search = request.args.get('search', '').lower()
        year_min = request.args.get('year_min')
        year_max = request.args.get('year_max')
        ref_doi = request.args.get('ref_doi')
        similarity_min = request.args.get('similarity_min')
        sort_by = request.args.get('sort_by', '')

        # 转换年份参数
        year_min = int(year_min) if year_min else None
        year_max = int(year_max) if year_max else None

        # 转换相似度参数
        similarity_min = float(similarity_min) if similarity_min else 0

        # 获取缓存的数据库
        db = get_cached_db()

        # 获取参考论文的前向引用列表（用于相似度计算）
        ref_forward = []
        if ref_doi:
            ref_paper = db.get(ref_doi)
            if ref_paper:
                ref_forward = ref_paper.get('forward', [])

        # 筛选论文
        filtered_papers = []
        for doi, paper_data in db.items():
            meta = paper_data.get('metadata', {})

            # 搜索过滤
            if search:
                if not (search in meta.get('title', '').lower() or search in doi.lower()):
                    continue

            # 年份过滤
            year = meta.get('year')
            if year_min and year and year < year_min:
                continue
            if year_max and year and year > year_max:
                continue

            # 计算相似度并过滤
            similarity = None
            if ref_doi and ref_forward and doi != ref_doi:
                paper_forward = paper_data.get('forward', [])
                similarity = calculate_jaccard(ref_forward, paper_forward)
                if similarity < similarity_min:
                    continue

            # 添加到结果
            paper_item = {
                'doi': doi,
                'title': meta.get('title', 'N/A'),
                'year': year,
                'journal': meta.get('journal', ''),
                'authors_count': len(meta.get('authors', [])),
                'forward_count': len(paper_data.get('forward', [])),
                'backward_count': len(paper_data.get('backward', []))
            }
            if similarity is not None:
                paper_item['similarity'] = similarity

            filtered_papers.append(paper_item)

        # 排序
        if sort_by == 'similarity_desc' and ref_doi:
            filtered_papers.sort(key=lambda x: (-x.get('similarity', 0), -x['year'] if x['year'] else 0))
        elif sort_by == 'similarity_asc' and ref_doi:
            filtered_papers.sort(key=lambda x: (x.get('similarity', 0), x['year'] if x['year'] else 0))
        elif sort_by == 'year_desc':
            filtered_papers.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title']))
        elif sort_by == 'year_asc':
            filtered_papers.sort(key=lambda x: (x['year'] if x['year'] else 0, x['title']))
        elif sort_by == 'title_asc':
            filtered_papers.sort(key=lambda x: x['title'])
        else:
            # 默认排序（按年份降序，标题升序）
            filtered_papers.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title']))

        # 分页
        total = len(filtered_papers)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        page_papers = filtered_papers[start_idx:end_idx]

        total_pages = (total + per_page - 1) // per_page

        return jsonify({
            'status': 'success',
            'total': total,
            'total_pages': total_pages,
            'page': page,
            'per_page': per_page,
            'papers': page_papers
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/search-papers', methods=['GET'])
def search_papers():
    """搜索参考论文（用于选择相似度对比的参考）

    Query params:
    - search: 搜索关键词（DOI 或标题）
    """
    try:
        search = request.args.get('search', '').lower()

        if len(search) < 2:
            return jsonify({
                'status': 'success',
                'papers': []
            })

        db = get_cached_db()
        results = []

        # 搜索论文
        for doi, paper_data in db.items():
            meta = paper_data.get('metadata', {})
            if search in doi.lower() or search in meta.get('title', '').lower():
                results.append({
                    'doi': doi,
                    'title': meta.get('title', 'N/A'),
                    'year': meta.get('year'),
                    'journal': meta.get('journal', '')
                })

            # 限制返回结果数
            if len(results) >= 20:
                break

        # 按匹配度排序（DOI 完全匹配优先）
        results.sort(key=lambda x: (
            not x['doi'].startswith(search),
            x['title']
        ))

        return jsonify({
            'status': 'success',
            'papers': results
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/citing-papers', methods=['GET'])
def get_citing_papers():
    """获取引用某篇论文的所有文章

    Query params:
    - doi: 要查询的论文 DOI
    """
    try:
        target_doi = request.args.get('doi', '').strip()

        if not target_doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400

        db = get_cached_db()

        # 检查论文是否存在
        if target_doi not in db:
            return jsonify({'status': 'error', 'message': '论文不存在'}), 404

        # 查找所有引用过该论文的文章
        citing_papers = []
        for doi, paper_data in db.items():
            forward_refs = paper_data.get('forward', [])
            if target_doi in forward_refs:
                meta = paper_data.get('metadata', {})
                citing_papers.append({
                    'doi': doi,
                    'title': meta.get('title', 'N/A'),
                    'year': meta.get('year'),
                    'journal': meta.get('journal', ''),
                    'authors_count': len(meta.get('authors', [])),
                    'forward_count': len(forward_refs),
                    'backward_count': len(paper_data.get('backward', []))
                })

        # 按年份降序排序
        citing_papers.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title']))

        return jsonify({
            'status': 'success',
            'papers': citing_papers,
            'total': len(citing_papers)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/reference-papers', methods=['GET'])
def get_reference_papers():
    """获取某篇论文引用的所有文章 (该论文的参考文献)

    Query params:
    - doi: 要查询的论文 DOI
    """
    try:
        target_doi = request.args.get('doi', '').strip()

        if not target_doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400

        db = get_cached_db()

        # 检查论文是否存在
        if target_doi not in db:
            return jsonify({'status': 'error', 'message': '论文不存在'}), 404

        # 获取该论文的 backward (引用的论文)
        target_paper = db[target_doi]
        backward_refs = target_paper.get('backward', [])

        # 查找这些论文的详细信息
        reference_papers = []
        for doi in backward_refs:
            if doi in db:
                paper_data = db[doi]
                meta = paper_data.get('metadata', {})
                reference_papers.append({
                    'doi': doi,
                    'title': meta.get('title', 'N/A'),
                    'year': meta.get('year'),
                    'journal': meta.get('journal', ''),
                    'authors_count': len(meta.get('authors', [])),
                    'forward_count': len(paper_data.get('forward', [])),
                    'backward_count': len(paper_data.get('backward', []))
                })

        # 按年份降序排序
        reference_papers.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title']))

        return jsonify({
            'status': 'success',
            'papers': reference_papers,
            'total': len(reference_papers)
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/fetch-paper', methods=['POST'])
def fetch_missing_paper():
    """如果数据库中不存在某个 DOI，则实时获取并保存

    Request body:
    {
        "doi": "10.1038/nphys2439"
    }
    """
    try:
        data = request.get_json()
        doi = data.get('doi', '').strip().lower()

        if not doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400

        # 检查数据库是否已存在
        db = get_cached_db()
        if doi in db:
            return jsonify({
                'status': 'success',
                'message': '论文已存在于数据库',
                'found': True,
                'paper': db[doi]
            })

        # 从 API 获取论文数据
        print(f"🔍 正在从 API 获取论文: {doi}")
        paper_data = fetch_combined_data(doi)

        if not paper_data:
            return jsonify({
                'status': 'error',
                'message': f'无法获取论文数据: {doi}',
                'found': False
            }), 404

        # 保存到数据库
        print(f"💾 正在保存论文到数据库: {doi}")
        upsert_paper(paper_data)

        # 重新加载缓存
        global _db_cache, _db_cache_time
        _db_cache = None
        _db_cache_time = None
        db = get_cached_db()

        return jsonify({
            'status': 'success',
            'message': f'成功获取并保存论文: {doi}',
            'found': True,
            'paper': paper_data
        })

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'获取论文失败: {str(e)}'
        }), 500


@app.route('/api/export', methods=['POST'])
def export_papers():
    """导出选中的论文

    Request body:
    {
        "dois": ["10.1038/nphys2439", ...],
        "format": "json" | "csv" | "txt-doi" | "txt-detail"
    }
    """
    try:
        data = request.get_json()
        dois = data.get('dois', [])
        export_format = data.get('format', 'json')

        if not dois:
            return jsonify({'status': 'error', 'message': 'No DOIs selected'}), 400

        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            temp_path = tmp.name

        try:
            if export_format == 'json':
                export_to_json(dois, temp_path)
                filename = f'papers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
                mimetype = 'application/json'

            elif export_format == 'csv':
                export_to_csv(dois, temp_path)
                filename = f'papers_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                mimetype = 'text/csv'

            elif export_format == 'txt-doi':
                export_to_txt(dois, temp_path, key_list=['doi'])
                filename = f'papers_doi_list_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                mimetype = 'text/plain'

            elif export_format == 'txt-detail':
                export_to_txt(dois, temp_path, key_list=['doi', 'title', 'year', 'journal', 'authors'])
                filename = f'papers_detail_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
                mimetype = 'text/plain'

            else:
                return jsonify({'status': 'error', 'message': f'Unknown format: {export_format}'}), 400

            return send_file(
                temp_path,
                as_attachment=True,
                download_name=filename,
                mimetype=mimetype
            )

        finally:
            # 注意：send_file 会在发送后清理文件
            pass

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/')
def index():
    """返回数据浏览器页面"""
    return send_file(os.path.join(OUTPUT_PATH, 'data_browser.html'))


if __name__ == '__main__':
    print("🌐 Starting Data Browser at http://localhost:5001")
    print("📊 Open in browser to view and export papers from the knowledge graph")
    app.run(debug=True, port=5001)
