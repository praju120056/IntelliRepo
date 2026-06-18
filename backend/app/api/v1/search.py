"""API v1 — Semantic search endpoint."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.registry import repo_registry
from app.cache.cache_manager import cache_manager
from app.ingestion.schemas import AnalysisStatus
from app.graph.serializer import load_graph
from app.retrieval.retriever import GraphRetriever

router = APIRouter(prefix="/repos", tags=["Search"])


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500, description="Natural language search query")
    top_k: int = Field(default=10, ge=1, le=50)
    node_types: Optional[list[str]] = Field(
        default=None,
        description="Filter by node types: 'function', 'class', 'file'"
    )
    expand: bool = Field(default=True, description="Expand results via graph neighbors")
    expand_depth: int = Field(default=1, ge=0, le=3)


@router.post("/{repo_id}/search", summary="Semantic search over repository nodes")
async def semantic_search(repo_id: str, body: SearchRequest) -> dict:
    """
    Embeds the query and retrieves semantically similar repository nodes.
    Optionally expands results through graph traversal.
    """
    repo = repo_registry.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    if repo.status != AnalysisStatus.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Analysis not complete. Status: {repo.status}",
        )

    G = repo_registry.get_graph(repo_id)
    if G is None:
        G = load_graph(repo_id)
        if G is None:
            raise HTTPException(status_code=404, detail="Graph not found.")
        repo_registry.store_graph(repo_id, G)

    cache_manager.touch(repo_id)
    retriever = GraphRetriever(repo_id, G)

    return retriever.semantic_search(
        query=body.query,
        top_k=body.top_k,
        node_types=body.node_types,
        expand=body.expand,
        expand_depth=body.expand_depth,
    )
