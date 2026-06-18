"""
Tests for graph builder.
"""
import textwrap
from pathlib import Path
import pytest

from app.ast_analysis.python_parser import PythonParser
from app.graph.graph_builder import GraphBuilder
from app.ingestion.schemas import FileNode, RepositoryMap
from datetime import datetime, timezone


def make_repo_map(files: list[FileNode]) -> RepositoryMap:
    return RepositoryMap(
        repo_id="test_repo",
        url="https://github.com/test/repo",
        name="test/repo",
        default_branch="main",
        total_files=len(files),
        python_files=sum(1 for f in files if f.language == "python"),
        file_tree=files,
        cloned_at=datetime.now(timezone.utc),
    )


def write_py(tmp_path: Path, name: str, content: str) -> tuple[Path, str]:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content))
    return p, name


def test_graph_has_repo_node(tmp_path):
    f, rel = write_py(tmp_path, "main.py", "def main(): pass")
    files = [FileNode(path=rel, language="python", size_bytes=20, lines=1, is_parseable=True)]
    repo_map = make_repo_map(files)

    parser = PythonParser()
    file_asts = [parser.parse_file(f, rel)]
    G = GraphBuilder().build(repo_map, file_asts)

    assert G.has_node("repo:test_repo")
    assert G.has_node("file:main.py")


def test_graph_contains_edges(tmp_path):
    f, rel = write_py(tmp_path, "main.py", "def main(): pass")
    files = [FileNode(path=rel, language="python", size_bytes=20, lines=1, is_parseable=True)]
    parser = PythonParser()
    file_asts = [parser.parse_file(f, rel)]
    G = GraphBuilder().build(make_repo_map(files), file_asts)

    # repo → file
    assert G.has_edge("repo:test_repo", "file:main.py")
    # file → function
    assert G.has_node("func:main.py::main")
    assert G.has_edge("file:main.py", "func:main.py::main")


def test_graph_import_edge(tmp_path):
    # a.py imports b.py
    fa, rel_a = write_py(tmp_path, "a.py", "from b import foo\n")
    fb, rel_b = write_py(tmp_path, "b.py", "def foo(): pass\n")
    files = [
        FileNode(path=rel_a, language="python", size_bytes=25, lines=1, is_parseable=True),
        FileNode(path=rel_b, language="python", size_bytes=20, lines=1, is_parseable=True),
    ]
    parser = PythonParser()
    file_asts = [parser.parse_file(fa, rel_a), parser.parse_file(fb, rel_b)]
    G = GraphBuilder().build(make_repo_map(files), file_asts)

    assert G.has_edge("file:a.py", "file:b.py")
    edge_data = G.get_edge_data("file:a.py", "file:b.py")
    assert edge_data["type"] == "imports"


def test_graph_class_inheritance(tmp_path):
    f, rel = write_py(tmp_path, "animals.py", """\
        class Animal:
            pass

        class Dog(Animal):
            pass
    """)
    files = [FileNode(path=rel, language="python", size_bytes=50, lines=5, is_parseable=True)]
    parser = PythonParser()
    file_asts = [parser.parse_file(f, rel)]
    G = GraphBuilder().build(make_repo_map(files), file_asts)

    assert G.has_node("class:animals.py::Animal")
    assert G.has_node("class:animals.py::Dog")
    assert G.has_edge("class:animals.py::Dog", "class:animals.py::Animal")
    edge_data = G.get_edge_data("class:animals.py::Dog", "class:animals.py::Animal")
    assert edge_data["type"] == "inherits"
