from __future__ import annotations
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    app_title: str = "GitParse — Repository Intelligence Engine"
    app_version: str = "0.1.0"

    # ── Data Storage (outside project root) ──────────────────────────────────
    gitparse_data_dir: Optional[str] = None

    @property
    def data_dir(self) -> Path:
        """Resolved data directory. Defaults to ~/.gitparse if not set."""
        if self.gitparse_data_dir:
            return Path(self.gitparse_data_dir)
        return Path.home() / ".gitparse"

    @property
    def workspaces_dir(self) -> Path:
        """Temporary cloned repository workspaces."""
        return self.data_dir / "workspaces"

    @property
    def graphs_dir(self) -> Path:
        """Serialized NetworkX graphs (JSON)."""
        return self.data_dir / "graphs"

    @property
    def chroma_dir(self) -> Path:
        """ChromaDB persistent storage."""
        return self.data_dir / "chroma_db"

    def ensure_dirs(self) -> None:
        """Create all data directories if they do not exist."""
        for d in [self.workspaces_dir, self.graphs_dir, self.chroma_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ── Analysis ──────────────────────────────────────────────────────────────
    max_traversal_depth: int = Field(default=5, ge=1, le=20)
    default_top_k: int = Field(default=10, ge=1, le=100)

    # ── Cache ─────────────────────────────────────────────────────────────────
    cache_ttl_hours: float = Field(default=3.0, ge=0.1)
    cache_check_interval_minutes: int = Field(default=15, ge=1)

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_batch_size: int = Field(default=64, ge=1, le=512)

    # ── CORS ──────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]


# Singleton settings instance
settings = Settings()
