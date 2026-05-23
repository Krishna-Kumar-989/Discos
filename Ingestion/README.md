# Discos Ingestion Pipeline

The Ingestion module reads raw Discord JSON exports directly from the **Object Store**, processes them into chunked, multi-vector embeddings, and indexes them into the **Qdrant Vector Database**. It tracks ingestion state locally in `LocalState/` to avoid redundant re-embedding of unchanged files.

## Component Architecture

| File | Role |
|------|------|
| `loaders.py` | Streams JSON exports from the `objectStore` and extracts messages, metadata, and channel details. |
| `chunkers.py` | Sliding-window chunking of messages to create context-rich, overlapping document chunks. |
| `embeddings.py` | Generates dense vector embeddings using SentenceTransformers. |
| `bm25.py` | Builds sparse BM25 vectors for precise keyword matching. |
| `pipeline.py` | Orchestrator that wires loader → chunker → embedder → qdrant upsert. |
| `cli.py` | Command-line interface to run, inspect, and test the indexing pipeline. |
| `config.py` / `config.yaml` | Pydantic-parsed configuration for all pipeline settings. |

> The `qdrant/client.py` module (shared across the project) handles collection management and incremental state tracking via `LocalState/<server_id>/ingestion_state.json`.

## Configuration

Settings are managed via `config.yaml`:

```yaml
vectordb_dir: "../LocalState"    # Local state tracking dir
chunking:
  chunk_size: 1000               # Max characters per chunk
  overlap: 200                   # Overlap between adjacent chunks
embedding:
  model_name: "all-MiniLM-L6-v2"
  batch_size: 32
qdrant:
  collection_prefix: "discord_"
```

## Usage

Run from the project root directory via the Endpoint CLI:

### Index a Discord Server
```bash
python Endpoint/ingestion_endpoint/cli.py
```

Or run directly from within the `Ingestion/` directory:
```bash
# Ingest (incremental — only processes new/changed files)
python cli.py ingest --server <server_name_or_id>

# Rebuild from scratch (wipes existing Qdrant collection)
python cli.py ingest --server <server_name_or_id> --rebuild
```

### Check Indexing Status
```bash
python cli.py status
```

### Test Search Directly
```bash
python cli.py query --server <server_name_or_id> --text "your query" --mode hybrid
```

### Programmatic Trigger
```python
from Endpoint import trigger_ingestion
result = trigger_ingestion(server_id="1234567890")
```
