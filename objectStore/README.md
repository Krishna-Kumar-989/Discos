# objectStore Module

A provider-agnostic, abstraction-based module for interacting with Object Storage (e.g., MinIO, AWS S3, GCS). Used by the `Scrapper`, `Ingestion`, and `Endpoint` (conversation history logging) subsystems.

## Architecture

This module follows a strict **Interface → Provider → Service** pattern:

| Component | Role |
|-----------|------|
| `interfaces.py` | Defines the `ObjectStoreProvider` ABC. Every provider must implement all methods here. |
| `providers/minio_provider.py` | Concrete MinIO implementation. |
| `service.py` | `ObjectStoreService` — factory wrapper that delegates to the active provider. Exposes `get_object_store()` singleton. |
| `config.py` | Reads all `OBJECT_STORE_*` environment variables into an `ObjectStoreConfig` dataclass. |
| `exceptions.py` | Standardized exceptions thrown by all providers, so calling code never needs to handle provider-specific errors. |

## Configuration

Set these in your `.env` file:

```env
OBJECT_STORE_PROVIDER="minio"          # Provider: "minio" (more coming)
OBJECT_STORE_ENDPOINT="localhost"
OBJECT_STORE_PORT=9000
OBJECT_STORE_USE_SSL=false
OBJECT_STORE_ACCESS_KEY="minioadmin"
OBJECT_STORE_SECRET_KEY="minioadmin"
OBJECT_STORE_DEFAULT_BUCKET="app-storage"
```

## Object Key Conventions

| Data Type | Object Key Pattern |
|-----------|-------------------|
| Scraped Discord exports | `discord_exports/<guild_id>/<channel_name>_<date>.json` |
| Conversation history logs | `conversation_history/<guild_id>/<run_id>.json` |

## Usage

```python
from objectStore import get_object_store
import io, json

store = get_object_store()  # Singleton — initialized once

# Upload a JSON object from memory
data = json.dumps({"key": "value"}).encode("utf-8")
store.upload_object("my/object/key.json", io.BytesIO(data), content_type="application/json")

# Read it back
raw = store.read_object("my/object/key.json")
payload = json.loads(raw.decode("utf-8"))

# Check existence
if store.object_exists("my/object/key.json"):
    print("Found!")

# List objects under a prefix
keys = store.list_objects(prefix="discord_exports/1234567890/")

# Get file metadata
stat = store.stat_object("my/object/key.json")
print(stat["size"], stat["mtime"])
```

## Adding a New Provider

1. Create `providers/<name>_provider.py` and subclass `ObjectStoreProvider`.
2. Implement all abstract methods from `interfaces.py`.
3. Register it in `service.py`'s `_resolve_provider()` factory method.
