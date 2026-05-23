import logging
import asyncio
from typing import List, Dict, Any, Optional

try:
    from stage_1.config import AppConfig, load_config
except ImportError:
    from Retrieval.stage_1.config import AppConfig, load_config

logger = logging.getLogger("retrieval.stage_2")

class Stage2Reranker:
    """
    Reranker for the Stage-2 retrieval pipeline.
    Uses a SentenceTransformer Cross-Encoder model to score query-document pairs.
    """
    def __init__(self, config: Optional[AppConfig] = None):
        self.app_config = config or load_config()
        self.config = self.app_config.reranker
        self.model_name = self.config.model_name
        self.model = None

    def _ensure_model_loaded(self):
        """Lazy load the CrossEncoder model when it's first needed."""
        if self.model is not None:
            return

        try:
            import os
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            import logging as hf_logging
            hf_logging.getLogger("transformers.modeling_utils").setLevel(hf_logging.ERROR)
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading CrossEncoder model '{self.model_name}'...")
            self.model = CrossEncoder(self.model_name)
            logger.info("CrossEncoder model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load CrossEncoder model '{self.model_name}': {e}")
            raise

    async def rerank(self, query: str, stage_1_results: List[Dict[str, Any]], limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Reranks the Stage-1 search results using the Cross-Encoder.
        Runs model prediction in a separate thread to avoid blocking the event loop.
        """
        if not stage_1_results:
            return []

        limit = limit or self.app_config.retrieval.limit

        self._ensure_model_loaded()
        
        logger.info(f"Stage 2 reranking {len(stage_1_results)} results with CrossEncoder '{self.model_name}'...")
        
        #Prepare query-document pairs
        pairs = [[query, hit.get("text", "")] for hit in stage_1_results]
        
        try:
            #Predict scores in a worker thread
            scores = await asyncio.to_thread(
                self.model.predict,
                pairs,
                batch_size=self.config.batch_size,
                show_progress_bar=False
            )
            
            #Update hit scores with Cross-Encoder scores
            for idx, score in enumerate(scores):
                stage_1_results[idx]["score"] = float(score)
                
            #Sort hits by new scores descending
            reranked_results = sorted(
                stage_1_results,
                key=lambda x: x["score"],
                reverse=True
            )
            
            return reranked_results[:limit]
            
        except Exception as e:
            logger.error(f"Error during CrossEncoder reranking: {e}", exc_info=True)
            #Fall back to original Stage-1 results under error condition
            return stage_1_results[:limit]
