import logging
from typing import List

try:
    from stage_1.config import AppConfig
except ImportError:
    from Retrieval.stage_1.config import AppConfig

logger = logging.getLogger("retrieval.embeddings")

class EmbeddingGenerator:
    """Generates query embeddings using a configurable SentenceTransformer model."""
    
    def __init__(self, config: AppConfig):
        self.config = config.embedding
        self.model_name = self.config.model_name
        self.model = None

    def _ensure_model_loaded(self):
        """Load the model only when it is actually needed (lazy loading)."""
        if self.model is not None:
            return
            
        try:
            import os
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            import logging as hf_logging
            hf_logging.getLogger("transformers.modeling_utils").setLevel(hf_logging.ERROR)
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
            self.model = SentenceTransformer(self.model_name)
            logger.info("Model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer model '{self.model_name}': {e}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the dimension of the embedding vectors produced by this model."""
        self._ensure_model_loaded()
        return int(self.model.get_sentence_embedding_dimension())

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of strings in batches."""
        if not texts:
            return []
            
        self._ensure_model_loaded()
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.config.batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}")
            raise
