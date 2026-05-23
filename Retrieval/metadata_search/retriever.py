import logging
import asyncio
from typing import List, Dict, Any, Optional

from Retrieval.stage_1.retriever import Stage1Retriever
from Retrieval.metadata_search.client import MetadataSearchClient
from Generation.pipeline.config import load_config, AppConfig

logger = logging.getLogger("retrieval.metadata_retriever")

class MetadataRetriever(Stage1Retriever):
    """Orchestrates pure metadata retrieval across servers."""
    
    def __init__(self, config: Optional[AppConfig] = None):
        super().__init__(config)
        
    def _query_single_server_sync(
        self,
        server_id: str,
        filters: Dict[str, Any],
        limit: int
    ) -> List[Dict[str, Any]]:
        client = MetadataSearchClient(server_id, self.config)
        server_name = client.resolve_server_name()
        
        if not client.client.collection_exists(client.collection_name):
            logger.warning(f"Qdrant collection '{client.collection_name}' not found for server ID {server_id}")
            return []
            
        hits = []
        records = client.metadata_search(filters=filters, limit=limit)
        
        for record in records:
            payload = record.payload or {}
            # Score is None for metadata-only searches since it's just filtering
            hits.append(self._format_hit(str(record.id), None, payload, server_name, server_id))
            
        return hits

    async def retrieve_metadata(
        self,
        server_name_or_id: str,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Asynchronously perform metadata-only document retrieval."""
        resolved_id = self.resolve_server_id(server_name_or_id)
        if not resolved_id:
            logger.error(f"Failed to resolve server: '{server_name_or_id}'")
            return []
            
        hits = await asyncio.to_thread(
            self._query_single_server_sync,
            server_id=resolved_id,
            filters=filters,
            limit=limit
        )
        
        return hits
