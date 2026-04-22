"""
Flask backend for interactive_graph.html.
Usage: python graph_server.py  (then open http://localhost:5000)
"""
import json
import os
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from graph_utils import extract_subgraph, compute_jaccard_to_seeds
from backend import OUTPUT_PATH
from db_sqlite import load_db, upsert_paper
from fitch_citations import fetch_combined_data

app = Flask(__name__, static_folder=OUTPUT_PATH)


@app.route('/')
def index():
    return send_from_directory(OUTPUT_PATH, 'interactive_graph.html')


@app.route('/api/graph', methods=['POST'])
def api_graph():
    body = request.get_json(force=True)
    raw_dois = body.get('seed_dois', [])
    seed_dois = [d.strip().lower() for d in raw_dois if d.strip()]
    max_forward_dist = min(int(body.get('max_forward_dist', 1)), 5)
    max_backward_dist = min(int(body.get('max_backward_dist', 1)), 5)

    if not seed_dois:
        return jsonify({'error': '请至少提供一个 DOI'}), 400

    db = load_db()

    missing = [d for d in seed_dois if d not in db]
    if missing:
        return jsonify({'error': f'以下 DOI 不在数据库中: {", ".join(missing)}'}), 404

    G = extract_subgraph(db, seed_dois, max_forward_dist, max_backward_dist)

    nodes = []
    for node_doi, attrs in G.nodes(data=True):
        jaccard = compute_jaccard_to_seeds(db, node_doi, seed_dois)
        nodes.append({
            'id': node_doi,
            'title': attrs.get('title') or node_doi,
            'year': attrs.get('year'),
            'authors': attrs.get('authors', []),
            'journal': attrs.get('journal'),
            'is_seed': bool(attrs.get('is_seed')),
            'in_degree': G.in_degree(node_doi),
            'jaccard': jaccard,
        })

    edges = [
        {'from': u, 'to': v, 'weight': round(d.get('weight', 0), 4)}
        for u, v, d in G.edges(data=True)
    ]

    return jsonify({'nodes': nodes, 'edges': edges, 'seed_dois': seed_dois})


@app.route('/api/save-graph', methods=['POST'])
def api_save_graph():
    """Save the current graph as an HTML file."""
    body = request.get_json(force=True)
    nodes = body.get('nodes', [])
    edges = body.get('edges', [])

    if not nodes:
        return jsonify({'error': '没有节点数据'}), 400

    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'graph_{timestamp}.html'
    filepath = os.path.join(OUTPUT_PATH, filename)

    # Generate HTML content
    html_content = generate_graph_html(nodes, edges)

    # Save to file
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return jsonify({'success': True, 'filename': filename, 'path': filepath})


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
        db = load_db()
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


def generate_graph_html(nodes, edges):
    """Generate an HTML file with the graph visualization."""
    nodes_json = json.dumps(nodes)
    edges_json = json.dumps(edges)

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>学术图谱</title>
    <script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            background: #1a1a1a;
            color: #e0e0e0;
            font-family: 'Segoe UI', system-ui, sans-serif;
            height: 100vh;
            overflow: hidden;
        }}
        #network {{
            width: 100%;
            height: 100%;
            background: #1a1a1a;
        }}
        #info {{
            position: fixed;
            top: 10px;
            left: 10px;
            background: rgba(34, 34, 34, 0.9);
            padding: 10px 15px;
            border-radius: 5px;
            font-size: 12px;
            color: #888;
        }}
    </style>
</head>
<body>
    <div id="network"></div>
    <div id="info">节点: {len(nodes)} | 边: {len(edges)}</div>
    <script>
        var nodes = new vis.DataSet({nodes_json});
        var edges = new vis.DataSet({edges_json});

        var options = {{
            nodes: {{ shape: 'dot', scaling: {{ min: 8, max: 60 }}, borderWidth: 1.5 }},
            edges: {{
                smooth: {{ type: 'dynamic' }},
                scaling: {{ min: 1, max: 10 }},
                selectionWidth: 2,
            }},
            physics: {{
                stabilization: {{ iterations: 200, updateInterval: 25 }},
                barnesHut: {{ gravitationalConstant: -8000, springLength: 130, springConstant: 0.04, damping: 0.09 }},
            }},
            interaction: {{ hover: true, tooltipDelay: 150, navigationButtons: false, keyboard: true }},
            layout: {{ improvedLayout: true }},
        }};

        var network = new vis.Network(
            document.getElementById('network'),
            {{ nodes: nodes, edges: edges }},
            options
        );
    </script>
</body>
</html>"""
    return html


if __name__ == '__main__':
    from db_sqlite import DB_PATH as _db_path
    print(f"数据库: {_db_path}")
    print("访问 http://localhost:5000 查看交互图谱")
    app.run(debug=False, port=5000)
