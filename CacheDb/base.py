from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseCacheClient(ABC):
    """Abstract base class for all Key-Value Cache databases."""
    
    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value by key. Returns None if not found."""
        pass
        
    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Store a value with an optional TTL in seconds."""
        pass
        
    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if deleted, False otherwise."""
        pass
