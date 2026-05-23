# Qdrant Module

The `qdrant` module is a shared, centralized layer that encapsulates all direct interactions with the **Qdrant Vector Database**. It is used by both the `Ingestion` and `Retrieval` subsystems.

## Architecture

This module interacts with a **single external Qdrant instance** and creates isolated **collections** (one per Discord Guild) to keep server data completely separated.

| Component | Role |
|-----------|------|
| `client.py` | Contains `QdrantManager` (collection management, upsert, search, state tracking) and the `get_qdrant_client()` singleton factory. |

## Configuration

Connection details are read from environment variables:

### External Hosted Qdrant (Qdrant Cloud or self-hosted)
```env
QDRANT_URL="https://your-cluster-url.cloud.qdrant.io"
QDRANT_API_KEY="your_api_key"
```

### Local Qdrant Instance (e.g. Docker)
```env
QDRANT_URL="http://localhost:6333"
# Leave QDRANT_API_KEY empty or omit it
```

> [!NOTE]
> If `QDRANT_URL` is not set at all, the system falls back to an in-memory Qdrant instance (useful only for unit testing — data is lost on exit).

## State Management

Incremental ingestion state is tracked locally to avoid re-embedding files that haven't changed. The state file is stored in the `LocalState/` directory:

```
LocalState/
└── <server_id>/
    └── ingestion_state.json   # Tracks object size + last-modified time per file
```

This path is configured via `qdrant.vectordb_dir` in the respective `config.yaml` files (Ingestion and Retrieval modules). The `LocalState/` directory is a local-only artifact and should be added to `.gitignore`.

## Collection Naming

Each Discord guild gets its own Qdrant collection, named using a configurable prefix:

```
discord_<sanitized_guild_id>
```

The sanitizer replaces all non-alphanumeric characters with underscores to ensure valid collection names.
