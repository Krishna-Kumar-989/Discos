# Discos Pipeline Endpoints

The `Endpoint` module serves as the centralized entry point and unified interface layer for the **Discos** project. It wraps the core processing subsystems (Scraping, Ingestion, and Generation (RAG)) into clean, decoupled APIs and interactive Command Line Interfaces (CLIs).

By encapsulating imports, environment initialization, and modular isolation, the Endpoint layer allows the Discord frontend (or any external service) to trigger pipelines without directly binding to the internal database or model orchestration logic.

---

## Directory Overview

```
Endpoint/
├── __init__.py                # Package exports for clean imports
├── test_endpoints.py          # Testing suite for validation
├── scrapper_endpoint/         # Subsystem to extract Discord chat logs
│   ├── cli.py                 # Interactive terminal scraper
│   └── trigger.py             # Programmatic scraper trigger
├── ingestion_endpoint/        # Subsystem to process and vector-index messages
│   ├── cli.py                 # Interactive terminal indexer
│   └── trigger.py             # Programmatic ingestion trigger
└── generation_endpoint/       # Subsystem to query the LangGraph RAG engine
    ├── cli.py                 # Interactive chatbox interface
    ├── config.yaml            # Configs for caches & logging
    └── query.py               # Programmatic Q&A & Summarization query runner
```

---

## Unified Programmatic API

All main entry points are exposed at the package level in [Endpoint/__init__.py](__init__.py):

```python
from Endpoint import (
    query_generation_pipeline,
    trigger_ingestion,
    trigger_scrapper
)
```

### 1. Scraper Endpoint (`trigger_scrapper`)
Triggers the Discord scraper to crawl message histories, channels, and threads for the specified Discord server (guild).

```python
async def trigger_scrapper(
    server_id: str, 
    discord_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Args:
        server_id: Discord server ID or name.
        discord_token: Bot token (defaults to loading from project root .env).
    """
```

### 2. Ingestion Endpoint (`trigger_ingestion`)
Takes the scraped logs, processes them (cleanses, chunks, generates embeddings), and updates the Vector/BM25 indices.

```python
def trigger_ingestion(
    server_id: str,
    rebuild: bool = False,
    config_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Args:
        server_id: Discord server ID or name to ingest.
        rebuild: Rebuild index from scratch, clearing existing data for this server.
        config_path: Custom configuration file path.
    """
```

### 3. Generation Endpoint (`query_generation_pipeline`)
Queries the LangGraph pipeline (supports QA & Summarization workflows) with context retrieval, LLM parsing, semantic response caching, and conversation history logging.

```python
async def query_generation_pipeline(
    query: str,
    server_id: str,
    mode: Optional[str] = None,          # 'semantic', 'lexical', 'sparse', 'hybrid'
    limit: Optional[int] = None,          # context document limit
    rerank: Optional[bool] = None,        # reranking toggle
    provider: Optional[str] = None,      # 'groq', 'openai', etc.
    model: Optional[str] = None,         # model identifier override
    workflow_type: Optional[str] = None, # 'QnA_workflow' or 'Summary_workflow'
    user_id: Optional[str] = None
) -> Dict[str, Any]:
```

---

## CLI Tools

Each endpoint includes an interactive CLI script to test and run the pipelines independently from the Discord Bot app.

> [!TIP]
> Ensure you run these commands from the project root directory and that your `.env` file is fully configured.

### Discord Scraper CLI
Launch the scraper to crawl discord messages from channels your bot resides in:
```bash
python Endpoint/scrapper_endpoint/cli.py
```

### Data Ingestion CLI
Embed and index crawled raw messages:
```bash
python Endpoint/ingestion_endpoint/cli.py
```

### Simple Chatbox RAG CLI
Interact directly with the indexed documents of your servers:
```bash
python Endpoint/generation_endpoint/cli.py
```

---

## Semantic Cache & Logging

The Generation Endpoint utilizes a fast caching and conversation logging mechanism controlled via [Endpoint/generation_endpoint/config.yaml](generation_endpoint/config.yaml):

- **Semantic Caching**: Automatically computes a hash of the query and server parameters. If enabled, it fetches cached LLM responses from the central `CacheDb` (Redis) layer, bypassing expensive retriever/generation pipelines.
- **Conversation Logs**: Successful execution runs are recorded as JSON files in the Object Store (MinIO/S3) under `conversation_history/<server_id>/<run_id>.json` and additionally saved to the `DataDb` database, containing user query, retrieved documents, prompts, and timestamps.
