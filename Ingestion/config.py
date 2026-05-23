import os
import yaml
from pathlib import Path
from typing import List
from pydantic import BaseModel, Field

class ChunkingConfig(BaseModel):
    chunk_size: int = Field(default=1000)
    overlap: int = Field(default=200)
    min_chunk_length: int = Field(default=50)

class EmbeddingConfig(BaseModel):
    model_name: str = Field(default="all-MiniLM-L6-v2")
    batch_size: int = Field(default=32)

class QdrantConfig(BaseModel):
    collection_prefix: str = Field(default="discord_")
    prefer_grpc: bool = Field(default=False)

class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    log_file: str = Field(default="../logs/ingestion.log")

class AppConfig(BaseModel):
    vectordb_dir: str = Field(default="../LocalState")
    supported_extensions: List[str] = Field(default_factory=lambda: [".json"])
    chunking: ChunkingConfig = Field(default_factory=ChunkingConfig)
    embedding: EmbeddingConfig = Field(default_factory=EmbeddingConfig)
    qdrant: QdrantConfig = Field(default_factory=QdrantConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    def get_absolute_path(self, relative_path: str) -> Path:
        """Resolve paths relative to the Ingestion directory."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (Path(__file__).parent / path).resolve()

def load_config(config_path: str = None) -> AppConfig:
    """Load configuration from YAML file or return defaults."""
    if config_path is None:
        config_path = str(Path(__file__).parent / "config.yaml")
    
    if not os.path.exists(config_path):
        return AppConfig()
        
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    return AppConfig(**data)
