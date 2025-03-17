"""
Persistent storage implementations for task backlog and LRU tracking.
"""
import json
import pickle
from typing import Any, Dict, Optional, Tuple, List

from celery import Task


class InMemoryStorage:
    """Simple in-memory storage implementation for development and testing."""
    
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        return self._data.get(key)
    
    def set(self, key: str, value: Any) -> None:
        """Set a value for a key."""
        self._data[key] = value
    
    def delete(self, key: str) -> None:
        """Delete a key."""
        if key in self._data:
            del self._data[key]
    
    def get_all_keys(self) -> List[str]:
        """Get all keys in the storage."""
        return list(self._data.keys())
    
    def get_keys_by_prefix(self, prefix: str) -> List[str]:
        """Get all keys starting with the given prefix."""
        return [k for k in self._data.keys() if k.startswith(prefix)]


class RedisStorage:
    """Redis-based storage implementation for production use."""
    
    def __init__(self, redis_client, prefix: str = "ranch:") -> None:
        """Initialize with a Redis client.
        
        Args:
            redis_client: A Redis client instance
            prefix: Key prefix to use in Redis
        """
        self._redis = redis_client
        self._prefix = prefix
    
    def _make_key(self, key: str) -> str:
        """Create a Redis key with prefix."""
        return f"{self._prefix}{key}"
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        data = self._redis.get(self._make_key(key))
        if data is None:
            return None
        return pickle.loads(data)
    
    def set(self, key: str, value: Any, expiry: Optional[int] = None) -> None:
        """Set a value for a key.
        
        Args:
            key: The key
            value: The value to store
            expiry: Optional expiry time in seconds
        """
        serialized = pickle.dumps(value)
        if expiry:
            # Redis 5.x API requires the key, expiry, value order
            self._redis.setex(name=self._make_key(key), time=expiry, value=serialized)
        else:
            self._redis.set(name=self._make_key(key), value=serialized)
    
    def delete(self, key: str) -> None:
        """Delete a key."""
        self._redis.delete(self._make_key(key))
    
    def get_all_keys(self) -> List[str]:
        """Get all keys in the storage."""
        pattern = self._make_key("*")
        keys = self._redis.keys(pattern)
        prefix_len = len(self._prefix)
        return [k.decode('utf-8')[prefix_len:] for k in keys]
    
    def get_keys_by_prefix(self, prefix: str) -> List[str]:
        """Get all keys starting with the given prefix."""
        pattern = self._make_key(f"{prefix}*")
        keys = self._redis.keys(pattern)
        prefix_len = len(self._prefix)
        return [k.decode('utf-8')[prefix_len:] for k in keys]