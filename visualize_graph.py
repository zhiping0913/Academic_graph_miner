from pyvis.network import Network
from graph_utils import extract_subgraph
from backend import OUTPUT_PATH
from db_sqlite import load_db

OUTPUT_FILE = OUTPUT_PATH + "/sub_network.html"

def visualize_subgraph(G, output="sub_network.html"):
    net = Network(height="800px", width="100%", bgcolor="#1a1a1a", font_color="white", directed=True)
    # 自动计算节点大小 (入度)
    for node, attrs in G.nodes(data=True):
        deg = G.in_degree(node)
        net.add_node(node, 
                     label=attrs.get('title', node)[:30], 
                     size=10 + deg*5, 
                     color="#ff3300" if attrs.get('is_seed') else "#00ccff")
    
    for u, v, d in G.edges(data=True):
        net.add_edge(u, v, value=d['weight']*10, color="#555555")
        
    net.show(output, notebook=False)

if __name__ == "__main__":
    db = load_db()
    # 示例：只看这篇文章周围 1 层的内容
    target_seeds = ["10.1088/1367-2630/15/1/015025"]
    sub_g = extract_subgraph(db, target_seeds, max_forward_dist=1, max_backward_dist=1)
    visualize_subgraph(sub_g, output=OUTPUT_FILE)