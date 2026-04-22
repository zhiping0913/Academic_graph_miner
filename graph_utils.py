import networkx as nx


def calculate_jaccard(list_a, list_b):
    set_a, set_b = set(list_a), set(list_b)
    if not set_a or not set_b:
        return 0.0
    return round(len(set_a & set_b) / len(set_a | set_b), 4)


def extract_subgraph(db, seed_dois, max_forward_dist=1, max_backward_dist=1):
    """Extract directed subgraph centered on seeds within max_forward_dist and max_backward_dist hops.
    If a direction has 0 layers, it won't expand in that direction."""
    G = nx.DiGraph()
    seeds = [d.lower() for d in seed_dois]

    # Collect nodes reachable via forward references
    nodes_forward = set(seeds)
    if max_forward_dist > 0:
        current_layer = set(seeds)
        for _ in range(max_forward_dist):
            next_layer = set()
            for node in current_layer:
                if node in db:
                    neighbors = [e['doi'] for e in db[node].get('classified_forward', [])]
                    for n in neighbors:
                        if n not in nodes_forward:
                            nodes_forward.add(n)
                            next_layer.add(n)
            current_layer = next_layer

    # Collect nodes reachable via backward references
    nodes_backward = set(seeds)
    if max_backward_dist > 0:
        current_layer = set(seeds)
        for _ in range(max_backward_dist):
            next_layer = set()
            for node in current_layer:
                if node in db:
                    neighbors = [e['doi'] for e in db[node].get('classified_backward', [])]
                    for n in neighbors:
                        if n not in nodes_backward:
                            nodes_backward.add(n)
                            next_layer.add(n)
            current_layer = next_layer

    # Combine both directions
    nodes_in_range = nodes_forward | nodes_backward

    for node_doi in nodes_in_range:
        if node_doi not in db:
            continue
        data = db[node_doi]
        G.add_node(node_doi, **data.get('metadata', {}), is_seed=(node_doi in seeds))
        for entry in data.get('classified_forward', []) + data.get('classified_backward', []):
            if entry['doi'] in nodes_in_range:
                G.add_edge(node_doi, entry['doi'], weight=entry['coefficient'])

    return G


def compute_jaccard_to_seeds(db, node_doi, seed_dois):
    """Return list of {doi, jaccard} dicts comparing node to each seed via backward refs."""
    node_backward = db.get(node_doi, {}).get('backward', [])
    result = []
    for seed in seed_dois:
        seed_backward = db.get(seed.lower(), {}).get('backward', [])
        result.append({
            'doi': seed,
            'jaccard': calculate_jaccard(node_backward, seed_backward)
        })
    return result
