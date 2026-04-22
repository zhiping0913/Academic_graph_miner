# 📐 Graph Utilities Module Reference (graph_utils.py)

**File**: `graph_utils.py` (73 lines)  
**Purpose**: Graph theory algorithms and similarity calculations for citation networks  
**Status**: Production-ready

---

## 🎯 Quick Start

### Basic Usage

```python
from graph_utils import calculate_jaccard, extract_subgraph, compute_jaccard_to_seeds
from db_sqlite import load_db
import networkx as nx

# Load database
db = load_db()

# Calculate Jaccard similarity between two papers
similarity = calculate_jaccard(
    ["ref1", "ref2", "ref3"],
    ["ref2", "ref3", "ref4"]
)
print(f"Similarity: {similarity}")  # 0.5

# Extract subgraph around seed papers
G = extract_subgraph(
    db=db,
    seed_dois=["10.1038/nphys2439"],
    max_forward_dist=1,
    max_backward_dist=1
)
print(f"Nodes: {G.number_of_nodes()}")
print(f"Edges: {G.number_of_edges()}")

# Find papers most similar to a seed
similarities = compute_jaccard_to_seeds(
    db=db,
    node_doi="10.1103/PhysRevE.101.033202",
    seed_dois=["10.1038/nphys2439"]
)
for entry in similarities:
    print(f"{entry['doi']}: Jaccard = {entry['jaccard']:.2f}")
```

---

## 🔧 Core Functions

### Similarity Calculation

#### `calculate_jaccard(list_a: List, list_b: List) -> float`

**Purpose**: Compute Jaccard similarity coefficient between two citation lists

**Formula**:
```
Jaccard = |A ∩ B| / |A ∪ B|
        = (# shared citations) / (# unique citations)
```

**Parameters**:
- `list_a` (List): First list of references/citations (e.g., DOIs)
- `list_b` (List): Second list of references/citations

**Returns**: `float` between 0.0 and 1.0
- 0.0 = completely different (no shared citations)
- 0.5 = moderate similarity (50% citation overlap)
- 1.0 = identical (all citations shared)

**Performance**: ~0.0079ms per pair (extremely fast)

**Example**:
```python
# Paper A cites {ref1, ref2, ref3, ref4}
# Paper B cites {ref2, ref3, ref5}
# Shared: {ref2, ref3}, Unique: {ref1, ref2, ref3, ref4, ref5}
# Jaccard: 2/5 = 0.4

similarity = calculate_jaccard(
    ["ref1", "ref2", "ref3", "ref4"],
    ["ref2", "ref3", "ref5"]
)
print(similarity)  # 0.4
```

**Interpretation**:
- `> 0.2`: Related papers (similar research)
- `> 0.1`: Potentially related
- `< 0.05`: Unrelated papers
- `0.0`: No citation overlap

---

### Subgraph Extraction

#### `extract_subgraph(db: Dict, seed_dois: List[str], max_forward_dist: int, max_backward_dist: int) -> nx.DiGraph`

**Purpose**: Extract a directed subgraph of papers around seed DOIs

**Graph Definition**:
- **Nodes**: Papers (with attributes: title, year, is_seed)
- **Edges**: Citation relationships (with weight: Jaccard coefficient if available)
- **Direction**: Forward = "cites", Backward = "cited by"

**Parameters**:
- `db` (Dict): Loaded database from `load_db()`
- `seed_dois` (List[str]): Starting papers, e.g., `["10.1038/nphys2439"]`
- `max_forward_dist` (int): How many hops forward (outgoing citations)
- `max_backward_dist` (int): How many hops backward (incoming citations)

**Returns**: `networkx.DiGraph` with:
- Nodes: `{"doi": {"metadata": {...}, "is_seed": bool}}`
- Edges: `{"from": "10.xxx", "to": "10.yyy", "weight": 0.25}` (weight if classified)

**Extraction Algorithm** (BFS):
```
1. Start with seed_dois as queue
2. Explore forward citations (papers this cites):
   - Add reachable papers up to max_forward_dist hops
3. Explore backward citations (papers citing this):
   - Add reachable papers up to max_backward_dist hops
4. Keep only papers found within distance limits
5. Return as NetworkX DiGraph
```

**Performance**: 100-500ms for typical subgraph (10-100 papers)

**Example**:
```python
from graph_utils import extract_subgraph
from db_sqlite import load_db

db = load_db()

# Get 1-hop neighborhood of a paper
G = extract_subgraph(
    db=db,
    seed_dois=["10.1038/nphys2439"],
    max_forward_dist=1,    # Papers this cites
    max_backward_dist=1    # Papers citing this
)

print(f"Subgraph size: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

# Access node attributes
for node in G.nodes():
    node_data = G.nodes[node]
    print(f"{node}: {node_data['metadata']['title']}")

# Access edge weights
for u, v, data in G.edges(data=True):
    print(f"{u} -> {v}: weight={data.get('weight', 'N/A')}")
```

---

#### Subgraph Distance Parameters

| Scenario | max_forward_dist | max_backward_dist | Size | Use Case |
|----------|------------------|------------------|------|----------|
| Direct connections | 1 | 1 | ~50 nodes | Quick overview |
| 2-hop neighborhood | 2 | 2 | ~200 nodes | Related work |
| Full network | 3+ | 3+ | 1000+ nodes | Comprehensive mapping |
| Seed only | 0 | 0 | 1 node | Single paper |

---

### Multi-seed Similarity

#### `compute_jaccard_to_seeds(db: Dict, node_doi: str, seed_dois: List[str]) -> List[Dict]`

**Purpose**: Calculate similarity between one paper and multiple seed papers

**Parameters**:
- `db` (Dict): Loaded database
- `node_doi` (str): Paper to compare, e.g., "10.1103/PhysRevE.101.033202"
- `seed_dois` (List[str]): Reference papers to compare against

**Returns**: List of dicts
```python
[
    {"doi": "10.1038/nphys2439", "jaccard": 0.35},
    {"doi": "10.1234/another", "jaccard": 0.18}
]
```

**Algorithm**:
```
For each seed_doi:
  1. Get backward citations of seed
  2. Get backward citations of node
  3. Compute Jaccard between the two lists
  4. Return result
```

**Performance**: ~10ms per seed (computes independently)

**Example**:
```python
similarities = compute_jaccard_to_seeds(
    db=db,
    node_doi="10.1103/PhysRevE.101.033202",
    seed_dois=["10.1038/nphys2439", "10.1234/other"]
)

# Results
for sim in similarities:
    print(f"{sim['doi']}: {sim['jaccard']:.3f}")
# Output:
# 10.1038/nphys2439: 0.250
# 10.1234/other: 0.085
```

---

## 📊 NetworkX Integration

### Working with Subgraphs

```python
import networkx as nx
from graph_utils import extract_subgraph

# Extract subgraph
G = extract_subgraph(db, ["10.1038/nphys2439"], 1, 1)

# Graph properties
print(f"Density: {nx.density(G):.2%}")
print(f"Diameter: {nx.diameter(G) if nx.is_strongly_connected(G) else 'N/A'}")

# Find most connected nodes
degrees = dict(G.in_degree())
most_cited = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]
print("Most cited papers in subgraph:")
for doi, in_degree in most_cited:
    print(f"  {doi}: cited {in_degree} times")

# Shortest path between papers
seed = "10.1038/nphys2439"
target = list(G.nodes())[-1]  # Pick another paper
try:
    path = nx.shortest_path(G, seed, target)
    print(f"Path from {seed} to {target}: {' → '.join(path)}")
except nx.NetworkXNoPath:
    print("No path found")
```

---

### Visualization-Ready Output

The extracted subgraph can be directly visualized:

```python
import matplotlib.pyplot as plt
from graph_utils import extract_subgraph

G = extract_subgraph(db, ["10.1038/nphys2439"], 1, 1)

# Position nodes using spring layout
pos = nx.spring_layout(G, k=0.5, iterations=50)

# Draw
plt.figure(figsize=(12, 8))
nx.draw_networkx_nodes(G, pos, node_size=300, node_color='lightblue')
nx.draw_networkx_edges(G, pos, edge_color='gray', arrows=True)
nx.draw_networkx_labels(G, pos, font_size=8)
plt.title("Citation Network")
plt.axis('off')
plt.show()
```

---

## 📈 Performance Metrics

| Operation | Time | Notes |
|-----------|------|-------|
| Jaccard calculation | 0.0079ms | Per pair |
| Jaccard 10K pairs | 79ms | Highly parallelizable |
| Subgraph extraction (50 nodes) | 50-100ms | BFS traversal |
| Subgraph extraction (1000 nodes) | 200-500ms | Larger graph |
| Similarity to seeds (10 seeds) | 100ms | ~10ms each |

---

## 🎯 Use Cases

### Use Case 1: Find Related Papers

```python
from graph_utils import compute_jaccard_to_seeds

# "I'm reading paper A, what are similar papers?"
query_doi = "10.1103/PhysRevE.101.033202"
seed_dois = ["10.1038/nphys2439"]  # Reference paper

similarities = compute_jaccard_to_seeds(db, query_doi, seed_dois)
for sim in sorted(similarities, key=lambda x: x['jaccard'], reverse=True):
    if sim['jaccard'] > 0.15:
        print(f"Similar: {sim['doi']} (Jaccard: {sim['jaccard']:.2f})")
```

### Use Case 2: Build Knowledge Graph

```python
from graph_utils import extract_subgraph
import networkx as nx

# Create focused knowledge graph
seeds = ["10.1038/nphys2439", "10.1103/PhysRevE.101.033202"]
G = extract_subgraph(db, seeds, max_forward_dist=2, max_backward_dist=2)

# Analyze structure
print(f"Papers in graph: {G.number_of_nodes()}")
print(f"Connections: {G.number_of_edges()}")
print(f"Average connections: {2*G.number_of_edges()/G.number_of_nodes():.1f}")
```

### Use Case 3: Citation Flow Analysis

```python
# Trace how knowledge flows through citations
import networkx as nx

# Build large subgraph
G = extract_subgraph(db, ["10.1038/nphys2439"], 3, 3)

# Find papers that cite many papers (hubs)
out_degree = dict(G.out_degree())
influential_citers = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:5]

print("Papers citing many others:")
for doi, count in influential_citers:
    meta = db[doi]['metadata']
    print(f"  {meta['title'][:50]}... ({count} citations)")
```

---

## 🔧 Configuration

### Performance Tuning

```python
# For large graphs, consider these optimizations:

# 1. Limit subgraph depth
G = extract_subgraph(db, seeds, max_forward_dist=1, max_backward_dist=1)
# Reduces computation time and memory

# 2. Batch Jaccard calculations
similarities = [
    calculate_jaccard(paper1['backward'], paper2['backward'])
    for paper2 in db.values()
]
# ~100ms for full database

# 3. Use NetworkX algorithms efficiently
# Pre-compute properties once, not repeatedly
in_degrees = dict(G.in_degree())
out_degrees = dict(G.out_degree())
```

---

## 🐛 Common Issues & Solutions

### Issue: Subgraph has only seed node
- **Cause**: Seed papers not in database or distance params too restrictive
- **Solution**: Check `db.get(seed_doi)` and increase max_*_dist

### Issue: Similarity always 0
- **Cause**: Papers have no citation overlap
- **Solution**: Normal for unrelated papers; check seed selection

### Issue: Slow subgraph extraction
- **Cause**: Large max_*_dist values with dense network
- **Solution**: Reduce distances or work with subset of database

---

## 📚 Related Modules

- **db_sqlite.py**: Provides database for graph construction
- **fitch_citations.py**: Mines papers that build the citation network
- **data_browser.py**: Uses graph utilities for similarity calculations
- **graph_server.py**: Visualizes subgraphs as interactive networks

---

## 🚀 Advanced Tips

### Pre-compute Similarity Matrix

```python
# For frequent similarity queries
import numpy as np
from graph_utils import calculate_jaccard

dois = list(db.keys())
n = len(dois)

# Full Jaccard matrix (17K x 17K is large, consider subset)
similarity_matrix = np.zeros((n, n))

for i, doi1 in enumerate(dois):
    for j, doi2 in enumerate(dois[i:], start=i):
        sim = calculate_jaccard(
            db[doi1]['backward'],
            db[doi2]['backward']
        )
        similarity_matrix[i, j] = sim
        similarity_matrix[j, i] = sim  # Symmetric

# Now O(1) similarity lookup instead of O(citations) computation
```

### Parallel Subgraph Extraction

```python
# For multiple independent queries
from concurrent.futures import ThreadPoolExecutor

seeds_list = [
    ["10.1038/nphys2439"],
    ["10.1103/PhysRevE.101.033202"],
    ["10.1234/another"]
]

with ThreadPoolExecutor(max_workers=3) as executor:
    graphs = list(executor.map(
        lambda seeds: extract_subgraph(db, seeds, 1, 1),
        seeds_list
    ))
```

---

**Last Updated**: 2026-04-21  
**Version**: 2.0  
**Status**: ✅ Production-ready  
**Algorithms**: Jaccard, BFS, NetworkX integration ✓
