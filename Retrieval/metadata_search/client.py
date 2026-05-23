import logging
from typing import Dict, Any, List

from qdrant_client import models
from qdrant.client import QdrantManager, build_qdrant_filter
from Generation.pipeline.config import AppConfig

logger = logging.getLogger("retrieval.metadata_client")

class MetadataSearchClient(QdrantManager):
    """Client for performing pure metadata filtering without vector or text search."""
    
    def __init__(self, server_id: str, config: AppConfig):
        super().__init__(server_id, config)
        
    def metadata_search(
        self,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[models.Record]:
        """Perform a metadata-only search using Qdrant scroll API."""
        if not self.client.collection_exists(self.collection_name):
            return []
            
        q_filter = build_qdrant_filter(filters)
        
        response, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=q_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False
        )
        return response
