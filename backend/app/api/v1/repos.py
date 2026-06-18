"""API v1 — Repository management endpoints."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.core.logging import get_logger
from app.core.pipeline import run_analysis_pipeline
from app.core.registry import repo_registry
from app.cache.cache_manager import cache_manager
from app.ingestion.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    AnalysisStatus,
    RepoStatusResponse,
    RepositoryMap,
)
from app.ingestion.ingestion_service import make_repo_id

logger = get_logger(__name__)
router = APIRouter(prefix="/repos", tags=["Repositories"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger full analysis pipeline for a GitHub repository",
)
async def analyze_repository(
    body: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> AnalyzeResponse:
    """
    Accepts a GitHub URL, validates it, and triggers the 5-phase analysis
    pipeline as a background task. Returns immediately with repo_id and status.
    """
    repo_id = make_repo_id(body.url)

    # Check if already analyzed
    existing = repo_registry.get(repo_id)
    if existing and existing.status == AnalysisStatus.COMPLETE:
        cache_manager.touch(repo_id)
        return AnalyzeResponse(
            repo_id=repo_id,
            status=AnalysisStatus.COMPLETE,
            message="Repository already analyzed. Use cached results.",
        )

    # Enforce one-at-a-time constraint
    if repo_registry.is_busy():
        active = repo_registry.get_active()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Another repository (id={active}) is currently being analyzed. "
                   "Please wait for it to complete.",
        )

    # Register as pending
    from app.ingestion.ingestion_service import extract_repo_name
    placeholder = RepositoryMap(
        repo_id=repo_id,
        url=body.url,
        name=extract_repo_name(body.url),
        default_branch="main",
        total_files=0,
        python_files=0,
        file_tree=[],
        cloned_at=datetime.now(timezone.utc),
        status=AnalysisStatus.PENDING,
    )
    repo_registry.register(placeholder)

    # Launch pipeline
    background_tasks.add_task(run_analysis_pipeline, body.url, repo_id)

    return AnalyzeResponse(
        repo_id=repo_id,
        status=AnalysisStatus.PENDING,
        message=f"Analysis started for {body.url}. Poll GET /repos/{repo_id} for status.",
    )


@router.get(
    "/{repo_id}",
    response_model=RepoStatusResponse,
    summary="Get repository metadata and analysis status",
)
async def get_repo_status(repo_id: str) -> RepoStatusResponse:
    repo = repo_registry.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")

    cache_manager.touch(repo_id)
    return RepoStatusResponse(
        repo_id=repo.repo_id,
        url=repo.url,
        name=repo.name,
        status=repo.status,
        python_files=repo.python_files,
        total_files=repo.total_files,
        cloned_at=repo.cloned_at,
        last_accessed=cache_manager.last_accessed(repo_id),
    )


@router.get(
    "/{repo_id}/tree",
    summary="Get repository file tree",
)
async def get_repo_tree(repo_id: str) -> dict:
    repo = repo_registry.get(repo_id)
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    if repo.status not in (AnalysisStatus.COMPLETE, AnalysisStatus.PARSING, AnalysisStatus.BUILDING_GRAPH):
        raise HTTPException(
            status_code=400,
            detail=f"Repository analysis not yet complete. Status: {repo.status}",
        )

    cache_manager.touch(repo_id)
    return {
        "repo_id": repo_id,
        "name": repo.name,
        "total_files": repo.total_files,
        "python_files": repo.python_files,
        "file_tree": [f.model_dump() for f in repo.file_tree],
    }


@router.get(
    "",
    summary="List all known repositories",
)
async def list_repos() -> dict:
    repos = repo_registry.all()
    return {
        "count": len(repos),
        "repos": [
            {
                "repo_id": r.repo_id,
                "name": r.name,
                "url": r.url,
                "status": r.status,
                "python_files": r.python_files,
            }
            for r in repos
        ],
    }


@router.delete(
    "/{repo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Manually evict a repository from cache",
)
async def delete_repo(repo_id: str) -> None:
    if not repo_registry.get(repo_id):
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found.")
    cache_manager.evict(repo_id)
    repo_registry.remove(repo_id)
