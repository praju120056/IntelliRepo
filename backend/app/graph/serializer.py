"""
Graph serialization / deserialization.
Stores NetworkX graphs as JSON using node_link_data format.
"""
import json
from pathlib import Path
from typing import Optional
import networkx as nx
from networkx.readwrite import json_graph

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def save_graph(G: nx.DiGraph, repo_id: str) -> Path:
    """Serialize graph to JSON and save to the graphs directory."""
    settings.ensure_dirs()
    out_path = settings.graphs_dir / f"{repo_id}.json"
    data = json_graph.node_link_data(G)
    out_path.write_text(json.dumps(data, default=str), encoding="utf-8")
    logger.info(f"[green]Graph saved:[/] {out_path}")
    return out_path


def load_graph(repo_id: str) -> Optional[nx.DiGraph]:
    """Load a graph from disk. Returns None if not found."""
    path = settings.graphs_dir / f"{repo_id}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    G = json_graph.node_link_graph(data, directed=True, multigraph=False)
    logger.info(f"[green]Graph loaded:[/] {path} ({G.number_of_nodes()} nodes)")
    return G


def delete_graph(repo_id: str) -> bool:
    """Delete a persisted graph. Returns True if deleted."""
    path = settings.graphs_dir / f"{repo_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"[yellow]Graph deleted:[/] {path}")
        return True
    return False


def graph_exists(repo_id: str) -> bool:
    """Check if a persisted graph exists for this repo_id."""
    return (settings.graphs_dir / f"{repo_id}.json").exists()


def graph_to_dict(G: nx.DiGraph) -> dict:
    """Convert graph to a JSON-serializable dict (for API responses)."""
    nodes = []
    for node_id, data in G.nodes(data=True):
        nodes.append({"id": node_id, **{k: v for k, v in data.items() if v is not None}})

    edges = []
    for src, dst, data in G.edges(data=True):
        edges.append({"source": src, "target": dst, **data})

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "repo_id": G.graph.get("repo_id"),
            "repo_name": G.graph.get("repo_name"),
        },
    }


def subgraph_by_edge_type(G: nx.DiGraph, edge_type: str) -> nx.DiGraph:
    """Return a subgraph containing only edges of a given type."""
    edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("type") == edge_type]
    nodes = set()
    for u, v in edges:
        nodes.add(u)
        nodes.add(v)
    sub = G.subgraph(nodes).copy()
    # Keep only matching edges
    remove = [(u, v) for u, v, d in sub.edges(data=True) if d.get("type") != edge_type]
    sub.remove_edges_from(remove)
    return sub
