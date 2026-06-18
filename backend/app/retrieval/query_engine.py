"""
Phase 7 — Deterministic Query Engine.

Implements all MVP query types using graph traversal.
No LLMs. All explanations are template-generated.

Query types:
  - callers_of(func_name)       → what functions call X?
  - dependencies_of(file_path)  → what files does Y import?
  - importers_of(module)        → what files import Z?
  - call_chain(func_name)       → DFS execution path from function
  - impact_of(file_path)        → what breaks if we modify file A?
  - feature_localize(query)     → semantic search for a feature
"""
from __future__ import annotations

from collections import deque
from typing import Literal, Optional
import networkx as nx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

QueryType = Literal[
    "callers_of",
    "dependencies_of",
    "importers_of",
    "call_chain",
    "impact_of",
    "feature_localize",
    "semantic",
]


class QueryResult:
    def __init__(
        self,
        query_type: QueryType,
        target: str,
        nodes: list[dict],
        edges: list[dict],
        explanation: str,
        metadata: Optional[dict] = None,
    ):
        self.query_type = query_type
        self.target = target
        self.nodes = nodes
        self.edges = edges
        self.explanation = explanation
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "query_type": self.query_type,
            "target": self.target,
            "nodes": self.nodes,
            "edges": self.edges,
            "explanation": self.explanation,
            "metadata": self.metadata,
        }


class QueryEngine:
    """
    Deterministic query engine over a NetworkX graph.
    All queries use BFS / DFS / reachability — no LLM calls.
    """

    def __init__(self, G: nx.DiGraph) -> None:
        self.G = G
        self._max_depth = settings.max_traversal_depth

    # ── Lookup helpers ────────────────────────────────────────────────────────

    def _find_function_nodes(self, name: str) -> list[str]:
        """Find function node(s) by bare name, qualified name, or node_id prefix."""
        matches = []
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") != "function":
                continue
            if (
                data.get("name") == name
                or data.get("qualified_name") == name
                or node_id == name
                or node_id.endswith(f"::{name}")
            ):
                matches.append(node_id)
        return matches

    def _find_file_nodes(self, path: str) -> list[str]:
        """Find file node(s) by partial or full path."""
        matches = []
        for node_id, data in self.G.nodes(data=True):
            if data.get("type") != "file":
                continue
            if data.get("path", "").endswith(path) or node_id == path or node_id == f"file:{path}":
                matches.append(node_id)
        return matches

    def _node_to_dict(self, node_id: str) -> dict:
        if not self.G.has_node(node_id):
            return {"id": node_id}
        return {"id": node_id, **dict(self.G.nodes[node_id])}

    # ── Query: callers_of ─────────────────────────────────────────────────────

    def callers_of(self, func_name: str, depth: int = 1) -> QueryResult:
        """
        Find all functions that directly (or transitively) call `func_name`.
        Uses reverse edge traversal on 'calls' edges.
        """
        targets = self._find_function_nodes(func_name)
        if not targets:
            return QueryResult(
                query_type="callers_of",
                target=func_name,
                nodes=[],
                edges=[],
                explanation=f"No function named '{func_name}' found in the graph.",
            )

        all_callers: set[str] = set()
        all_edges: list[dict] = []
        target_id = targets[0]  # Use first match

        # BFS over reversed graph
        reverse_G = self.G.reverse(copy=False)
        frontier = deque([(target_id, 0)])
        visited = {target_id}

        while frontier:
            current_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue
            for pred_id, _, edge_data in self.G.in_edges(current_id, data=True):
                if edge_data.get("type") != "calls":
                    continue
                all_edges.append({
                    "source": pred_id,
                    "target": current_id,
                    "type": "calls",
                })
                if pred_id not in visited:
                    visited.add(pred_id)
                    all_callers.add(pred_id)
                    frontier.append((pred_id, current_depth + 1))

        caller_list = sorted(all_callers)
        nodes_out = [self._node_to_dict(target_id)] + [self._node_to_dict(n) for n in caller_list]

        callers_str = ", ".join(
            self.G.nodes[n].get("qualified_name", n) for n in caller_list[:5]
        ) or "none"

        explanation = (
            f"Function '{func_name}' is called by {len(caller_list)} function(s): {callers_str}."
            if caller_list
            else f"Function '{func_name}' is not called by any other function in this repository."
        )

        return QueryResult(
            query_type="callers_of",
            target=func_name,
            nodes=nodes_out,
            edges=all_edges,
            explanation=explanation,
            metadata={"target_node_id": target_id, "caller_count": len(all_callers)},
        )

    # ── Query: dependencies_of ────────────────────────────────────────────────

    def dependencies_of(self, file_path: str, depth: int = 2) -> QueryResult:
        """
        Find all files that `file_path` directly or transitively imports.
        Uses BFS on 'imports' edges.
        """
        targets = self._find_file_nodes(file_path)
        if not targets:
            return QueryResult(
                query_type="dependencies_of",
                target=file_path,
                nodes=[],
                edges=[],
                explanation=f"No file matching '{file_path}' found.",
            )

        target_id = targets[0]
        visited: set[str] = {target_id}
        dep_edges: list[dict] = []
        frontier = deque([(target_id, 0)])

        while frontier:
            current_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue
            for _, neighbor_id, edge_data in self.G.out_edges(current_id, data=True):
                if edge_data.get("type") != "imports":
                    continue
                dep_edges.append({
                    "source": current_id,
                    "target": neighbor_id,
                    "type": "imports",
                })
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    frontier.append((neighbor_id, current_depth + 1))

        dep_nodes = visited - {target_id}
        nodes_out = [self._node_to_dict(n) for n in [target_id] + sorted(dep_nodes)]

        dep_names = [
            self.G.nodes[n].get("path", n) for n in sorted(dep_nodes)[:5]
        ]
        explanation = (
            f"'{file_path}' depends on {len(dep_nodes)} file(s): {', '.join(dep_names)}."
            if dep_nodes
            else f"'{file_path}' has no local file dependencies (only external imports)."
        )

        return QueryResult(
            query_type="dependencies_of",
            target=file_path,
            nodes=nodes_out,
            edges=dep_edges,
            explanation=explanation,
            metadata={"source_node_id": target_id, "dependency_count": len(dep_nodes)},
        )

    # ── Query: importers_of ───────────────────────────────────────────────────

    def importers_of(self, module: str) -> QueryResult:
        """
        Find all files that import a given module.
        Searches import edge metadata and node names.
        """
        importers: list[str] = []
        imp_edges: list[dict] = []

        for src, dst, data in self.G.edges(data=True):
            if data.get("type") != "imports":
                continue
            mod = data.get("module", "")
            dst_data = self.G.nodes.get(dst, {})
            dst_path = dst_data.get("path", "")

            if (
                module in mod
                or mod.endswith(module)
                or module in dst_path
            ):
                importers.append(src)
                imp_edges.append({"source": src, "target": dst, "type": "imports"})

        nodes_out = [self._node_to_dict(n) for n in sorted(set(importers))]
        explanation = (
            f"{len(importers)} file(s) import '{module}'."
            if importers
            else f"No files import '{module}' in this repository."
        )

        return QueryResult(
            query_type="importers_of",
            target=module,
            nodes=nodes_out,
            edges=imp_edges,
            explanation=explanation,
        )

    # ── Query: call_chain ─────────────────────────────────────────────────────

    def call_chain(self, func_name: str, depth: int = 5) -> QueryResult:
        """
        DFS forward traversal — show all functions that `func_name` calls
        transitively (the execution call chain / reachability).
        """
        targets = self._find_function_nodes(func_name)
        if not targets:
            return QueryResult(
                query_type="call_chain",
                target=func_name,
                nodes=[],
                edges=[],
                explanation=f"No function named '{func_name}' found.",
            )

        target_id = targets[0]
        visited: set[str] = {target_id}
        chain_edges: list[dict] = []
        stack: list[tuple[str, int]] = [(target_id, 0)]

        while stack:
            current_id, current_depth = stack.pop()
            if current_depth >= depth:
                continue
            for _, callee_id, edge_data in self.G.out_edges(current_id, data=True):
                if edge_data.get("type") != "calls":
                    continue
                chain_edges.append({
                    "source": current_id,
                    "target": callee_id,
                    "type": "calls",
                })
                if callee_id not in visited:
                    visited.add(callee_id)
                    stack.append((callee_id, current_depth + 1))

        all_nodes = sorted(visited)
        nodes_out = [self._node_to_dict(n) for n in all_nodes]

        reachable = visited - {target_id}
        explanation = (
            f"'{func_name}' transitively calls {len(reachable)} function(s) "
            f"(up to depth {depth})."
        )

        return QueryResult(
            query_type="call_chain",
            target=func_name,
            nodes=nodes_out,
            edges=chain_edges,
            explanation=explanation,
            metadata={"start_node_id": target_id, "reachable_count": len(reachable)},
        )

    # ── Query: impact_of ──────────────────────────────────────────────────────

    def impact_of(self, file_path: str, depth: int = 4) -> QueryResult:
        """
        Impact analysis — find all files that would be affected if `file_path` changes.
        Uses BFS on the REVERSED import graph (who imports us?).
        """
        targets = self._find_file_nodes(file_path)
        if not targets:
            return QueryResult(
                query_type="impact_of",
                target=file_path,
                nodes=[],
                edges=[],
                explanation=f"No file matching '{file_path}' found.",
            )

        target_id = targets[0]
        affected: set[str] = set()
        impact_edges: list[dict] = []
        frontier = deque([(target_id, 0)])
        visited = {target_id}

        while frontier:
            current_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue
            for importer_id, _, edge_data in self.G.in_edges(current_id, data=True):
                if edge_data.get("type") != "imports":
                    continue
                impact_edges.append({
                    "source": importer_id,
                    "target": current_id,
                    "type": "imports",
                    "impact": "may_break",
                })
                if importer_id not in visited:
                    visited.add(importer_id)
                    affected.add(importer_id)
                    frontier.append((importer_id, current_depth + 1))

        nodes_out = [self._node_to_dict(n) for n in [target_id] + sorted(affected)]

        affected_names = [
            self.G.nodes[n].get("path", n) for n in sorted(affected)[:5]
        ]
        explanation = (
            f"Modifying '{file_path}' may impact {len(affected)} file(s): "
            f"{', '.join(affected_names)}{'...' if len(affected) > 5 else ''}."
            if affected
            else f"Modifying '{file_path}' has no detected impact (no files import it)."
        )

        return QueryResult(
            query_type="impact_of",
            target=file_path,
            nodes=nodes_out,
            edges=impact_edges,
            explanation=explanation,
            metadata={"source_node_id": target_id, "affected_count": len(affected)},
        )
