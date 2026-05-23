# Discos Retrieval Subsystem

The Retrieval module is a modular, two-stage search framework that fetches contextually relevant Discord message chunks from Qdrant for a given user query.

## Architecture Overview

### Stage 1: Candidate Retrieval (`stage_1/`)

Fetches a broad set of candidate documents using one or more of the following strategies, then fuses them:

| Mode | Description |
|------|-------------|
| `semantic` | Dense vector similarity search using SentenceTransformer embeddings. |
| `lexical` | Exact keyword full-text match using Qdrant's `MatchText` index. |
| `sparse` | BM25 sparse vector search for precise term frequency matching. |
| `hybrid` | Runs semantic + sparse in parallel and merges results using **Reciprocal Rank Fusion (RRF)**. |

**Components:**
- `stage_1/retriever.py` — Orchestrates multi-modal lookups.
- `stage_1/embeddings.py` — Generates query embeddings.
- `stage_1/bm25.py` — Encodes queries into sparse BM25 vectors.
- `stage_1/fusion.py` — RRF score merging.
- `stage_1/config.py` — Pydantic config schema (reads `config/config.yaml`).

### Stage 2: Cross-Encoder Reranking (`stage_2/`)

Takes the top-K candidates from Stage 1 and re-scores each `(query, document)` pair using a transformer Cross-Encoder model for fine-grained contextual relevance ordering.

- `stage_2/reranker.py` — Loads and runs the `cross-encoder/ms-marco-MiniLM-L-6-v2` model.

---

## Configuration

Settings are in `config/config.yaml`:

```yaml
qdrant:
  vectordb_dir: "../LocalState"   # Local ingestion state tracking dir
  collection_prefix: "discord_"

retrieval:
  mode: "hybrid"
  limit: 5
  rerank: false
  rerank_prefetch_limit: 20

reranker:
  model_name: "cross-encoder/ms-marco-MiniLM-L-6-v2"
```

---

## CLI Usage

Run from the project root:

```bash
python Retrieval/cli.py --query "your search query" --server <server_name_or_id> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--query` | (Required) Search query string. |
| `--server` | (Required) Server name or Guild ID. |
| `--mode` | Search mode: `semantic`, `lexical`, `sparse`, or `hybrid`. |
| `--limit` | Number of documents to return. |
| `--rerank` | Enable Stage-2 Cross-Encoder reranking. |
| `--no-rerank` | Disable Stage-2 reranking. |
| `--config` | Path to a custom config YAML file. |
