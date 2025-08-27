from typing import Dict, Any, List, Optional


def to_networkx(inmem_graph) -> Optional[object]:
    """Convert InMemoryGraph to networkx.DiGraph if available; else None."""
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return None
    G = nx.DiGraph()
    for nid, node in inmem_graph.nodes.items():
        G.add_node(nid, **{"type": node.type, **node.attrs})
    for src, out_edges in inmem_graph.edges.items():
        for (dst, etype, attrs) in out_edges:
            G.add_edge(src, dst, **{"type": etype, **attrs})
    return G


def compute_basic_metrics(G, focus_nodes: List[str]) -> Dict[str, Dict[str, float]]:
    """Return basic degree metrics for provided nodes; empty if NX missing."""
    try:
        import networkx as nx  # type: ignore
    except Exception:
        return {}
    metrics: Dict[str, Dict[str, float]] = {}
    deg_cent = nx.degree_centrality(G)
    for n in focus_nodes:
        if n in G:
            metrics[n] = {
                "in_degree": float(G.in_degree(n)),
                "out_degree": float(G.out_degree(n)),
                "degree_centrality": float(deg_cent.get(n, 0.0)),
            }
        else:
            metrics[n] = {"in_degree": 0.0, "out_degree": 0.0, "degree_centrality": 0.0}
    return metrics
