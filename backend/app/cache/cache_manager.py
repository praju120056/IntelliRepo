"""
Phase 9 — Cache Manager.

Tracks repository access times and evicts stale entries:
  - Deletes ChromaDB collection
  - Deletes serialized graph JSON
  - Source workspaces are already deleted post-analysis

Background asyncio task runs every N minutes.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger
from app.graph.serializer import delete_graph
from app.vector_store.chroma_store import delete_repo_collection

logger = get_logger(__name__)


class CacheManager:
    """
    In-memory registry of repository access timestamps.
    """

    def __init__(self) -> None:
        # repo_id → last_access datetime (UTC)
        self._registry: dict[str, datetime] = {}
        self._task: Optional[asyncio.Task] = None

    def touch(self, repo_id: str) -> None:
        """Record (or refresh) the last access time for a repository."""
        self._registry[repo_id] = datetime.now(timezone.utc)

    def last_accessed(self, repo_id: str) -> Optional[datetime]:
        return self._registry.get(repo_id)

    def is_registered(self, repo_id: str) -> bool:
        return repo_id in self._registry

    def all_repos(self) -> dict[str, datetime]:
        return dict(self._registry)

    def remove(self, repo_id: str) -> None:
        self._registry.pop(repo_id, None)

    # ── Eviction ──────────────────────────────────────────────────────────────

    def evict(self, repo_id: str) -> None:
        """Immediately evict a repository from all caches."""
        logger.info(f"[yellow]Evicting repository[/] {repo_id}")
        delete_graph(repo_id)
        delete_repo_collection(repo_id)
        self.remove(repo_id)

    def evict_stale(self) -> list[str]:
        """
        Evict all repositories that have been inactive for longer than TTL.
        Returns list of evicted repo_ids.
        """
        ttl = timedelta(hours=settings.cache_ttl_hours)
        now = datetime.now(timezone.utc)
        evicted = []

        for repo_id, last_access in list(self._registry.items()):
            if now - last_access > ttl:
                logger.info(
                    f"[yellow]TTL expired[/] for {repo_id} "
                    f"(last access: {last_access.isoformat()})"
                )
                self.evict(repo_id)
                evicted.append(repo_id)

        return evicted

    # ── Background task ───────────────────────────────────────────────────────

    async def start_background_eviction(self) -> None:
        """Start the background eviction task. Call once on app startup."""
        self._task = asyncio.create_task(self._eviction_loop())
        logger.info(
            f"[blue]Cache eviction loop started[/] "
            f"(interval={settings.cache_check_interval_minutes}m, "
            f"TTL={settings.cache_ttl_hours}h)"
        )

    async def stop_background_eviction(self) -> None:
        """Cancel the background eviction task. Call on app shutdown."""
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("[yellow]Cache eviction loop stopped.[/]")

    async def _eviction_loop(self) -> None:
        interval_seconds = settings.cache_check_interval_minutes * 60
        while True:
            await asyncio.sleep(interval_seconds)
            evicted = self.evict_stale()
            if evicted:
                logger.info(f"[yellow]Eviction run:[/] removed {len(evicted)} stale repo(s)")


# Module-level singleton
cache_manager = CacheManager()
