import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("objectStore.config")

@dataclass
class ObjectStoreConfig:
    provider: str
    endpoint: str
    port: int
    use_ssl: bool
    access_key: str
    secret_key: str
    default_bucket: str

def get_config() -> ObjectStoreConfig:
    """Loads and validates the object store configuration from environment variables."""
    provider = os.getenv("OBJECT_STORE_PROVIDER", "minio").lower()
    endpoint = os.getenv("OBJECT_STORE_ENDPOINT", "localhost")
    
    try:
        port = int(os.getenv("OBJECT_STORE_PORT", "9000"))
    except ValueError:
        logger.warning("Invalid OBJECT_STORE_PORT, defaulting to 9000")
        port = 9000

    use_ssl_str = str(os.getenv("OBJECT_STORE_USE_SSL", "false")).lower()
    use_ssl = use_ssl_str in ("true", "1", "yes")

    access_key = os.getenv("OBJECT_STORE_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("OBJECT_STORE_SECRET_KEY", "minioadmin")
    default_bucket = os.getenv("OBJECT_STORE_DEFAULT_BUCKET", "app-storage")

    return ObjectStoreConfig(
        provider=provider,
        endpoint=endpoint,
        port=port,
        use_ssl=use_ssl,
        access_key=access_key,
        secret_key=secret_key,
        default_bucket=default_bucket
    )
