import os
from CacheDb.base import BaseCacheClient

# Singleton cache instance
_cache_client = None

def get_cache_client() -> BaseCacheClient:
    """
    Factory function to get the configured cache client.
    Defaults to RedisCacheClient.
    """
    global _cache_client
    if _cache_client is None:
        provider = os.getenv("CACHE_PROVIDER", "redis").lower()
        if provider == "redis":
            from CacheDb.redis_client import RedisCacheClient
            _cache_client = RedisCacheClient()
        else:
            raise ValueError(f"Unknown cache provider: {provider}")
            
    return _cache_client
