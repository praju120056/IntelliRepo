"""
Phase 4 — Embedding Pipeline using Sentence Transformers.

Generates text embeddings for repository nodes (functions, classes, files).
Designed for batch processing with configurable model and batch size.
"""
from __future__ import annotations

from typing import Optional
import networkx as nx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_summary(node_id: str, data: dict) -> Optional[str]:
    """
    Create a natural-language summary for a graph node.
    This text is what gets embedded — quality here directly impacts search quality.
    """
    node_type = data.get("type", "unknown")
    name = data.get("name", "") or data.get("label", "")
    file_path = data.get("file_path", data.get("path", ""))
    docstring = data.get("docstring", "")

    if node_type == "function":
        args = ", ".join(data.get("args", []))
        calls = ", ".join(data.get("calls_list", [])[:5])  # stored separately
        decs = ", ".join(data.get("decorators", []))
        class_ctx = f" in class {data['class_name']}" if data.get("class_name") else ""
        parts = [
            f"Function {name}{class_ctx} in {file_path}.",
            f"Arguments: {args}." if args else "",
            f"Decorators: {decs}." if decs else "",
            f"Calls: {calls}." if calls else "",
            docstring.strip() if docstring else "",
        ]
        return " ".join(p for p in parts if p)

    elif node_type == "class":
        bases = ", ".join(data.get("bases", []))
        parts = [
            f"Class {name} in {file_path}.",
            f"Inherits from: {bases}." if bases else "",
            docstring.strip() if docstring else "",
        ]
        return " ".join(p for p in parts if p)

    elif node_type == "file":
        lang = data.get("language", "unknown")
        lines = data.get("lines", 0)
        parts = [
            f"File {file_path or name}.",
            f"Language: {lang}.",
            f"Lines: {lines}." if lines else "",
        ]
        return " ".join(p for p in parts if p)

    return None


class EmbeddingPipeline:
    """
    Lazy-loading embedding pipeline.
    The model is loaded on first use to avoid startup delay.
    """

    def __init__(self) -> None:
        self._model = None

    @property
    def model(self):
        if self._model is None:
            logger.info(f"[blue]Loading embedding model:[/] {settings.embedding_model}")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.embedding_model)
            logger.info(f"[green]Model loaded:[/] {settings.embedding_model}")
        return self._model

    def embed_graph(self, G: nx.DiGraph) -> list[dict]:
        """
        Generate embeddings for all embeddable nodes in the graph.

        Returns a list of dicts ready for ChromaDB upsert:
          { id, document, embedding, metadata }
        """
        # Collect nodes to embed
        embeddable_types = {"function", "class", "file"}
        items: list[tuple[str, dict, str]] = []  # (node_id, data, summary)

        for node_id, data in G.nodes(data=True):
            if data.get("type") not in embeddable_types:
                continue
            summary = _build_summary(node_id, data)
            if summary:
                items.append((node_id, data, summary))

        if not items:
            logger.warning("No embeddable nodes found in graph.")
            return []

        logger.info(f"[blue]Embedding[/] {len(items)} nodes...")

        # Batch embed
        texts = [summary for _, _, summary in items]
        batch_size = settings.embedding_batch_size

        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            vecs = self.model.encode(batch, show_progress_bar=False)
            all_embeddings.extend(vecs.tolist())

        # Assemble output records
        records = []
        repo_id = G.graph.get("repo_id", "unknown")

        for (node_id, data, summary), embedding in zip(items, all_embeddings):
            records.append({
                "id": node_id,
                "document": summary,
                "embedding": embedding,
                "metadata": {
                    "node_type": data.get("type", "unknown"),
                    "name": data.get("name", data.get("label", "")),
                    "file_path": data.get("file_path", data.get("path", "")),
                    "repo_id": repo_id,
                    "start_line": data.get("start_line", 0),
                    "end_line": data.get("end_line", 0),
                    "docstring": (data.get("docstring") or "")[:500],  # Truncate for metadata
                },
            })

        logger.info(f"[green]Embedding complete:[/] {len(records)} vectors generated")
        return records

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string for semantic search."""
        vec = self.model.encode([text], show_progress_bar=False)
        return vec[0].tolist()


# Module-level singleton
embedding_pipeline = EmbeddingPipeline()
