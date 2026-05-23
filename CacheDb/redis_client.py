import os
import json
import logging
from typing import Any, Optional
from dotenv import load_dotenv

from CacheDb.base import BaseCacheClient

logger = logging.getLogger("CacheDb.redis")

class RedisCacheClient(BaseCacheClient):
    """Concrete implementation of BaseCacheClient using Redis."""
    
    def __init__(self):
        try:
            import redis
        except ImportError:
            raise ImportError("redis-py is not installed. Please install it using 'pip install redis'.")
            
    
        load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
        
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        password = os.getenv("REDIS_PASSWORD", None)
        
        try:
            self.client = redis.Redis(
                host=host, 
                port=port, 
                db=db, 
                password=password,
                decode_responses=True # Automatically decode string values
            )
            # Ping to verify connection
            self.client.ping()
            logger.info(f"Connected to Redis at {host}:{port}/{db}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.client = None

    def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        try:
            val = self.client.get(key)
            if val is not None:
                try:
                    return json.loads(val)
                except json.JSONDecodeError:
                    return val
            return None
        except Exception as e:
            logger.error(f"Redis get error for {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        if not self.client:
            return False
        try:
            # Serialize dicts/lists to JSON strings
            if isinstance(value, (dict, list)):
                value_str = json.dumps(value)
            else:
                value_str = str(value)
                
            self.client.set(key, value_str, ex=ttl)
            return True
        except Exception as e:
            logger.error(f"Redis set error for {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Redis delete error for {key}: {e}")
            return False
