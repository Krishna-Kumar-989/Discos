from abc import ABC, abstractmethod
from typing import List, Optional, Any, Union
import io

class ObjectStoreProvider(ABC):
    """
    Abstract Base Class defining the contract for all Object Store providers.
    Any new provider (e.g., S3, Azure) must implement these methods.
    """

    @abstractmethod
    def initialize_client(self) -> None:
        """Initialize the connection to the object storage provider."""
        pass

    @abstractmethod
    def create_bucket(self, bucket_name: str) -> None:
        """Create a new bucket/container if it doesn't exist."""
        pass

    @abstractmethod
    def upload_object(
        self, 
        bucket_name: str, 
        object_name: str, 
        data: Union[str, io.BytesIO], 
        content_type: str = "application/octet-stream"
    ) -> None:
        """
        Upload an object to the specified bucket.
        :param data: Can be a local file path (str) or a byte stream (BytesIO).
        """
        pass

    @abstractmethod
    def download_object(self, bucket_name: str, object_name: str, destination_path: str) -> None:
        """Download an object from a bucket to a local file path."""
        pass

    @abstractmethod
    def delete_object(self, bucket_name: str, object_name: str) -> None:
        """Delete an object from the specified bucket."""
        pass

    @abstractmethod
    def list_objects(self, bucket_name: str, prefix: Optional[str] = None) -> List[str]:
        """List all object names in a bucket, optionally filtered by a prefix."""
        pass

    @abstractmethod
    def get_object_url(self, bucket_name: str, object_name: str, expires_in_seconds: int = 3600) -> str:
        """Generate a pre-signed URL to access the object."""
        pass

    @abstractmethod
    def object_exists(self, bucket_name: str, object_name: str) -> bool:
        """Check if an object exists in the specified bucket."""
        pass

    @abstractmethod
    def read_object(self, bucket_name: str, object_name: str) -> bytes:
        """Read the contents of an object directly into memory as bytes."""
        pass

    @abstractmethod
    def stat_object(self, bucket_name: str, object_name: str) -> dict:
        """
        Get metadata about an object.
        Should return a dict containing at least 'size' (int) and 'mtime' (float, unix timestamp).
        """
        pass
