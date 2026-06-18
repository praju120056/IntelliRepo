"""
Analysis pipeline orchestrator.
Coordinates all phases: ingest → parse → build graph → embed → index.
Runs as a background asyncio task (fire-and-forget from the API layer).
"""
from __future__ import annotations

import asyncio
from typing import Optional

from app.core.logging import get_logger
from app.core.registry import repo_registry
from app.ingestion.schemas import AnalysisStatus, RepositoryMap
from app.ingestion.ingestion_service import IngestionService
from app.ast_analysis.python_parser import RepositoryParser
from app.graph.graph_builder import GraphBuilder
from app.graph.serializer import save_graph, load_graph
from app.embeddings.embedder import embedding_pipeline
from app.vector_store.chroma_store import VectorStore
from app.cache.cache_manager import cache_manager

logger = get_logger(__name__)

ingestion_service = IngestionService()
repo_parser = RepositoryParser()
graph_builder = GraphBuilder()


async def run_analysis_pipeline(url: str, repo_id: str) -> None:
    """
    Full analysis pipeline — runs in a background task.
    Sets repo status at each stage so the frontend can poll progress.
    """
    try:
        repo_registry.set_active(repo_id)

        # ── Phase 1: Ingestion ────────────────────────────────────────────────
        logger.info(f"[bold cyan]Phase 1:[/] Ingesting {url}")
        repo_registry.set_status(repo_id, AnalysisStatus.CLONING)

        # Run blocking git clone in thread pool
        repo_map = await asyncio.get_event_loop().run_in_executor(
            None, ingestion_service.ingest, url
        )
        repo_registry.register(repo_map)
        workspace = ingestion_service.get_workspace_path(repo_id)

        # ── Phase 2: AST Parsing ──────────────────────────────────────────────
        logger.info("[bold cyan]Phase 2:[/] Parsing Python files")
        repo_registry.set_status(repo_id, AnalysisStatus.PARSING)

        python_files = [f.path for f in repo_map.file_tree if f.language == "python"]

        file_asts = await asyncio.get_event_loop().run_in_executor(
            None, repo_parser.parse_repository, workspace, python_files
        )

        # ── Phase 3: Graph Construction ───────────────────────────────────────
        logger.info("[bold cyan]Phase 3:[/] Building graph")
        repo_registry.set_status(repo_id, AnalysisStatus.BUILDING_GRAPH)

        G = await asyncio.get_event_loop().run_in_executor(
            None, graph_builder.build, repo_map, file_asts
        )
        repo_registry.store_graph(repo_id, G)
        await asyncio.get_event_loop().run_in_executor(None, save_graph, G, repo_id)

        # Cleanup workspace NOW — source files no longer needed
        await asyncio.get_event_loop().run_in_executor(
            None, ingestion_service.cleanup_workspace, repo_id
        )
        logger.info("[green]Workspace cleaned up post-AST extraction[/]")

        # ── Phase 4: Embedding ────────────────────────────────────────────────
        logger.info("[bold cyan]Phase 4:[/] Generating embeddings")
        repo_registry.set_status(repo_id, AnalysisStatus.EMBEDDING)

        records = await asyncio.get_event_loop().run_in_executor(
            None, embedding_pipeline.embed_graph, G
        )

        # ── Phase 5: Vector Index ─────────────────────────────────────────────
        logger.info("[bold cyan]Phase 5:[/] Indexing into ChromaDB")
        repo_registry.set_status(repo_id, AnalysisStatus.INDEXING)

        vector_store = VectorStore(repo_id)
        await asyncio.get_event_loop().run_in_executor(None, vector_store.upsert, records)

        # ── Done ──────────────────────────────────────────────────────────────
        repo_registry.set_status(repo_id, AnalysisStatus.COMPLETE)
        cache_manager.touch(repo_id)
        logger.info(f"[bold green]Analysis complete[/] for repo_id={repo_id}")

    except Exception as exc:
        logger.exception(f"[red]Analysis failed[/] for {url}: {exc}")
        repo_registry.set_status(repo_id, AnalysisStatus.FAILED)
        # Cleanup on failure
        try:
            ingestion_service.cleanup_workspace(repo_id)
        except Exception:
            pass
    finally:
        repo_registry.set_active(None)
