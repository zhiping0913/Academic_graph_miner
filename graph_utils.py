import networkx as nx


def calculate_jaccard(list_a, list_b):
    set_a, set_b = set(list_a), set(list_b)
    if not set_a or not set_b:
        return 0.0
    return round(len(set_a & set_b) / len(set_a | set_b), 4)


def extract_subgraph(db, seed_dois, max_citation_dist=1, max_reference_dist=1):
    """Extract directed subgraph centered on seeds.

    max_citation_dist  — hops along the Citation edge set (incoming citers).
    max_reference_dist — hops along the Reference edge set (outgoing refs).
    A distance of 0 disables expansion in that direction.
    """
    G = nx.DiGraph()
    seeds = [d.lower() for d in seed_dois]

    # Citation side: papers citing the seeds (incoming).
    nodes_citation = set(seeds)
    if max_citation_dist > 0:
        current_layer = set(seeds)
        for _ in range(max_citation_dist):
            next_layer = set()
            for node in current_layer:
                if node in db:
                    neighbors = [e['doi'] for e in db[node].get('classified_citation', [])]
                    for n in neighbors:
                        if n not in nodes_citation:
                            nodes_citation.add(n)
                            next_layer.add(n)
            current_layer = next_layer

    # Reference side: papers the seeds cite (outgoing).
    nodes_reference = set(seeds)
    if max_reference_dist > 0:
        current_layer = set(seeds)
        for _ in range(max_reference_dist):
            next_layer = set()
            for node in current_layer:
                if node in db:
                    neighbors = [e['doi'] for e in db[node].get('classified_reference', [])]
                    for n in neighbors:
                        if n not in nodes_reference:
                            nodes_reference.add(n)
                            next_layer.add(n)
            current_layer = next_layer

    nodes_in_range = nodes_citation | nodes_reference

    for node_doi in nodes_in_range:
        if node_doi not in db:
            continue
        data = db[node_doi]
        G.add_node(node_doi, **data.get('metadata', {}), is_seed=(node_doi in seeds))
        for entry in data.get('classified_citation', []) + data.get('classified_reference', []):
            if entry['doi'] in nodes_in_range:
                G.add_edge(node_doi, entry['doi'], weight=entry['coefficient'])

    return G


def compute_jaccard_to_seeds(db, node_doi, seed_dois):
    """Return list of {doi, jaccard} dicts comparing node to each seed via reference lists."""
    node_reference = db.get(node_doi, {}).get('reference', [])
    result = []
    for seed in seed_dois:
        seed_reference = db.get(seed.lower(), {}).get('reference', [])
        result.append({
            'doi': seed,
            'jaccard': calculate_jaccard(node_reference, seed_reference)
        })
    return result
