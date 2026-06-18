"""
Phase 5 — Vector Database (ChromaDB).

Persistent ChromaDB storage for repository node embeddings.
One collection per repository (named repo_{repo_id}).
"""
from __future__ import annotations

from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Sentinel for not-yet-initialized client
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Return (or create) the shared ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        settings.ensure_dirs()
        _chroma_client = chromadb.PersistentClient(
            path=str(settings.chroma_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info(f"[green]ChromaDB initialized[/] at {settings.chroma_dir}")
    return _chroma_client


def _collection_name(repo_id: str) -> str:
    return f"repo_{repo_id}"


class VectorStore:
    """
    Manages a single ChromaDB collection for one repository.
    """

    def __init__(self, repo_id: str) -> None:
        self.repo_id = repo_id
        self._collection_name = _collection_name(repo_id)
        self._client = get_chroma_client()
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(self, records: list[dict]) -> None:
        """
        Upsert a list of embedding records into the collection.

        Each record must have: id, document, embedding, metadata.
        """
        if not records:
            return

        ids = [r["id"] for r in records]
        documents = [r["document"] for r in records]
        embeddings = [r["embedding"] for r in records]
        metadatas = [r["metadata"] for r in records]

        # ChromaDB upsert in batches of 500 (Chroma limit)
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            self._collection.upsert(
                ids=ids[i : i + batch_size],
                documents=documents[i : i + batch_size],
                embeddings=embeddings[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
            )

        logger.info(f"[green]Upserted {len(records)} vectors[/] into {self._collection_name}")

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        where: Optional[dict] = None,
    ) -> list[dict]:
        """
        Semantic nearest-neighbor search.

        Returns list of result dicts with keys:
          id, document, metadata, distance
        """
        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, self._collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        output = []
        for i, doc_id in enumerate(results["ids"][0]):
            output.append({
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
                "score": 1.0 - results["distances"][0][i],  # cosine similarity
            })
        return output

    def delete_collection(self) -> None:
        """Remove the entire collection for this repository."""
        try:
            self._client.delete_collection(self._collection_name)
            logger.info(f"[yellow]Collection deleted:[/] {self._collection_name}")
        except Exception as exc:
            logger.warning(f"Failed to delete collection {self._collection_name}: {exc}")

    def count(self) -> int:
        """Return number of stored vectors."""
        return self._collection.count()

    def collection_exists(self) -> bool:
        """Check if a collection exists for this repo_id."""
        try:
            self._client.get_collection(self._collection_name)
            return True
        except Exception:
            return False


def delete_repo_collection(repo_id: str) -> None:
    """Delete a repository's vector store collection (used during cache eviction)."""
    client = get_chroma_client()
    name = _collection_name(repo_id)
    try:
        client.delete_collection(name)
        logger.info(f"[yellow]Collection evicted:[/] {name}")
    except Exception:
        pass  # Already gone
