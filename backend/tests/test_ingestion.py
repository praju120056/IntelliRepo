"""
Tests for repository ingestion service.
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from app.ingestion.ingestion_service import (
    IngestionService,
    make_repo_id,
    extract_repo_name,
)
from app.ingestion.schemas import AnalyzeRequest


def test_make_repo_id_is_stable():
    url = "https://github.com/owner/repo"
    assert make_repo_id(url) == make_repo_id(url)
    assert len(make_repo_id(url)) == 16


def test_extract_repo_name():
    assert extract_repo_name("https://github.com/tiangolo/fastapi") == "tiangolo/fastapi"
    assert extract_repo_name("https://github.com/owner/repo/") == "owner/repo"


def test_analyze_request_validates_url():
    # Valid
    req = AnalyzeRequest(url="https://github.com/owner/repo")
    assert req.url == "https://github.com/owner/repo"

    # Invalid — not GitHub
    with pytest.raises(Exception):
        AnalyzeRequest(url="https://gitlab.com/owner/repo")

    # Invalid — missing repo part
    with pytest.raises(Exception):
        AnalyzeRequest(url="https://github.com/owner")


def test_build_file_tree(tmp_path: Path):
    # Create dummy repo structure
    (tmp_path / "main.py").write_text("print('hello')")
    (tmp_path / "utils.py").write_text("def foo(): pass")
    (tmp_path / "README.md").write_text("# Title")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "main.cpython-311.pyc").write_bytes(b"")
    (tmp_path / ".git").mkdir()

    service = IngestionService()
    tree = service.build_file_tree(tmp_path)

    paths = [f.path for f in tree]
    assert "main.py" in paths
    assert "utils.py" in paths
    assert "README.md" in paths
    # Ignored dirs must be excluded
    assert not any("__pycache__" in p for p in paths)
    assert not any(".git" in p for p in paths)

    py_files = [f for f in tree if f.language == "python"]
    assert len(py_files) == 2
    assert all(f.is_parseable for f in py_files)
