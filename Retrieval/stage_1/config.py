import os
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class QdrantConfig(BaseModel):
    vectordb_dir: str = Field(default="../LocalState")
    collection_prefix: str = Field(default="discord_")
    prefer_grpc: bool = Field(default=False)

class EmbeddingConfig(BaseModel):
    model_name: str = Field(default="all-MiniLM-L6-v2")
    batch_size: int = Field(default=32)

class BM25Config(BaseModel):
    k1: float = Field(default=1.2)
    b: float = Field(default=0.75)

class RRFConfig(BaseModel):
    k: int = Field(default=60)
    dense_weight: float = Field(default=1.0)
    sparse_weight: float = Field(default=1.0)

class RetrievalConfig(BaseModel):
    mode: str = Field(default="hybrid")
    limit: int = Field(default=5)
    prefetch_limit: int = Field(default=50)
    score_threshold: Optional[float] = Field(default=None)
    rerank: bool = Field(default=False)
    rerank_prefetch_limit: int = Field(default=20)
    rrf: RRFConfig = Field(default_factory=RRFConfig)
    filters: Dict[str, Any] = Field(default_factory=dict)

class RerankerConfig(BaseModel):
    model_name: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")
    batch_size: int = Field(default=32)

class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    log_file: str = Field(default="../logs/retrieval.log")

class AppConfig(BaseModel):
    data_dir: str = Field(default="../scrapedData/discord_exports")
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    bm25: BM25Config = Field(default_factory=BM25Config)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def get_absolute_path(self, relative_path: str) -> Path:
        """Resolve paths relative to the Retrieval directory."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        
        return (Path(__file__).parent.parent / path).resolve()

def load_config(config_path: str = None) -> AppConfig:
    """Load configuration from YAML file or return defaults."""
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config" / "config.yaml")
    
    if not os.path.exists(config_path):
        return AppConfig()
        
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    return AppConfig(**data)
