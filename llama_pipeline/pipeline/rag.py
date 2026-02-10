"""
RAG: SQLite-based vector store with local embeddings.

Uses sentence-transformers for embeddings (CPU-friendly, no GPU needed).
Stores vectors in SQLite — no external vector DB dependency.
"""

import json
import logging
import sqlite3
import struct
from pathlib import Path
from typing import Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)


def _encode_vector(vec: np.ndarray) -> bytes:
    """Pack float32 array into bytes for SQLite storage."""
    return struct.pack(f"{len(vec)}f", *vec.tolist())


def _decode_vector(data: bytes, dim: int) -> np.ndarray:
    """Unpack bytes back to float32 array."""
    return np.array(struct.unpack(f"{dim}f", data), dtype=np.float32)


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(dot / norm)


class VectorStore:
    """SQLite-backed vector store with local embeddings."""

    def __init__(self, config_path: str = "config.yaml"):
        with open(config_path) as fh:
            cfg = yaml.safe_load(fh)

        rag_cfg = cfg.get("rag", {})
        self.db_path = rag_cfg.get("db_path", "./data/vectors.db")
        self.embedding_model_name = rag_cfg.get("embedding_model", "all-MiniLM-L6-v2")
        self.top_k = rag_cfg.get("top_k", 5)
        self.chunk_size = rag_cfg.get("chunk_size", 512)
        self.chunk_overlap = rag_cfg.get("chunk_overlap", 64)

        # Lazy-load embedding model
        self._model = None
        self._dim: Optional[int] = None

        # Ensure DB directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding BLOB NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_source
            ON documents(source)
        """)
        conn.commit()
        conn.close()

    @property
    def model(self):
        """Lazy-load sentence-transformers model."""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.embedding_model_name}")
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.embedding_model_name)
            # Determine embedding dimension
            test = self._model.encode(["test"])
            self._dim = test.shape[1]
            logger.info(f"Embedding dimension: {self._dim}")
        return self._model

    @property
    def dim(self) -> int:
        """Embedding dimension (triggers model load if needed)."""
        if self._dim is None:
            _ = self.model  # force load
        return self._dim  # type: ignore

    def embed(self, texts: list[str]) -> np.ndarray:
        """Compute embeddings for a list of texts."""
        return self.model.encode(texts, show_progress_bar=False, normalize_embeddings=True)

    def chunk_text(self, text: str) -> list[str]:
        """Split text into overlapping chunks."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def ingest_file(self, file_path: str, metadata: Optional[dict] = None) -> int:
        """Ingest a text file into the vector store. Returns number of chunks."""
        path = Path(file_path)
        text = path.read_text(errors="replace")
        return self.ingest_text(text, source=str(path), metadata=metadata)

    def ingest_text(
        self, text: str, source: str = "<inline>", metadata: Optional[dict] = None
    ) -> int:
        """Ingest raw text into the vector store. Returns number of chunks."""
        chunks = self.chunk_text(text)
        if not chunks:
            logger.warning(f"No chunks produced from source: {source}")
            return 0

        embeddings = self.embed(chunks)
        meta_json = json.dumps(metadata or {})

        conn = sqlite3.connect(self.db_path)
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            conn.execute(
                "INSERT INTO documents (source, chunk_index, content, embedding, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (source, i, chunk, _encode_vector(emb), meta_json),
            )
        conn.commit()
        conn.close()

        logger.info(f"Ingested {len(chunks)} chunks from {source}")
        return len(chunks)

    def ingest_directory(self, dir_path: str, glob: str = "**/*.txt") -> int:
        """Ingest all matching files from a directory. Returns total chunks."""
        total = 0
        for path in sorted(Path(dir_path).glob(glob)):
            if path.is_file():
                total += self.ingest_file(str(path))
        logger.info(f"Ingested {total} total chunks from {dir_path}")
        return total

    def search(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        """
        Search for similar documents.
        Returns list of {content, source, score, chunk_index}.
        """
        k = top_k or self.top_k
        query_emb = self.embed([query])[0]

        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT id, source, chunk_index, content, embedding FROM documents"
        ).fetchall()
        conn.close()

        if not rows:
            logger.warning("Vector store is empty. Run 'make ingest' first.")
            return []

        # Score all documents (brute-force — fine for <100k chunks)
        scored = []
        for row_id, source, chunk_idx, content, emb_bytes in rows:
            doc_emb = _decode_vector(emb_bytes, self.dim)
            score = _cosine_similarity(query_emb, doc_emb)
            scored.append({
                "content": content,
                "source": source,
                "chunk_index": chunk_idx,
                "score": round(score, 4),
            })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:k]

    def search_with_context(self, query: str, top_k: Optional[int] = None) -> str:
        """Search and return formatted context string for prompt injection."""
        results = self.search(query, top_k)
        if not results:
            return "(No relevant context found in knowledge base)"

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(f"--- Context {i} (score: {r['score']}, source: {r['source']}) ---")
            lines.append(r["content"])
            lines.append("")
        return "\n".join(lines)

    def count(self) -> int:
        """Return total number of chunks in the store."""
        conn = sqlite3.connect(self.db_path)
        count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        conn.close()
        return count

    def clear(self):
        """Delete all documents from the store."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("DELETE FROM documents")
        conn.commit()
        conn.close()
        logger.info("Vector store cleared")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    ap = argparse.ArgumentParser(description="RAG vector store operations")
    sub = ap.add_subparsers(dest="command")

    # ingest
    ingest_p = sub.add_parser("ingest", help="Ingest documents")
    ingest_p.add_argument("--docs", required=True, help="Directory or file to ingest")
    ingest_p.add_argument("--glob", default="**/*.txt", help="File glob pattern")
    ingest_p.add_argument("--config", default="config.yaml", help="Config file")

    # search
    search_p = sub.add_parser("search", help="Search vector store")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--top-k", type=int, help="Number of results")
    search_p.add_argument("--config", default="config.yaml", help="Config file")

    # info
    info_p = sub.add_parser("info", help="Show vector store info")
    info_p.add_argument("--config", default="config.yaml", help="Config file")

    args = ap.parse_args()

    if args.command == "ingest":
        store = VectorStore(config_path=args.config)
        path = Path(args.docs)
        if path.is_dir():
            n = store.ingest_directory(str(path), glob=args.glob)
        else:
            n = store.ingest_file(str(path))
        print(f"Ingested {n} chunks. Total: {store.count()}")

    elif args.command == "search":
        store = VectorStore(config_path=args.config)
        results = store.search(args.query, top_k=args.top_k)
        for i, r in enumerate(results, 1):
            print(f"\n--- Result {i} (score: {r['score']}) ---")
            print(f"Source: {r['source']}")
            print(r["content"][:300])

    elif args.command == "info":
        store = VectorStore(config_path=args.config)
        print(f"Vector store: {store.db_path}")
        print(f"Total chunks: {store.count()}")
        print(f"Embedding model: {store.embedding_model_name}")

    else:
        ap.print_help()


if __name__ == "__main__":
    main()
