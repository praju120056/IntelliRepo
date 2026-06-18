"""API v1 — Query engine endpoints."""
from __future__ import annotations

from typing import Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.registry import repo_registry
from app.cache.cache_manager import cache_manager
from app.ingestion.schemas import AnalysisStatus
from app.graph.serializer import load_graph
from app.retrieval.query_engine import QueryEngine

router = APIRouter(prefix="/repos", tags=["Query"])


class QueryRequest(BaseModel):
    type: Literal[
        "callers_of",
        "dependencies_of",
        "importers_of",
        "call_chain",
        "impact_of",
    ] = Field(..., description="Type of graph query to execute")
    target: str = Field(..., min_length=1, description="Function name, file path, or module name")
    depth: int = Field(default=3, ge=1, le=10, description="Maximum BFS/DFS traversal depth")


def _get_engine(repo_id: str) -> QueryEngine:
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
            raise HTTPException(status_code=404, detail="Graph not found on disk.")
        repo_registry.store_graph(repo_id, G)
    cache_manager.touch(repo_id)
    return QueryEngine(G)


@router.post("/{repo_id}/query", summary="Execute a graph traversal query")
async def execute_query(repo_id: str, body: QueryRequest) -> dict:
    """
    Run a deterministic graph query over the repository structure.
    No LLMs — all answers are derived from graph traversal.
    """
    engine = _get_engine(repo_id)

    dispatch = {
        "callers_of": lambda: engine.callers_of(body.target, depth=body.depth),
        "dependencies_of": lambda: engine.dependencies_of(body.target, depth=body.depth),
        "importers_of": lambda: engine.importers_of(body.target),
        "call_chain": lambda: engine.call_chain(body.target, depth=body.depth),
        "impact_of": lambda: engine.impact_of(body.target, depth=body.depth),
    }

    result = dispatch[body.type]()
    return result.to_dict()


# ── Shortcut GET endpoints for easy browser/curl testing ─────────────────────

@router.get("/{repo_id}/query/callers/{func_name:path}")
async def callers_of(repo_id: str, func_name: str, depth: int = 3) -> dict:
    return _get_engine(repo_id).callers_of(func_name, depth).to_dict()


@router.get("/{repo_id}/query/deps/{file_path:path}")
async def dependencies_of(repo_id: str, file_path: str, depth: int = 2) -> dict:
    return _get_engine(repo_id).dependencies_of(file_path, depth).to_dict()


@router.get("/{repo_id}/query/importers/{module:path}")
async def importers_of(repo_id: str, module: str) -> dict:
    return _get_engine(repo_id).importers_of(module).to_dict()


@router.get("/{repo_id}/query/chain/{func_name:path}")
async def call_chain(repo_id: str, func_name: str, depth: int = 5) -> dict:
    return _get_engine(repo_id).call_chain(func_name, depth).to_dict()


@router.get("/{repo_id}/query/impact/{file_path:path}")
async def impact_of(repo_id: str, file_path: str, depth: int = 4) -> dict:
    return _get_engine(repo_id).impact_of(file_path, depth).to_dict()
