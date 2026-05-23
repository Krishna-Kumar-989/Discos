import os
from pathlib import Path
from typing import Optional
import yaml
from pydantic import BaseModel, Field
from dotenv import load_dotenv


dotenv_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path, override=True)

class QnAWorkflowConfig(BaseModel):
    provider: str = Field(default="mock")
    model: str = Field(default="mock-model")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    prompt_template: str = Field(default="QnA_workflow/default_rag.txt")
    enable_query_rewrite: bool = Field(default=False)

class SummaryWorkflowConfig(BaseModel):
    provider: str = Field(default="mock")
    model: str = Field(default="mock-model")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=1000)
    filter_extraction_template: str = Field(default="Summary_workflow/filter_extraction.txt")
    summarization_template: str = Field(default="Summary_workflow/summarization.txt")

class GenerationConfig(BaseModel):
    workflow_type: str = Field(default="QnA_workflow")
    QnA_workflow: QnAWorkflowConfig = Field(default_factory=QnAWorkflowConfig)
    Summary_workflow: SummaryWorkflowConfig = Field(default_factory=SummaryWorkflowConfig)

class RetrievalConfig(BaseModel):
    mode: str = Field(default="hybrid")
    limit: int = Field(default=5)
    rerank: bool = Field(default=False)
    rerank_prefetch_limit: int = Field(default=20)

class StorageConfig(BaseModel):
    cache_ttl_seconds: int = Field(default=3600)

class CacheConfig(BaseModel):
    document_store_ttl_seconds: int = Field(default=3600)
    enable_semantic_cache: bool = Field(default=False)
    semantic_cache_ttl_seconds: int = Field(default=3600)

class LoggingConfig(BaseModel):
    level: str = Field(default="INFO")
    log_file: str = Field(default="../logs/generation.log")

class AppConfig(BaseModel):
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """Resolve paths relative to the Generation directory."""
        path = Path(relative_path)
        if path.is_absolute():
            return path
        return (Path(__file__).parent.parent / path).resolve()

def load_config(config_path: Optional[str] = None) -> AppConfig:
    if config_path is None:
        config_path = str(Path(__file__).parent.parent / "config" / "config.yaml")
        
    if not os.path.exists(config_path):
        return AppConfig()
        
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
        
    return AppConfig(**data)
