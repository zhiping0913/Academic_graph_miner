#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Data Browser - Flask API for browsing and exporting papers.

All DB access goes through db_sqlite (split-by-year layout). The home-page
listing only loads one year at a time (default = current year) so initial
render is fast even with 144K+ papers in the index. Similarity ranking against
a seed paper is delegated to similarity_search.find_similar, which scans every
year DB in parallel.
"""

import os
import tempfile
from datetime import datetime
from flask import Flask, jsonify, send_file, request

from backend import OUTPUT_PATH
from db_sqlite import (
    get_paper,
    upsert_paper,
    get_metadata,
    get_metadata_batch,
    search_metadata,
    get_citation_counts,
    find_citing_dois,
    list_papers_paginated,
)
from data_export import export_to_json, export_to_csv, export_to_txt
from fitch_citations import fetch_combined_data
from similarity_search import find_similar


app = Flask(__name__, static_folder=OUTPUT_PATH)

DEFAULT_YEAR = datetime.now().year   # 2026 right now; auto-adjusts


def _build_listing_items(meta_rows: list[dict]) -> list[dict]:
    """Add forward/backward counts to a page of metadata rows."""
    dois = [m["doi"] for m in meta_rows]
    counts = get_citation_counts(dois) if dois else {}
    items = []
    for m in meta_rows:
        meta = m["metadata"]
        c = counts.get(m["doi"], {"forward": 0, "backward": 0})
        items.append({
            "doi": m["doi"],
            "title": meta.get("title", "N/A"),
            "year": meta.get("year"),
            "journal": meta.get("journal", ""),
            "authors_count": len(meta.get("authors", [])),
            "forward_count": c["forward"],
            "backward_count": c["backward"],
        })
    return items


# ---------------------------------------------------------------------------
# /api/papers — list / filter / rank-by-similarity
# ---------------------------------------------------------------------------

@app.route('/api/papers', methods=['GET'])
def get_papers_list():
    """List papers with pagination, search, year filter, and optional
    similarity ranking against a seed (ref_doi).

    Query params:
      - page, per_page
      - search        substring (DOI or title)
      - year_min, year_max
      - ref_doi       seed for similarity ranking (Jaccard, "both" direction)
      - similarity_min
      - sort_by       similarity_desc/asc, year_desc/asc, title_asc

    Defaults: when no year filter is given the listing shows only papers from
    DEFAULT_YEAR (the current year) to keep the initial load fast. A
    similarity ranking (ref_doi) always scans the full DB regardless.
    """
    try:
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(500, max(10, int(request.args.get('per_page', 50))))
        search = request.args.get('search', '').lower()
        year_min = request.args.get('year_min')
        year_max = request.args.get('year_max')
        ref_doi = (request.args.get('ref_doi') or '').strip()
        similarity_min = float(request.args.get('similarity_min') or 0)
        sort_by = request.args.get('sort_by', '')

        year_min = int(year_min) if year_min else None
        year_max = int(year_max) if year_max else None

        # ---- similarity ranking path: full-library scan via similarity_search
        if ref_doi:
            top_n = max(per_page * 5, 200)  # rank broadly, paginate locally
            hits = find_similar(
                ref_doi,
                year_min=year_min,
                year_max=year_max,
                top_n=top_n,
                direction="both",
            )
            # Apply search filter on top of the ranked list
            filtered = []
            for h in hits:
                if similarity_min and h["similarity"] < similarity_min:
                    continue
                if search and not (
                    search in (h["doi"] or "").lower()
                    or search in (h["title"] or "").lower()
                ):
                    continue
                filtered.append({
                    "doi": h["doi"],
                    "title": h["title"] or "N/A",
                    "year": h["year"],
                    "journal": h["journal"] or "",
                    "authors_count": 0,           # not loaded in similarity path
                    "forward_count": h["citation_count"],
                    "backward_count": 0,
                    "similarity": h["similarity"],
                })

            if sort_by == 'similarity_asc':
                filtered.sort(key=lambda x: (x['similarity'], x['year'] or 0))
            elif sort_by == 'year_desc':
                filtered.sort(key=lambda x: (-(x['year'] or 0), x['title']))
            elif sort_by == 'year_asc':
                filtered.sort(key=lambda x: ((x['year'] or 0), x['title']))
            elif sort_by == 'title_asc':
                filtered.sort(key=lambda x: x['title'])
            # else: keep similarity_desc (already sorted by find_similar)

            total = len(filtered)
            start = (page - 1) * per_page
            page_papers = filtered[start:start + per_page]
            return jsonify({
                'status': 'success',
                'total': total,
                'total_pages': (total + per_page - 1) // per_page,
                'page': page,
                'per_page': per_page,
                'papers': page_papers,
            })

        # ---- plain listing path: SQL-paginated, only the page is read
        effective_year_min = year_min if year_min is not None else DEFAULT_YEAR
        effective_year_max = year_max if year_max is not None else DEFAULT_YEAR
        meta_rows, total = list_papers_paginated(
            year_min=effective_year_min,
            year_max=effective_year_max,
            search=search,
            sort_by=sort_by or 'year_desc',
            page=page,
            per_page=per_page,
        )
        page_papers = _build_listing_items(meta_rows)
        return jsonify({
            'status': 'success',
            'total': total,
            'total_pages': (total + per_page - 1) // per_page,
            'page': page,
            'per_page': per_page,
            'papers': page_papers,
            'year_range': [effective_year_min, effective_year_max],
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# /api/search-papers — autocomplete in the seed-picker
# ---------------------------------------------------------------------------

@app.route('/api/search-papers', methods=['GET'])
def search_papers():
    """SQL-backed search on doi + title (no citation load)."""
    try:
        search = (request.args.get('search') or '').strip()
        if len(search) < 2:
            return jsonify({'status': 'success', 'papers': []})

        hits = search_metadata(search, limit=20)
        results = [
            {
                'doi': h['doi'],
                'title': h['metadata'].get('title', 'N/A'),
                'year': h['metadata'].get('year'),
                'journal': h['metadata'].get('journal', ''),
            }
            for h in hits
        ]
        return jsonify({'status': 'success', 'papers': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# /api/citing-papers — reverse lookup (who cites target)
# ---------------------------------------------------------------------------

@app.route('/api/citing-papers', methods=['GET'])
def get_citing_papers():
    try:
        target_doi = (request.args.get('doi') or '').strip()
        if not target_doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400
        if get_metadata(target_doi) is None:
            return jsonify({'status': 'error', 'message': '论文不存在'}), 404

        citer_dois = find_citing_dois(target_doi, direction='forward')
        if not citer_dois:
            return jsonify({'status': 'success', 'papers': [], 'total': 0})

        meta = get_metadata_batch(citer_dois)
        counts = get_citation_counts(citer_dois)
        papers = []
        for doi in citer_dois:
            m = meta.get(doi, {}).get('metadata', {})
            c = counts.get(doi, {'forward': 0, 'backward': 0})
            papers.append({
                'doi': doi,
                'title': m.get('title', 'N/A'),
                'year': m.get('year'),
                'journal': m.get('journal', ''),
                'authors_count': len(m.get('authors', [])),
                'forward_count': c['forward'],
                'backward_count': c['backward'],
            })
        papers.sort(key=lambda x: (-(x['year'] or 0), x['title']))
        return jsonify({'status': 'success', 'papers': papers, 'total': len(papers)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# /api/reference-papers — target's own reference list
# ---------------------------------------------------------------------------

@app.route('/api/reference-papers', methods=['GET'])
def get_reference_papers():
    try:
        target_doi = (request.args.get('doi') or '').strip()
        if not target_doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400

        target_paper = get_paper(target_doi)
        if target_paper is None:
            return jsonify({'status': 'error', 'message': '论文不存在'}), 404

        ref_dois = target_paper.get('backward', [])
        if not ref_dois:
            return jsonify({'status': 'success', 'papers': [], 'total': 0})

        meta = get_metadata_batch(ref_dois)
        # Only return refs that exist in our DB (preserves prior behavior)
        existing = [d for d in ref_dois if d in meta]
        counts = get_citation_counts(existing)

        papers = []
        for doi in existing:
            m = meta[doi]['metadata']
            c = counts.get(doi, {'forward': 0, 'backward': 0})
            papers.append({
                'doi': doi,
                'title': m.get('title', 'N/A'),
                'year': m.get('year'),
                'journal': m.get('journal', ''),
                'authors_count': len(m.get('authors', [])),
                'forward_count': c['forward'],
                'backward_count': c['backward'],
            })
        papers.sort(key=lambda x: (-(x['year'] or 0), x['title']))
        return jsonify({'status': 'success', 'papers': papers, 'total': len(papers)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# /api/fetch-paper — pull missing paper from upstream APIs
# ---------------------------------------------------------------------------

@app.route('/api/fetch-paper', methods=['POST'])
def fetch_missing_paper():
    try:
        data = request.get_json() or {}
        doi = (data.get('doi') or '').strip().lower()
        if not doi:
            return jsonify({'status': 'error', 'message': '请提供 DOI'}), 400

        existing = get_paper(doi)
        if existing is not None:
            return jsonify({
                'status': 'success',
                'message': '论文已存在于数据库',
                'found': True,
                'paper': existing,
            })

        print(f"🔍 fetching {doi} from upstream APIs")
        paper_data = fetch_combined_data(doi)
        if not paper_data:
            return jsonify({
                'status': 'error',
                'message': f'无法获取论文数据: {doi}',
                'found': False,
            }), 404

        print(f"💾 saving {doi}")
        upsert_paper(paper_data)

        return jsonify({
            'status': 'success',
            'message': f'成功获取并保存论文: {doi}',
            'found': True,
            'paper': paper_data,
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'获取论文失败: {str(e)}',
        }), 500


# ---------------------------------------------------------------------------
# /api/export — TXT/CSV/JSON export of a selected DOI list
# ---------------------------------------------------------------------------

@app.route('/api/export', methods=['POST'])
def export_papers():
    try:
        data = request.get_json() or {}
        dois = data.get('dois', [])
        export_format = data.get('format', 'json')
        if not dois:
            return jsonify({'status': 'error', 'message': 'No DOIs selected'}), 400

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
            temp_path = tmp.name

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if export_format == 'json':
            export_to_json(dois, temp_path)
            filename, mimetype = f'papers_{ts}.json', 'application/json'
        elif export_format == 'csv':
            export_to_csv(dois, temp_path)
            filename, mimetype = f'papers_{ts}.csv', 'text/csv'
        elif export_format == 'txt-doi':
            export_to_txt(dois, temp_path, key_list=['doi'])
            filename, mimetype = f'papers_doi_list_{ts}.txt', 'text/plain'
        elif export_format == 'txt-detail':
            export_to_txt(dois, temp_path,
                          key_list=['doi', 'title', 'year', 'journal', 'authors'])
            filename, mimetype = f'papers_detail_{ts}.txt', 'text/plain'
        else:
            return jsonify({'status': 'error',
                            'message': f'Unknown format: {export_format}'}), 400

        return send_file(temp_path, as_attachment=True,
                         download_name=filename, mimetype=mimetype)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# Static page
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_file(os.path.join(OUTPUT_PATH, 'data_browser.html'))


if __name__ == '__main__':
    print(f"🌐 Starting Data Browser at http://localhost:5001")
    print(f"📊 Default year for initial load: {DEFAULT_YEAR}")
    app.run(debug=True, port=5001)
