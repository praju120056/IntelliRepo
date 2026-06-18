"""
In-memory repository registry.
Stores RepositoryMap objects and coordinates the analysis pipeline state.
Single-analysis-at-a-time enforced here.
"""
from __future__ import annotations

import asyncio
from typing import Optional
import networkx as nx

from app.ingestion.schemas import RepositoryMap, AnalysisStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class RepoRegistry:
    """
    Central in-memory registry for repositories undergoing or having completed analysis.
    Enforces single-concurrent-analysis constraint.
    """

    def __init__(self) -> None:
        self._repos: dict[str, RepositoryMap] = {}
        self._graphs: dict[str, nx.DiGraph] = {}
        self._lock = asyncio.Lock()
        self._active_repo_id: Optional[str] = None  # currently analyzing

    # ── Registry operations ───────────────────────────────────────────────────

    def register(self, repo_map: RepositoryMap) -> None:
        self._repos[repo_map.repo_id] = repo_map

    def get(self, repo_id: str) -> Optional[RepositoryMap]:
        return self._repos.get(repo_id)

    def set_status(self, repo_id: str, status: AnalysisStatus) -> None:
        if repo_id in self._repos:
            self._repos[repo_id].status = status

    def all(self) -> list[RepositoryMap]:
        return list(self._repos.values())

    def remove(self, repo_id: str) -> None:
        self._repos.pop(repo_id, None)
        self._graphs.pop(repo_id, None)

    def is_busy(self) -> bool:
        return self._active_repo_id is not None

    def get_active(self) -> Optional[str]:
        return self._active_repo_id

    def set_active(self, repo_id: Optional[str]) -> None:
        self._active_repo_id = repo_id

    # ── Graph storage ─────────────────────────────────────────────────────────

    def store_graph(self, repo_id: str, G: nx.DiGraph) -> None:
        self._graphs[repo_id] = G

    def get_graph(self, repo_id: str) -> Optional[nx.DiGraph]:
        return self._graphs.get(repo_id)


# Module-level singleton
repo_registry = RepoRegistry()
