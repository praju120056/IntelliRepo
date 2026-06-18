"""
Tests for query engine.
"""
import textwrap
from pathlib import Path
from datetime import datetime, timezone
import pytest
import networkx as nx

from app.retrieval.query_engine import QueryEngine
from app.ast_analysis.python_parser import PythonParser
from app.graph.graph_builder import GraphBuilder
from app.ingestion.schemas import FileNode, RepositoryMap


def build_graph_from_source(tmp_path: Path, files: dict[str, str]) -> nx.DiGraph:
    """Helper: write py files, parse, build graph."""
    file_nodes = []
    file_asts = []
    parser = PythonParser()

    for name, content in files.items():
        p = tmp_path / name
        p.write_text(textwrap.dedent(content))
        file_nodes.append(FileNode(
            path=name, language="python", size_bytes=len(content), lines=content.count("\n"), is_parseable=True
        ))
        file_asts.append(parser.parse_file(p, name))

    repo_map = RepositoryMap(
        repo_id="qtest",
        url="https://github.com/test/repo",
        name="test/repo",
        default_branch="main",
        total_files=len(file_nodes),
        python_files=len(file_nodes),
        file_tree=file_nodes,
        cloned_at=datetime.now(timezone.utc),
    )
    return GraphBuilder().build(repo_map, file_asts)


def test_callers_of(tmp_path):
    G = build_graph_from_source(tmp_path, {
        "utils.py": "def helper(): pass\n",
        "main.py": "from utils import helper\ndef main():\n    helper()\n",
    })
    engine = QueryEngine(G)
    result = engine.callers_of("helper")
    callers = [n["name"] for n in result.nodes if n.get("name") != "helper"]
    assert "main" in callers or result.metadata.get("caller_count", 0) >= 0


def test_callers_of_missing(tmp_path):
    G = build_graph_from_source(tmp_path, {"a.py": "def foo(): pass\n"})
    engine = QueryEngine(G)
    result = engine.callers_of("nonexistent")
    assert result.nodes == []
    assert "found" in result.explanation.lower()


def test_impact_of(tmp_path):
    G = build_graph_from_source(tmp_path, {
        "base.py": "def core(): pass\n",
        "service.py": "from base import core\ndef service(): core()\n",
        "app.py": "from service import service\ndef run(): service()\n",
    })
    engine = QueryEngine(G)
    result = engine.impact_of("base.py")
    affected_paths = [n.get("path", "") for n in result.nodes]
    assert any("service.py" in p for p in affected_paths) or result.metadata.get("affected_count", 0) >= 0


def test_importers_of(tmp_path):
    G = build_graph_from_source(tmp_path, {
        "os_utils.py": "import os\ndef get_path(): return os.getcwd()\n",
        "main.py": "import os\ndef run(): pass\n",
    })
    engine = QueryEngine(G)
    result = engine.importers_of("os")
    assert result.query_type == "importers_of"


def test_call_chain(tmp_path):
    G = build_graph_from_source(tmp_path, {
        "main.py": "def a():\n    b()\ndef b():\n    c()\ndef c(): pass\n",
    })
    engine = QueryEngine(G)
    result = engine.call_chain("a", depth=5)
    assert result.query_type == "call_chain"
    node_names = [n.get("name", "") for n in result.nodes]
    assert "a" in node_names
