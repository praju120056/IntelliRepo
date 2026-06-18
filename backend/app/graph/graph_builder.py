"""
Phase 3 — Graph Construction using NetworkX.

Builds a directed graph (DiGraph) representing the full structure
and relationships of a Python repository.

Node types:
  - repository  (repo:{repo_id})
  - file        (file:{path})
  - class       (class:{path}::{name})
  - function    (func:{path}::{qualified_name})

Edge types (stored as edge attribute `type`):
  - contains    repository→file, file→class, file→function, class→function
  - imports     file→file  (resolved from import statements)
  - calls       function→function  (resolved from call sites)
  - inherits    class→class
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
import networkx as nx

from app.core.logging import get_logger
from app.ast_analysis.schemas import FileAST, FunctionDef, ClassDef, ImportStatement
from app.ingestion.schemas import RepositoryMap

logger = get_logger(__name__)


class GraphBuilder:
    """
    Constructs a NetworkX DiGraph from AST extraction results.

    Usage:
        builder = GraphBuilder()
        G = builder.build(repo_map, file_asts)
    """

    def build(
        self,
        repo_map: RepositoryMap,
        file_asts: list[FileAST],
    ) -> nx.DiGraph:
        """
        Main entry point. Returns a fully constructed dependency + call graph.
        """
        G = nx.DiGraph()
        G.graph["repo_id"] = repo_map.repo_id
        G.graph["repo_url"] = repo_map.url
        G.graph["repo_name"] = repo_map.name

        logger.info(f"[blue]Building graph[/] for {repo_map.name}")

        # 1 — Add repository root node
        repo_node_id = f"repo:{repo_map.repo_id}"
        G.add_node(repo_node_id, type="repository", label=repo_map.name, url=repo_map.url)

        # 2 — Add file nodes + structural edges
        for file_node in repo_map.file_tree:
            file_node_id = f"file:{file_node.path}"
            G.add_node(
                file_node_id,
                type="file",
                label=Path(file_node.path).name,
                path=file_node.path,
                language=file_node.language,
                size_bytes=file_node.size_bytes,
                lines=file_node.lines,
            )
            G.add_edge(repo_node_id, file_node_id, type="contains")

        # 3 — Add class + function nodes from AST
        for file_ast in file_asts:
            file_node_id = f"file:{file_ast.file_path}"

            for cls in file_ast.classes:
                G.add_node(
                    cls.node_id,
                    type="class",
                    label=cls.name,
                    name=cls.name,
                    file_path=cls.file_path,
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    bases=cls.bases,
                    docstring=cls.docstring or "",
                )
                G.add_edge(file_node_id, cls.node_id, type="contains")

            for func in file_ast.functions:
                G.add_node(
                    func.node_id,
                    type="function",
                    label=func.name,
                    name=func.name,
                    qualified_name=func.qualified_name,
                    file_path=func.file_path,
                    start_line=func.start_line,
                    end_line=func.end_line,
                    args=func.args,
                    decorators=func.decorators,
                    docstring=func.docstring or "",
                    is_method=func.is_method,
                    class_name=func.class_name or "",
                )
                # Connect to file or class
                if func.is_method and func.class_name:
                    class_node_id = f"class:{func.file_path}::{func.class_name}"
                    if G.has_node(class_node_id):
                        G.add_edge(class_node_id, func.node_id, type="contains")
                    else:
                        G.add_edge(file_node_id, func.node_id, type="contains")
                else:
                    G.add_edge(file_node_id, func.node_id, type="contains")

        # 4 — Add import edges (file → file)
        path_set = {fn.path for fn in repo_map.file_tree if fn.language == "python"}
        for file_ast in file_asts:
            self._add_import_edges(G, file_ast, path_set)

        # 5 — Add call edges (function → function)
        # Build lookup: function name → list of node_ids (may be ambiguous)
        name_to_node_ids = self._build_name_index(G)
        for file_ast in file_asts:
            self._add_call_edges(G, file_ast, name_to_node_ids)

        # 6 — Add inheritance edges (class → class)
        class_name_to_id = {
            G.nodes[n]["name"]: n
            for n in G.nodes
            if G.nodes[n].get("type") == "class"
        }
        for file_ast in file_asts:
            self._add_inheritance_edges(G, file_ast, class_name_to_id)

        logger.info(
            f"[green]Graph built:[/] {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )
        return G

    # ── Import resolution ─────────────────────────────────────────────────────

    def _add_import_edges(
        self,
        G: nx.DiGraph,
        file_ast: FileAST,
        python_paths: set[str],
    ) -> None:
        """
        Resolve import statements to actual files and add edges.
        Strategy: convert module path to file path and check if it exists.
        """
        src_id = f"file:{file_ast.file_path}"
        src_dir = str(Path(file_ast.file_path).parent)

        for imp in file_ast.imports:
            target_path = self._resolve_import(imp, src_dir, python_paths)
            if target_path:
                dst_id = f"file:{target_path}"
                if G.has_node(dst_id) and not G.has_edge(src_id, dst_id):
                    G.add_edge(src_id, dst_id, type="imports", module=imp.module)

    def _resolve_import(
        self,
        imp: ImportStatement,
        src_dir: str,
        python_paths: set[str],
    ) -> Optional[str]:
        """
        Attempt to resolve an import to a repository-local file path.
        Returns the relative file path string, or None if not resolvable.
        """
        module = imp.module

        # Handle relative imports
        if module.startswith("."):
            dots = len(module) - len(module.lstrip("."))
            parts = module.lstrip(".").split(".") if module.lstrip(".") else []
            base_parts = src_dir.replace("\\", "/").split("/")
            # Go up 'dots - 1' directories
            if dots > 1:
                base_parts = base_parts[:-(dots - 1)] if dots - 1 <= len(base_parts) else []
            candidate_parts = base_parts + parts
            candidate = "/".join(candidate_parts) + ".py"
            if candidate in python_paths:
                return candidate
            # Try as package
            candidate_init = "/".join(candidate_parts) + "/__init__.py"
            if candidate_init in python_paths:
                return candidate_init
            return None

        # Absolute import — convert dots to slashes
        parts = module.split(".")
        candidate = "/".join(parts) + ".py"
        if candidate in python_paths:
            return candidate

        candidate_init = "/".join(parts) + "/__init__.py"
        if candidate_init in python_paths:
            return candidate_init

        return None

    # ── Call graph edges ──────────────────────────────────────────────────────

    def _build_name_index(self, G: nx.DiGraph) -> dict[str, list[str]]:
        """Map bare function names → list of node_ids for fuzzy call resolution."""
        index: dict[str, list[str]] = {}
        for node_id, data in G.nodes(data=True):
            if data.get("type") == "function":
                name = data.get("name", "")
                index.setdefault(name, []).append(node_id)
                qname = data.get("qualified_name", "")
                if qname and qname != name:
                    index.setdefault(qname, []).append(node_id)
        return index

    def _add_call_edges(
        self,
        G: nx.DiGraph,
        file_ast: FileAST,
        name_index: dict[str, list[str]],
    ) -> None:
        """Add function → function call edges."""
        for func in file_ast.functions:
            if not G.has_node(func.node_id):
                continue
            for call_name in set(func.calls):  # deduplicate
                # Try exact match, then bare name
                candidates = name_index.get(call_name, [])
                if not candidates:
                    # Strip attribute prefix: "self.validate" → "validate"
                    bare = call_name.split(".")[-1]
                    candidates = name_index.get(bare, [])

                for callee_id in candidates:
                    if callee_id != func.node_id and not G.has_edge(func.node_id, callee_id):
                        G.add_edge(func.node_id, callee_id, type="calls", call_name=call_name)

    # ── Inheritance edges ─────────────────────────────────────────────────────

    def _add_inheritance_edges(
        self,
        G: nx.DiGraph,
        file_ast: FileAST,
        class_name_index: dict[str, str],
    ) -> None:
        """Add class → class inheritance edges."""
        for cls in file_ast.classes:
            if not G.has_node(cls.node_id):
                continue
            for base_name in cls.bases:
                base_id = class_name_index.get(base_name)
                if base_id and base_id != cls.node_id:
                    G.add_edge(cls.node_id, base_id, type="inherits")
