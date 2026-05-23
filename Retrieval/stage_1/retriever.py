import asyncio
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from stage_1.config import load_config, AppConfig
    from stage_1.embeddings import EmbeddingGenerator
    from stage_1.bm25 import BM25Vectorizer
    from stage_1.fusion import reciprocal_rank_fusion
    from qdrant.client import QdrantManager
except ImportError:
    from Retrieval.stage_1.config import load_config, AppConfig
    from Retrieval.stage_1.embeddings import EmbeddingGenerator
    from Retrieval.stage_1.bm25 import BM25Vectorizer
    from Retrieval.stage_1.fusion import reciprocal_rank_fusion
    from qdrant.client import QdrantManager

logger = logging.getLogger("retrieval.retriever")

class Stage1Retriever:
    """Orchestrates the Stage-1 hybrid retrieval pipeline."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or load_config()
        self.embedding_generator = EmbeddingGenerator(self.config)

    def get_available_servers(self) -> List[str]:
        """List all server/guild IDs that are currently indexed in the vector database directory."""
        vectordb_dir = self.config.get_absolute_path(self.config.qdrant.vectordb_dir)
        server_ids = []
        if vectordb_dir.exists() and vectordb_dir.is_dir():
            for item in vectordb_dir.iterdir():
                # Server directories contain segment files and ingestion states
                if item.is_dir() and (item / "ingestion_state.json").exists():
                    server_ids.append(item.name)
        return sorted(server_ids)

    def resolve_server_id(self, server_name_or_id: str) -> Optional[str]:
        """Resolve a server name or ID to the corresponding guild ID folder name."""
        available_ids = self.get_available_servers()
        if server_name_or_id in available_ids:
            return server_name_or_id
            
        # Search by connecting to each DB and fetching resolved server name
        for s_id in available_ids:
            client = QdrantManager(s_id, self.config)
            name = client.resolve_server_name()
            if name.lower() == server_name_or_id.lower():
                return s_id
                
        return None

    def _format_hit(self, hit_id: str, score: Optional[float], payload: Dict[str, Any], server_name: str, server_id: str) -> Dict[str, Any]:
        """Format raw search result into standard dictionary structure."""
        return {
            "id": hit_id,
            "score": score,
            "text": payload.get("text", ""),
            "source_file": payload.get("source_file", ""),
            "start_timestamp": payload.get("start_timestamp", ""),
            "end_timestamp": payload.get("end_timestamp", ""),
            "channel": payload.get("channel", ""),
            "channel_id": payload.get("channel_id", ""),
            "server": server_name,
            "server_id": server_id,
            "metadata": {k: v for k, v in payload.items() if k not in ["text", "source_file", "start_timestamp", "end_timestamp", "channel", "channel_id", "server"]}
        }

    def _query_single_server_sync(
        self,
        server_id: str,
        query: str,
        mode: str,
        limit: int,
        prefetch_limit: int,
        score_threshold: Optional[float],
        filters: Optional[Dict[str, Any]],
        dense_vector: List[float]
    ) -> List[Dict[str, Any]]:
        """Synchronously query a single Qdrant server database. Meant to run inside thread executors."""
        client = QdrantManager(server_id, self.config)
        server_name = client.resolve_server_name()
        
        if not client.client.collection_exists(client.collection_name):
            logger.warning(f"Qdrant collection '{client.collection_name}' not found for server ID {server_id}")
            return []

        hits = []
        
        if mode == "lexical":
            records = client.lexical_search(query, limit=limit, filters=filters)
            for record in records:
                payload = record.payload or {}
                hits.append(self._format_hit(record.id, None, payload, server_name, server_id))
                
        elif mode == "sparse":
            stats = client.get_bm25_stats()
            vectorizer = BM25Vectorizer(**stats, k1=self.config.bm25.k1, b=self.config.bm25.b)
            sparse_indices, sparse_values = vectorizer.vectorize(query)
            points = client.sparse_search(
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                limit=limit,
                filters=filters,
                score_threshold=score_threshold
            )
            for pt in points:
                payload = pt.payload or {}
                hits.append(self._format_hit(pt.id, pt.score, payload, server_name, server_id))
                
        elif mode == "hybrid":
            stats = client.get_bm25_stats()
            vectorizer = BM25Vectorizer(**stats, k1=self.config.bm25.k1, b=self.config.bm25.b)
            sparse_indices, sparse_values = vectorizer.vectorize(query)
            points = client.hybrid_search(
                query_dense=dense_vector,
                sparse_indices=sparse_indices,
                sparse_values=sparse_values,
                limit=limit,
                prefetch_limit=prefetch_limit,
                filters=filters,
                score_threshold=score_threshold
            )
            for pt in points:
                payload = pt.payload or {}
                hits.append(self._format_hit(pt.id, pt.score, payload, server_name, server_id))
                
        else: # semantic
            points = client.semantic_search(
                query_vector=dense_vector,
                limit=limit,
                filters=filters,
                score_threshold=score_threshold
            )
            for pt in points:
                payload = pt.payload or {}
                hits.append(self._format_hit(pt.id, pt.score, payload, server_name, server_id))
                
        return hits

    async def retrieve(
        self,
        query: str,
        server_name_or_id: Optional[str] = None,
        mode: Optional[str] = None,
        limit: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Asynchronously perform Stage-1 document retrieval.
        
        Args:
            query: The search query string.
            server_name_or_id: Optional server name or Guild ID folder name. If None, queries all servers.
            mode: Search mode: 'semantic', 'lexical', 'sparse', or 'hybrid'. Defaults to config settings.
            limit: Maximum number of results to return. Defaults to config settings.
            filters: Optional metadata filters. Defaults to config settings.
            
        Returns:
            A list of ranked, structured retrieval result dicts.
        """
        #config 
        mode = mode or self.config.retrieval.mode
        limit = limit or self.config.retrieval.limit
        filters = filters or self.config.retrieval.filters
        prefetch_limit = self.config.retrieval.prefetch_limit
        score_threshold = self.config.retrieval.score_threshold

        #resolve servers
        if not server_name_or_id:
            raise ValueError("Server name or ID must be provided. Querying all servers implicitly is disabled.")
            
        resolved_id = self.resolve_server_id(server_name_or_id)
        if not resolved_id:
            logger.error(f"Failed to resolve server: '{server_name_or_id}'")
            return []
        server_ids = [resolved_id]
            
        if not server_ids:
            logger.warning("No vector databases available for search.")
            return []

        #Generate query dense vector once 
        dense_vector = []
        if mode in ["semantic", "hybrid"]:
            # Run in thread since embedding generation is CPU/GPU intensive
            dense_vectors = await asyncio.to_thread(
                self.embedding_generator.generate_embeddings, [query]
            )
            if dense_vectors:
                dense_vector = dense_vectors[0]

        #execute queries concurrently in thread workers to avoid blocking the event loop
        tasks = [
            asyncio.to_thread(
                self._query_single_server_sync,
                server_id=server_id,
                query=query,
                mode=mode,
                limit=limit,
                prefetch_limit=prefetch_limit,
                score_threshold=score_threshold,
                filters=filters,
                dense_vector=dense_vector
            )
            for server_id in server_ids
        ]
        
        results_per_server = await asyncio.gather(*tasks)
        
        # Merge results
        if len(server_ids) == 1:
            # Single server, already ranked natively
            merged_hits = results_per_server[0]
        else:
            # Multi-server merging
            if mode == "hybrid":
                # Multi-collection Reciprocal Rank Fusion on Python side
                merged_hits = reciprocal_rank_fusion(
                    ranked_lists=results_per_server,
                    k=self.config.retrieval.rrf.k
                )
            else:
                # Merge and sort by database score (for semantic / sparse / lexical)
                all_hits = []
                for hits in results_per_server:
                    all_hits.extend(hits)
                    
                # Lexical matches won't have score, rank is arbitary. Semantic/sparse has score.
                if mode == "lexical":
                    merged_hits = all_hits
                else:
                    # Sort by score descending 
                    merged_hits = sorted(
                        all_hits,
                        key=lambda x: x.get("score") if x.get("score") is not None else -float('inf'),
                        reverse=True
                    )

        # Apply final limit
        return merged_hits[:limit]
