"""
Phase 6 — Graph-Aware Retriever.

Combines:
  1. Semantic search (ChromaDB) to find seed nodes
  2. Graph expansion (BFS) to find connected context nodes
  3. Context assembly into a structured response

This is the core "Graph-RAG without LLMs" pipeline.
"""
from __future__ import annotations

from collections import deque
from typing import Optional
import networkx as nx

from app.core.config import settings
from app.core.logging import get_logger
from app.embeddings.embedder import embedding_pipeline
from app.vector_store.chroma_store import VectorStore

logger = get_logger(__name__)


class RetrievedNode:
    """A single node in a retrieval result."""
    def __init__(
        self,
        node_id: str,
        data: dict,
        score: float = 0.0,
        distance: float = 1.0,
        origin: str = "graph_expansion",   # "semantic" | "graph_expansion"
    ):
        self.node_id = node_id
        self.data = data
        self.score = score
        self.distance = distance
        self.origin = origin

    def to_dict(self) -> dict:
        return {
            "id": self.node_id,
            "type": self.data.get("type"),
            "name": self.data.get("name", self.data.get("label", "")),
            "file_path": self.data.get("file_path", self.data.get("path", "")),
            "start_line": self.data.get("start_line"),
            "end_line": self.data.get("end_line"),
            "docstring": self.data.get("docstring", ""),
            "score": round(self.score, 4),
            "origin": self.origin,
        }


class GraphRetriever:
    """
    Graph-aware retriever for a single repository.

    Usage:
        retriever = GraphRetriever(repo_id, G)
        results = retriever.semantic_search("authentication", top_k=10)
        context = retriever.expand("func:auth/login.py::login", depth=2)
    """

    def __init__(self, repo_id: str, G: nx.DiGraph) -> None:
        self.repo_id = repo_id
        self.G = G
        self._store = VectorStore(repo_id)

    # ── Semantic search ───────────────────────────────────────────────────────

    def semantic_search(
        self,
        query: str,
        top_k: int = 10,
        node_types: Optional[list[str]] = None,
        expand: bool = True,
        expand_depth: int = 1,
    ) -> dict:
        """
        Full semantic search + optional graph expansion.

        Returns:
          {
            "query": str,
            "seed_nodes": [RetrievedNode dicts],
            "expanded_nodes": [RetrievedNode dicts],
            "edges": [edge dicts],
            "explanation": str
          }
        """
        logger.info(f"[blue]Semantic search:[/] '{query}' (top_k={top_k})")

        # 1 — Embed query
        query_vec = embedding_pipeline.embed_query(query)

        # 2 — ChromaDB search
        where_filter = {"node_type": {"$in": node_types}} if node_types else None
        raw_results = self._store.query(query_vec, top_k=top_k, where=where_filter)

        # 3 — Map results to graph nodes
        seed_nodes: list[RetrievedNode] = []
        for r in raw_results:
            node_id = r["id"]
            if self.G.has_node(node_id):
                seed_nodes.append(RetrievedNode(
                    node_id=node_id,
                    data=dict(self.G.nodes[node_id]),
                    score=r["score"],
                    distance=r["distance"],
                    origin="semantic",
                ))

        # 4 — Graph expansion from seed nodes
        expanded_nodes: list[RetrievedNode] = []
        edges: list[dict] = []

        if expand and seed_nodes:
            seed_ids = {n.node_id for n in seed_nodes}
            expanded_ids, edge_list = self._bfs_expand(seed_ids, depth=expand_depth)
            for node_id in expanded_ids - seed_ids:
                if self.G.has_node(node_id):
                    expanded_nodes.append(RetrievedNode(
                        node_id=node_id,
                        data=dict(self.G.nodes[node_id]),
                        origin="graph_expansion",
                    ))
            edges = edge_list

        explanation = self._build_search_explanation(query, seed_nodes, expanded_nodes)

        return {
            "query": query,
            "seed_nodes": [n.to_dict() for n in seed_nodes],
            "expanded_nodes": [n.to_dict() for n in expanded_nodes],
            "edges": edges,
            "explanation": explanation,
        }

    # ── Graph traversal ───────────────────────────────────────────────────────

    def _bfs_expand(
        self,
        seed_ids: set[str],
        depth: int = 2,
        edge_types: Optional[set[str]] = None,
    ) -> tuple[set[str], list[dict]]:
        """
        BFS expansion from a set of seed nodes up to `depth` hops.
        Returns (all_visited_node_ids, edge_list).
        """
        visited = set(seed_ids)
        frontier = deque((node_id, 0) for node_id in seed_ids)
        edges: list[dict] = []

        while frontier:
            current_id, current_depth = frontier.popleft()
            if current_depth >= depth:
                continue

            # Outgoing edges
            for _, neighbor_id, data in self.G.out_edges(current_id, data=True):
                etype = data.get("type", "")
                if edge_types and etype not in edge_types:
                    continue
                edges.append({"source": current_id, "target": neighbor_id, "type": etype})
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    frontier.append((neighbor_id, current_depth + 1))

            # Incoming edges
            for neighbor_id, _, data in self.G.in_edges(current_id, data=True):
                etype = data.get("type", "")
                if edge_types and etype not in edge_types:
                    continue
                edges.append({"source": neighbor_id, "target": current_id, "type": etype})
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    frontier.append((neighbor_id, current_depth + 1))

        return visited, edges

    def get_node_context(self, node_id: str, depth: int = 2) -> dict:
        """Return a node and all its graph neighbors up to `depth` hops."""
        if not self.G.has_node(node_id):
            return {"error": f"Node '{node_id}' not found in graph."}

        data = dict(self.G.nodes[node_id])
        visited, edges = self._bfs_expand({node_id}, depth=depth)
        neighbor_nodes = [
            {"id": nid, **dict(self.G.nodes[nid])}
            for nid in visited - {node_id}
            if self.G.has_node(nid)
        ]
        return {
            "node": {"id": node_id, **data},
            "neighbors": neighbor_nodes,
            "edges": edges,
        }

    # ── Explanation builder ───────────────────────────────────────────────────

    def _build_search_explanation(
        self,
        query: str,
        seeds: list[RetrievedNode],
        expanded: list[RetrievedNode],
    ) -> str:
        if not seeds:
            return f"No results found for query '{query}'."

        top = seeds[0]
        top_name = top.data.get("name", top.node_id)
        top_type = top.data.get("type", "node")
        top_file = top.data.get("file_path", "")

        parts = [
            f"Found {len(seeds)} relevant {top_type}s for '{query}'.",
            f"Best match: {top_name} ({top_type}) in {top_file} "
            f"(similarity {top.score:.2%}).",
        ]
        if expanded:
            parts.append(f"Graph expansion added {len(expanded)} related nodes.")

        return " ".join(parts)
