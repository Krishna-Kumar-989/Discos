import os
import json
import logging
import re
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional

from qdrant_client import QdrantClient
from qdrant_client import models
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("qdrant.client")

def sanitize_collection_name(name: str) -> str:
    """Convert server name to a safe Qdrant collection name (alphanumeric and underscores)."""
    cleaned = re.sub(r'[^a-zA-Z0-9]', '_', name.lower())
    cleaned = re.sub(r'_+', '_', cleaned)
    return cleaned.strip('_')

def format_uuid(md5_hex: str) -> str:
    """Format a 32-character hex string into a valid UUID string (8-4-4-4-12 format)."""
    if len(md5_hex) != 32:
        return md5_hex
    return f"{md5_hex[0:8]}-{md5_hex[8:12]}-{md5_hex[12:16]}-{md5_hex[16:20]}-{md5_hex[20:32]}"

def build_qdrant_filter(filters: Dict[str, Any]) -> Optional[models.Filter]:
    """Convert a dictionary of filters into a Qdrant Filter object."""
    if not filters:
        return None
        
    conditions = []
    for key, value in filters.items():
        if value is None:
            continue
        if isinstance(value, list):
            conditions.append(models.FieldCondition(key=key, match=models.MatchAny(any=value)))
        else:
            conditions.append(models.FieldCondition(key=key, match=models.MatchValue(value=value)))
            
    return models.Filter(must=conditions) if conditions else None

# Global client singleton to reuse connection
_QDRANT_CLIENT: Optional[QdrantClient] = None

def get_qdrant_client() -> QdrantClient:
    global _QDRANT_CLIENT
    if _QDRANT_CLIENT is not None:
        return _QDRANT_CLIENT

    url = os.getenv("QDRANT_URL")
    api_key = os.getenv("QDRANT_API_KEY")
    
    # Treat empty strings as None to prevent QdrantClient from defaulting to SSL
    if api_key == "":
        api_key = None
    
    if not url:
        logger.warning("QDRANT_URL is not set in environment variables. Falling back to local memory (only useful for testing).")
        _QDRANT_CLIENT = QdrantClient(":memory:")
    else:
        logger.info(f"Connecting to Qdrant at {url}")
        _QDRANT_CLIENT = QdrantClient(url=url, api_key=api_key)
        
    return _QDRANT_CLIENT

class QdrantManager:
    """Unified client for Qdrant ingestion and retrieval operations."""
    
    def __init__(self, server_id: str, config: Any, vector_size: int = 384):
        self.server_id = server_id
        self.config = config
        self.vector_size = vector_size
        
        self.client = get_qdrant_client()
        
        # Determine collection name
        prefix = getattr(config.qdrant, 'collection_prefix', 'server_')
        self.collection_name = f"{prefix}{sanitize_collection_name(server_id)}"

        # State file path (still kept local)
        # Using the same path as before to maintain backward compatibility with local state
        # In retrieval config it's `config.qdrant.vectordb_dir`, in ingestion it's `config.vectordb_dir`
        try:
            vectordb_dir = config.qdrant.vectordb_dir
        except AttributeError:
            vectordb_dir = getattr(config, 'vectordb_dir', 'LocalState')
            
        self.db_path = config.get_absolute_path(vectordb_dir) / server_id
        self.state_file_path = self.db_path / "ingestion_state.json"
        
        # Load state if exists
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load incremental ingestion state from disk."""
        state = {"files": {}, "bm25_stats": {"N": 0, "total_len": 0, "df": {}}}
        if self.state_file_path.exists():
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    loaded_state = json.load(f)
                    state["files"] = loaded_state.get("files", {})
                    state["bm25_stats"] = loaded_state.get("bm25_stats", state["bm25_stats"])
            except Exception as e:
                logger.warning(f"Failed to load ingestion state for server ID '{self.server_id}': {e}. Starting fresh.")
        return state

    def save_state(self):
        """Save incremental ingestion state to disk."""
        try:
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save ingestion state for server ID '{self.server_id}': {e}")

    def get_bm25_stats(self) -> Dict[str, Any]:
        """Get BM25 statistics from state."""
        return self.state.get("bm25_stats", {})

    def is_file_unchanged(self, filename: str, stat_info: dict) -> bool:
        """Check if the object metadata matches the indexed file metadata."""
        if filename not in self.state["files"]:
            return False
        stored = self.state["files"][filename]
        return (stored.get("size") == stat_info.get("size") and stored.get("mtime") == stat_info.get("mtime"))

    def mark_file_indexed(self, filename: str, stat_info: dict):
        """Record object metadata in state after indexing."""
        self.state["files"][filename] = {
            "size": stat_info.get("size"),
            "mtime": stat_info.get("mtime")
        }

    def ensure_collection_exists(self, force_recreate: bool = False):
        """Create or recreate the collection with correct vector parameter config."""
        exists = self.client.collection_exists(self.collection_name)
        if exists and force_recreate:
            logger.info(f"Rebuilding index: Decreating collection '{self.collection_name}'...")
            self.client.delete_collection(self.collection_name)
            exists = False
            
        if not exists:
            logger.info(f"Creating collection '{self.collection_name}' with vector dimension {self.vector_size}...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(size=self.vector_size, distance=models.Distance.COSINE),
                sparse_vectors_config={
                    "text-sparse": models.SparseVectorParams(
                        index=models.SparseIndexParams(on_disk=False)
                    )
                }
            )
            self.client.create_payload_index(collection_name=self.collection_name, field_name="source_file", field_schema=models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(collection_name=self.collection_name, field_name="channel", field_schema=models.PayloadSchemaType.KEYWORD)
            self.client.create_payload_index(
                collection_name=self.collection_name, 
                field_name="text", 
                field_schema=models.TextIndexParams(type="text", tokenizer=models.TokenizerType.WORD, lowercase=True)
            )

    def remove_file_vectors(self, filename: str):
        """Delete all points associated with a specific source file name."""
        logger.info(f"Removing old vector points for file: {filename}")
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[models.FieldCondition(key="source_file", match=models.MatchValue(value=filename))]
            )
        )
        if filename in self.state["files"]:
            del self.state["files"][filename]

    def upsert_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]], sparse_vectors: List[Tuple[List[int], List[float]]] = None):
        """Batch upsert points (vectors + payload) to the Qdrant collection."""
        if not chunks: return
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            uuid_str = format_uuid(chunk["id"])
            payload = {"text": chunk["text"], **chunk["metadata"]}
            vector_dict = {"": embedding}
            if sparse_vectors and i < len(sparse_vectors):
                indices, values = sparse_vectors[i]
                if indices:
                    vector_dict["text-sparse"] = models.SparseVector(indices=indices, values=values)
            points.append(models.PointStruct(id=uuid_str, vector=vector_dict, payload=payload))

        logger.info(f"Upserting {len(points)} points into Qdrant collection '{self.collection_name}'...")
        self.client.upsert(collection_name=self.collection_name, points=points)

    def get_collection_info(self) -> Dict[str, Any]:
        """Get collection metrics like point count."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {"collection_name": self.collection_name, "points_count": info.points_count, "status": info.status}
        except Exception as e:
            logger.error(f"Error fetching collection info: {e}")
            return {"error": str(e)}

    def resolve_server_name(self) -> str:
        """Fetch the server name stored in the payloads of this collection."""
        try:
            if not self.client.collection_exists(self.collection_name): return "Unknown Server"
            response, _ = self.client.scroll(collection_name=self.collection_name, limit=1, with_payload=True, with_vectors=False)
            if response and response[0].payload:
                return response[0].payload.get("server") or "Unknown Server"
        except Exception as e:
            logger.warning(f"Error scrolling server name for ID '{self.server_id}': {e}")
        return "Unknown Server"

    def semantic_search(self, query_vector: List[float], limit: int = 5, filters: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None) -> List[models.ScoredPoint]:
        """Perform a dense vector similarity search."""
        if not self.client.collection_exists(self.collection_name): return []
        qdrant_filter = build_qdrant_filter(filters)
        response = self.client.query_points(collection_name=self.collection_name, query=query_vector, query_filter=qdrant_filter, score_threshold=score_threshold, limit=limit)
        return response.points

    def lexical_search(self, query_text: str, limit: int = 5, filters: Optional[Dict[str, Any]] = None) -> List[models.Record]:
        """Perform a full-text exact match search using scroll."""
        if not self.client.collection_exists(self.collection_name): return []
        conditions = [models.FieldCondition(key="text", match=models.MatchText(text=query_text))]
        if filters:
            q_filter = build_qdrant_filter(filters)
            if q_filter and q_filter.must:
                conditions.extend(q_filter.must)
        scroll_filter = models.Filter(must=conditions)
        response, _ = self.client.scroll(collection_name=self.collection_name, scroll_filter=scroll_filter, limit=limit, with_payload=True, with_vectors=False)
        return response

    def sparse_search(self, sparse_indices: List[int], sparse_values: List[float], limit: int = 5, filters: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None) -> List[models.ScoredPoint]:
        """Perform a sparse vector BM25 search."""
        if not self.client.collection_exists(self.collection_name): return []
        if not sparse_indices: return []
        qdrant_filter = build_qdrant_filter(filters)
        response = self.client.query_points(
            collection_name=self.collection_name,
            query=models.SparseVector(indices=sparse_indices, values=sparse_values),
            using="text-sparse", query_filter=qdrant_filter, score_threshold=score_threshold, limit=limit
        )
        return response.points

    def hybrid_search(self, query_dense: List[float], sparse_indices: List[int], sparse_values: List[float], limit: int = 5, prefetch_limit: int = 50, filters: Optional[Dict[str, Any]] = None, score_threshold: Optional[float] = None) -> List[models.ScoredPoint]:
        """Perform native hybrid search using Reciprocal Rank Fusion on prefetch lists."""
        if not self.client.collection_exists(self.collection_name): return []
        qdrant_filter = build_qdrant_filter(filters)
        prefetch_queries = [models.Prefetch(query=query_dense, using="", limit=prefetch_limit, filter=qdrant_filter)]
        if sparse_indices:
            prefetch_queries.append(models.Prefetch(query=models.SparseVector(indices=sparse_indices, values=sparse_values), using="text-sparse", limit=prefetch_limit, filter=qdrant_filter))
        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=prefetch_queries,
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            score_threshold=score_threshold, limit=limit
        )
        return response.points
