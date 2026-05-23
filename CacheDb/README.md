# CacheDb Module

The `CacheDb` module provides a decoupled, global abstraction layer for all Key-Value caching requirements across the Discos project. It prevents any module from being tightly coupled to a specific caching technology.

## Architecture

| Component | Role |
|-----------|------|
| `base.py` | Defines the `BaseCacheClient` abstract interface (get, set, delete, exists, flush, health_check). |
| `factory.py` | Exports `get_cache_client()` — returns the active singleton cache client. |
| `redis_client.py` | Primary concrete implementation using `redis-py`. Gracefully falls back to the `InMemoryFallbackClient` if Redis is unavailable. |

## Redis Setup

By default, the factory initializes `RedisCacheClient`. Ensure a Redis server is running and accessible. Configure the connection in `.env`:

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=your_password  
```

> [!TIP]
> If Redis is unavailable at startup, the system automatically falls back to an in-process `InMemoryFallbackClient` so the bot continues to function. Caching will not persist across restarts in fallback mode.

## Module Integrations

The `CacheDb` is currently used by two subsystems:

### 1. Semantic Response Cache (`Endpoint/generation_endpoint`)

Caches LLM-generated answers keyed by a hash of `(server_id, query)`. If the same query is repeated, the cached response is returned instantly, bypassing the entire Retrieval + Generation pipeline.

- TTL is controlled via `cache.semantic_cache_ttl_seconds` in `Endpoint/generation_endpoint/config.yaml`.
- Enable/disable via `cache.enable_semantic_cache: true/false`.

### 2. Distributed LangGraph Document Store (`Generation/storage`)

Replaces LangGraph's default process-locked `InMemoryDocumentStore` with a Redis-backed `KeyValueDocumentStore`. This allows retrieved context documents to be shared across multiple async workers, enabling horizontal scaling.

All TTLs and specific cache behaviors are owned by the consuming modules — `CacheDb` remains a pure, stateless abstraction.
