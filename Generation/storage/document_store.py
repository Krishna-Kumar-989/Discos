from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import time
import threading

class BaseDocumentStore(ABC):
    @abstractmethod
    def store_documents(self, run_id: str, documents: List[Dict[str, Any]]):
        pass

    @abstractmethod
    def get_documents(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        pass

    @abstractmethod
    def clear_expired(self):
        pass


class InMemoryDocumentStore(BaseDocumentStore):
    """
    A simple thread-safe in-memory cache for retrieved documents.
    Supports TTL expiration based on configuration.
    """
    def __init__(self, ttl_seconds: int = 3600):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()

    def store_documents(self, run_id: str, documents: List[Dict[str, Any]]):
        with self._lock:
            self._store[run_id] = {
                "timestamp": time.time(),
                "documents": documents
            }

    def get_documents(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        with self._lock:
            record = self._store.get(run_id)
            if not record:
                return None
                
            # Check expiration
            if time.time() - record["timestamp"] > self.ttl_seconds:
                del self._store[run_id]
                return None
                
            return record["documents"]

    def clear_expired(self):
        with self._lock:
            now = time.time()
            expired_keys = [
                k for k, v in self._store.items() 
                if now - v["timestamp"] > self.ttl_seconds
            ]
            for k in expired_keys:
                del self._store[k]

class KeyValueDocumentStore(BaseDocumentStore):
    """
    A distributed cache for retrieved documents using the abstract CacheDb.
    """
    def __init__(self, cache_client, ttl_seconds: int = 3600):
        self.cache = cache_client
        self.ttl_seconds = ttl_seconds
        
    def _key(self, run_id: str) -> str:
        return f"doc_store:{run_id}"

    def store_documents(self, run_id: str, documents: List[Dict[str, Any]]):
        self.cache.set(self._key(run_id), documents, ttl=self.ttl_seconds)

    def get_documents(self, run_id: str) -> Optional[List[Dict[str, Any]]]:
        return self.cache.get(self._key(run_id))

    def clear_expired(self):
        
        pass
