"""
Pydantic schemas for Phase 1 — Repository Ingestion.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, HttpUrl, field_validator
from enum import Enum


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    CLONING = "cloning"
    PARSING = "parsing"
    BUILDING_GRAPH = "building_graph"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETE = "complete"
    FAILED = "failed"


class FileNode(BaseModel):
    """Represents a single file in the repository."""
    path: str                       # relative path from repo root
    language: str                   # "python", "markdown", "unknown", etc.
    size_bytes: int
    lines: int
    is_parseable: bool              # True if we can extract AST from it


class RepositoryMap(BaseModel):
    """Full structural map of an ingested repository."""
    repo_id: str                    # SHA256(url) — unique stable identifier
    url: str
    name: str                       # owner/repo slug
    default_branch: str
    total_files: int
    python_files: int
    file_tree: list[FileNode]
    cloned_at: datetime
    status: AnalysisStatus = AnalysisStatus.PENDING


class AnalyzeRequest(BaseModel):
    """Request body for POST /api/v1/repos/analyze"""
    url: str

    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        v = v.strip().rstrip("/")
        if not (v.startswith("https://github.com/") or v.startswith("http://github.com/")):
            raise ValueError("Only public GitHub URLs are supported (https://github.com/owner/repo)")
        parts = v.split("github.com/")[-1].split("/")
        if len(parts) < 2 or not parts[0] or not parts[1]:
            raise ValueError("URL must follow format: https://github.com/owner/repo")
        return v


class AnalyzeResponse(BaseModel):
    """Response from POST /api/v1/repos/analyze"""
    repo_id: str
    status: AnalysisStatus
    message: str


class RepoStatusResponse(BaseModel):
    """Response from GET /api/v1/repos/{repo_id}"""
    repo_id: str
    url: str
    name: str
    status: AnalysisStatus
    python_files: int
    total_files: int
    cloned_at: datetime
    last_accessed: Optional[datetime] = None
