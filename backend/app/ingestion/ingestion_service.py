"""
Phase 1 — Repository Ingestion Service.

Responsibilities:
  - Clone a GitHub repository into the configured workspaces directory
  - Walk the directory tree and build a RepositoryMap
  - Detect file languages by extension
  - Clean up source files after analysis (workspace is ephemeral)
"""
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import git

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.schemas import (
    AnalysisStatus,
    FileNode,
    RepositoryMap,
)

logger = get_logger(__name__)

# ── Language detection ────────────────────────────────────────────────────────
EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".md": "markdown",
    ".txt": "text",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sh": "shell",
    ".bash": "shell",
    ".rst": "rst",
    ".html": "html",
    ".css": "css",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".java": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".c": "c",
    ".cpp": "cpp",
    ".h": "c",
    ".hpp": "cpp",
}

PARSEABLE_LANGUAGES = {"python"}  # Only Python for MVP

# Directories to skip during traversal
IGNORED_DIRS = {
    ".git", ".github", "__pycache__", ".pytest_cache", "node_modules",
    ".venv", "venv", "env", ".env", "dist", "build", ".tox", "*.egg-info",
    ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
}


def make_repo_id(url: str) -> str:
    """Stable, deterministic repo identifier from URL."""
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def extract_repo_name(url: str) -> str:
    """Extract 'owner/repo' slug from GitHub URL."""
    parts = url.rstrip("/").split("github.com/")[-1].split("/")
    return f"{parts[0]}/{parts[1]}"


def count_lines(file_path: Path) -> int:
    """Count lines in a file, returning 0 on read failure."""
    try:
        return sum(1 for _ in file_path.open("r", encoding="utf-8", errors="ignore"))
    except Exception:
        return 0


class IngestionService:
    """Handles repository cloning, tree extraction, and cleanup."""

    def __init__(self) -> None:
        settings.ensure_dirs()

    def clone_repository(self, url: str, repo_id: str) -> Path:
        """
        Clone the GitHub repository into the workspaces directory.
        Returns the path to the cloned repository.
        """
        dest = settings.workspaces_dir / repo_id

        if dest.exists():
            logger.info(f"[yellow]Workspace already exists, removing:[/] {dest}")
            shutil.rmtree(dest, ignore_errors=True)

        logger.info(f"[blue]Cloning[/] {url} → {dest}")
        git.Repo.clone_from(
            url,
            str(dest),
            depth=1,                    # Shallow clone — we only need current state
            no_single_branch=False,
        )
        logger.info(f"[green]Clone complete:[/] {dest}")
        return dest

    def build_file_tree(self, repo_root: Path) -> list[FileNode]:
        """
        Walk the repository and build a flat list of FileNode objects.
        Skips ignored directories and binary files.
        """
        file_nodes: list[FileNode] = []

        for file_path in repo_root.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip files inside ignored directories
            rel_parts = set(file_path.relative_to(repo_root).parts)
            if rel_parts & IGNORED_DIRS:
                continue

            ext = file_path.suffix.lower()
            language = EXTENSION_LANGUAGE_MAP.get(ext, "unknown")
            is_parseable = language in PARSEABLE_LANGUAGES

            try:
                size = file_path.stat().st_size
            except OSError:
                size = 0

            lines = count_lines(file_path) if is_parseable else 0

            file_nodes.append(FileNode(
                path=str(file_path.relative_to(repo_root)).replace("\\", "/"),
                language=language,
                size_bytes=size,
                lines=lines,
                is_parseable=is_parseable,
            ))

        return sorted(file_nodes, key=lambda f: f.path)

    def ingest(self, url: str) -> RepositoryMap:
        """
        Full ingestion pipeline for a single repository.
        Returns a RepositoryMap with cloned repo still on disk.
        The caller is responsible for cleanup after AST extraction.
        """
        repo_id = make_repo_id(url)
        name = extract_repo_name(url)

        logger.info(f"[bold]Starting ingestion[/] for [cyan]{name}[/] (id={repo_id})")

        repo_path = self.clone_repository(url, repo_id)

        # Get default branch
        try:
            git_repo = git.Repo(str(repo_path))
            default_branch = git_repo.active_branch.name
        except Exception:
            default_branch = "main"

        file_tree = self.build_file_tree(repo_path)
        python_files = sum(1 for f in file_tree if f.language == "python")

        repo_map = RepositoryMap(
            repo_id=repo_id,
            url=url,
            name=name,
            default_branch=default_branch,
            total_files=len(file_tree),
            python_files=python_files,
            file_tree=file_tree,
            cloned_at=datetime.now(timezone.utc),
            status=AnalysisStatus.PARSING,
        )

        logger.info(
            f"[green]Ingestion complete:[/] {len(file_tree)} files "
            f"({python_files} Python) in [cyan]{name}[/]"
        )
        return repo_map

    def cleanup_workspace(self, repo_id: str) -> None:
        """
        Delete the cloned source files from disk.
        Called after AST extraction is complete.
        """
        dest = settings.workspaces_dir / repo_id
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
            logger.info(f"[yellow]Workspace cleaned up:[/] {dest}")

    def get_workspace_path(self, repo_id: str) -> Optional[Path]:
        """Return the workspace path if it exists, else None."""
        dest = settings.workspaces_dir / repo_id
        return dest if dest.exists() else None
