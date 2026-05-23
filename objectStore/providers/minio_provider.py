import os
import io
from typing import List, Optional, Union
import urllib3

from minio import Minio
from minio.error import S3Error

from objectStore.interfaces import ObjectStoreProvider
from objectStore.config import ObjectStoreConfig
from objectStore.exceptions import (
    ObjectStoreConfigurationError,
    BucketOperationError,
    ObjectOperationError,
    ObjectNotFoundError
)

class MinioProvider(ObjectStoreProvider):
    def __init__(self, config: ObjectStoreConfig):
        self.config = config
        self.client: Optional[Minio] = None

    def initialize_client(self) -> None:
        try:
            endpoint = f"{self.config.endpoint}:{self.config.port}"
            self.client = Minio(
                endpoint=endpoint,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.use_ssl
            )
        except Exception as e:
            raise ObjectStoreConfigurationError(f"Failed to initialize MinIO client: {e}")

    def _ensure_client(self):
        if not self.client:
            self.initialize_client()

    def create_bucket(self, bucket_name: str) -> None:
        self._ensure_client()
        try:
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)
        except S3Error as e:
            raise BucketOperationError(f"Failed to create bucket '{bucket_name}': {e}")

    def upload_object(
        self, 
        bucket_name: str, 
        object_name: str, 
        data: Union[str, io.BytesIO], 
        content_type: str = "application/octet-stream"
    ) -> None:
        self._ensure_client()
        try:
            if isinstance(data, str):
                # It's a file path
                self.client.fput_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    file_path=data,
                    content_type=content_type
                )
            else:
                # It's a stream
                data.seek(0, os.SEEK_END)
                length = data.tell()
                data.seek(0)
                self.client.put_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    data=data,
                    length=length,
                    content_type=content_type
                )
        except S3Error as e:
            raise ObjectOperationError(f"Failed to upload object '{object_name}': {e}")

    def download_object(self, bucket_name: str, object_name: str, destination_path: str) -> None:
        self._ensure_client()
        try:
            self.client.fget_object(bucket_name, object_name, destination_path)
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(f"Object '{object_name}' not found in bucket '{bucket_name}'.")
            raise ObjectOperationError(f"Failed to download object '{object_name}': {e}")

    def delete_object(self, bucket_name: str, object_name: str) -> None:
        self._ensure_client()
        try:
            self.client.remove_object(bucket_name, object_name)
        except S3Error as e:
            raise ObjectOperationError(f"Failed to delete object '{object_name}': {e}")

    def list_objects(self, bucket_name: str, prefix: Optional[str] = None) -> List[str]:
        self._ensure_client()
        try:
            objects = self.client.list_objects(bucket_name, prefix=prefix, recursive=True)
            return [obj.object_name for obj in objects]
        except S3Error as e:
            raise ObjectOperationError(f"Failed to list objects in bucket '{bucket_name}': {e}")

    def get_object_url(self, bucket_name: str, object_name: str, expires_in_seconds: int = 3600) -> str:
        self._ensure_client()
        try:
            import datetime
            return self.client.presigned_get_object(
                bucket_name=bucket_name,
                object_name=object_name,
                expires=datetime.timedelta(seconds=expires_in_seconds)
            )
        except S3Error as e:
            raise ObjectOperationError(f"Failed to generate URL for object '{object_name}': {e}")

    def object_exists(self, bucket_name: str, object_name: str) -> bool:
        self._ensure_client()
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            raise ObjectOperationError(f"Failed to check existence of object '{object_name}': {e}")

    def read_object(self, bucket_name: str, object_name: str) -> bytes:
        self._ensure_client()
        response = None
        try:
            response = self.client.get_object(bucket_name, object_name)
            return response.read()
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(f"Object '{object_name}' not found in bucket '{bucket_name}'.")
            raise ObjectOperationError(f"Failed to read object '{object_name}': {e}")
        finally:
            if response:
                response.close()
                response.release_conn()

    def stat_object(self, bucket_name: str, object_name: str) -> dict:
        self._ensure_client()
        try:
            stat = self.client.stat_object(bucket_name, object_name)
            return {
                "size": stat.size,
                "mtime": stat.last_modified.timestamp() if stat.last_modified else 0.0
            }
        except S3Error as e:
            if e.code == "NoSuchKey":
                raise ObjectNotFoundError(f"Object '{object_name}' not found in bucket '{bucket_name}'.")
            raise ObjectOperationError(f"Failed to stat object '{object_name}': {e}")
