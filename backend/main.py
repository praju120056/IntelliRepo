"""
GitParse — Repository Intelligence Engine
FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.cache.cache_manager import cache_manager

# ── Logging setup (must be first) ─────────────────────────────────────────────
setup_logging("INFO")
logger = get_logger("gitparse")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle: startup → yield → shutdown."""
    settings.ensure_dirs()
    logger.info(f"[bold green]GitParse starting[/bold green]")
    logger.info(f"  Data dir: {settings.data_dir}")
    logger.info(f"  ChromaDB: {settings.chroma_dir}")
    logger.info(f"  Graphs:   {settings.graphs_dir}")
    logger.info(f"  Cache TTL: {settings.cache_ttl_hours}h")

    await cache_manager.start_background_eviction()
    yield
    await cache_manager.stop_background_eviction()
    logger.info("[yellow]GitParse shutdown complete.[/yellow]")


app = FastAPI(
    title=settings.app_title,
    version=settings.app_version,
    description=(
        "Repository Intelligence Engine — Graph-RAG without LLMs. "
        "Analyzes GitHub repositories via AST, dependency graphs, and semantic embeddings."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from app.api.v1.repos import router as repos_router
from app.api.v1.graph import router as graph_router
from app.api.v1.search import router as search_router
from app.api.v1.query import router as query_router

API_PREFIX = "/api/v1"
app.include_router(repos_router, prefix=API_PREFIX)
app.include_router(graph_router, prefix=API_PREFIX)
app.include_router(search_router, prefix=API_PREFIX)
app.include_router(query_router, prefix=API_PREFIX)


@app.get("/health", tags=["System"])
async def health() -> dict:
    return {
        "status": "ok",
        "version": settings.app_version,
        "data_dir": str(settings.data_dir),
    }


@app.get("/", tags=["System"])
async def root() -> dict:
    return {
        "name": settings.app_title,
        "version": settings.app_version,
        "docs": "/docs",
    }
