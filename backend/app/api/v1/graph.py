"""API v1 — Graph endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.core.registry import repo_registry
from app.cache.cache_manager import cache_manager
from app.graph.serializer import graph_to_dict, subgraph_by_edge_type, load_graph
from app.ingestion.schemas import AnalysisStatus

logger = get_logger(__name__)
router = APIRouter(prefix="/repos", tags=["Graph"])


def _get_graph_or_404(repo_id: str):
    repo = repo_registry.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    if repo.status != AnalysisStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Graph not yet available. Analysis status: {repo.status}",
        )

    G = repo_registry.get_graph(repo_id)
    if G is None:
        # Try loading from disk
        G = load_graph(repo_id)
        if G is None:
            raise HTTPException(status_code=404, detail="Graph data not found on disk.")
        repo_registry.store_graph(repo_id, G)

    cache_manager.touch(repo_id)
    return G


@router.get("/{repo_id}/graph", summary="Get full repository graph (nodes + edges)")
async def get_full_graph(repo_id: str) -> dict:
    G = _get_graph_or_404(repo_id)
    return graph_to_dict(G)


@router.get("/{repo_id}/graph/deps", summary="Get dependency subgraph (import edges only)")
async def get_deps_graph(repo_id: str) -> dict:
    G = _get_graph_or_404(repo_id)
    sub = subgraph_by_edge_type(G, "imports")
    return graph_to_dict(sub)


@router.get("/{repo_id}/graph/calls", summary="Get call graph (function call edges only)")
async def get_call_graph(repo_id: str) -> dict:
    G = _get_graph_or_404(repo_id)
    sub = subgraph_by_edge_type(G, "calls")
    return graph_to_dict(sub)


@router.get("/{repo_id}/graph/node/{node_id:path}", summary="Get a single node and its neighbors")
async def get_node(repo_id: str, node_id: str, depth: int = 2) -> dict:
    G = _get_graph_or_404(repo_id)

    if not G.has_node(node_id):
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found in graph.")

    from app.retrieval.retriever import GraphRetriever
    retriever = GraphRetriever(repo_id, G)
    return retriever.get_node_context(node_id, depth=min(depth, 3))


@router.get("/{repo_id}/graph/stats", summary="Get graph statistics")
async def get_graph_stats(repo_id: str) -> dict:
    G = _get_graph_or_404(repo_id)

    node_types = {}
    for _, data in G.nodes(data=True):
        t = data.get("type", "unknown")
        node_types[t] = node_types.get(t, 0) + 1

    edge_types = {}
    for _, _, data in G.edges(data=True):
        t = data.get("type", "unknown")
        edge_types[t] = edge_types.get(t, 0) + 1

    return {
        "repo_id": repo_id,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "node_types": node_types,
        "edge_types": edge_types,
        "is_dag": _is_dag(G),
    }


def _is_dag(G) -> bool:
    try:
        import networkx as nx
        return nx.is_directed_acyclic_graph(G)
    except Exception:
        return False
