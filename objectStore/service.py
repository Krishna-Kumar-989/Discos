from typing import Optional, List, Union
import io

from objectStore.interfaces import ObjectStoreProvider
from objectStore.config import get_config, ObjectStoreConfig
from objectStore.exceptions import ObjectStoreConfigurationError

# Import providers
from objectStore.providers.minio_provider import MinioProvider

class ObjectStoreService:
    """
    High-level functional API for the application to interact with Object Storage.
    It abstracts away the provider implementation.
    """
    def __init__(self, config: Optional[ObjectStoreConfig] = None):
        self.config = config or get_config()
        self.provider = self._resolve_provider()
        self.default_bucket = self.config.default_bucket

    def _resolve_provider(self) -> ObjectStoreProvider:
        """Factory method to resolve the correct provider based on configuration."""
        provider_name = self.config.provider.lower()
        
        if provider_name == "minio":
            return MinioProvider(self.config)
        # elif provider_name == "s3":
        #     return S3Provider(self.config)
        else:
            raise ObjectStoreConfigurationError(f"Unsupported object store provider: '{provider_name}'")

    def initialize_client(self) -> None:
        self.provider.initialize_client()

    def create_bucket(self, bucket_name: Optional[str] = None) -> None:
        target_bucket = bucket_name or self.default_bucket
        self.provider.create_bucket(target_bucket)

    def upload_object(
        self, 
        object_name: str, 
        data: Union[str, io.BytesIO], 
        bucket_name: Optional[str] = None,
        content_type: str = "application/octet-stream"
    ) -> None:
        target_bucket = bucket_name or self.default_bucket
        self.provider.upload_object(target_bucket, object_name, data, content_type)

    def download_object(self, object_name: str, destination_path: str, bucket_name: Optional[str] = None) -> None:
        target_bucket = bucket_name or self.default_bucket
        self.provider.download_object(target_bucket, object_name, destination_path)

    def delete_object(self, object_name: str, bucket_name: Optional[str] = None) -> None:
        target_bucket = bucket_name or self.default_bucket
        self.provider.delete_object(target_bucket, object_name)

    def list_objects(self, prefix: Optional[str] = None, bucket_name: Optional[str] = None) -> List[str]:
        target_bucket = bucket_name or self.default_bucket
        return self.provider.list_objects(target_bucket, prefix)

    def get_object_url(self, object_name: str, expires_in_seconds: int = 3600, bucket_name: Optional[str] = None) -> str:
        target_bucket = bucket_name or self.default_bucket
        return self.provider.get_object_url(target_bucket, object_name, expires_in_seconds)

    def object_exists(self, object_name: str, bucket_name: Optional[str] = None) -> bool:
        target_bucket = bucket_name or self.default_bucket
        return self.provider.object_exists(target_bucket, object_name)

    def read_object(self, object_name: str, bucket_name: Optional[str] = None) -> bytes:
        target_bucket = bucket_name or self.default_bucket
        return self.provider.read_object(target_bucket, object_name)

    def stat_object(self, object_name: str, bucket_name: Optional[str] = None) -> dict:
        target_bucket = bucket_name or self.default_bucket
        return self.provider.stat_object(target_bucket, object_name)


# Singleton instance manager for ease of use
_STORE_INSTANCE: Optional[ObjectStoreService] = None

def get_object_store() -> ObjectStoreService:
    """Returns a singleton instance of the ObjectStoreService."""
    global _STORE_INSTANCE
    if _STORE_INSTANCE is None:
        _STORE_INSTANCE = ObjectStoreService()
        _STORE_INSTANCE.initialize_client()
    return _STORE_INSTANCE
