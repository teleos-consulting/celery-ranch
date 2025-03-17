"""
Persistent storage implementations for task backlog and LRU tracking.
"""

import json
import logging
import pickle
import time
from abc import ABC, abstractmethod
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


def retry_on_error(
    max_attempts: int = 3, backoff_factor: float = 0.5, exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for retrying operations with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Factor to determine delay between retries
        (seconds = backoff_factor * 2 ^ (attempt))
        exceptions: Tuple of exceptions to catch and retry on
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 0
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error(
                            f"Operation failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise

                    # Calculate backoff time
                    backoff_time = backoff_factor * (2**attempt)
                    logger.warning(
                        f"Operation failed, retrying in {backoff_time:.2f}s: {str(e)}"
                    )
                    time.sleep(backoff_time)

            # This should never happen, but keeps mypy happy
            raise RuntimeError("Unexpected end of retry loop")

        return wrapper

    return decorator


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        pass

    @abstractmethod
    def set(self, key: str, value: Any, expiry: Optional[int] = None) -> None:
        """Set a value for a key."""
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key."""
        pass

    @abstractmethod
    def get_all_keys(self) -> List[str]:
        """Get all keys in the storage."""
        pass

    @abstractmethod
    def get_keys_by_prefix(self, prefix: str) -> List[str]:
        """Get all keys starting with the given prefix."""
        pass


class InMemoryStorage(StorageBackend):
    """Simple in-memory storage implementation for development and testing."""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get a value by key."""
        return self._data.get(key)

    def set(self, key: str, value: Any, expiry: Optional[int] = None) -> None:
        """Set a value for a key.

        Args:
            key: The key
            value: The value to store
            expiry: Optional expiry time in seconds (ignored in memory storage)
        """
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


class SerializerType:
    """Enumeration of supported serializers."""

    PICKLE = "pickle"
    JSON = "json"


class RedisStorage(StorageBackend):
    """Redis-based storage implementation for production use.

    Supports connection retry with exponential backoff, health checking,
    and optional serializer choice.
    """

    def __init__(
        self,
        redis_client,
        prefix: str = "ranch:",
        serializer: str = SerializerType.PICKLE,
        max_retries: int = 3,
        key_ttl: Optional[int] = None,
    ) -> None:
        """Initialize with a Redis client.

        Args:
            redis_client: A Redis client instance
            prefix: Key prefix to use in Redis
            serializer: Serialization format to use ('pickle' or 'json')
            max_retries: Maximum number of retries for Redis operations
            key_ttl: Default TTL for keys in seconds (None = no expiry)
        """
        self._redis = redis_client
        self._prefix = prefix
        self._serializer = serializer
        self._max_retries = max_retries
        self._default_ttl = key_ttl
        self._validate_connection()

    def _validate_connection(self) -> None:
        """Validate that Redis connection is working."""
        try:
            self._redis.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    def _make_key(self, key: str) -> str:
        """Create a Redis key with prefix."""
        return f"{self._prefix}{key}"

    def _serialize(self, value: Any) -> bytes:
        """Serialize a value based on the configured serializer."""
        if self._serializer == SerializerType.JSON:
            return json.dumps(value).encode("utf-8")
        return pickle.dumps(value)

    def _deserialize(self, data: bytes) -> Any:
        """Deserialize a value based on the configured serializer."""
        if self._serializer == SerializerType.JSON:
            return json.loads(data.decode("utf-8"))
        return pickle.loads(data)

    @retry_on_error(exceptions=(Exception,))
    def get(self, key: str) -> Optional[Any]:
        """Get a value by key.

        Automatically retries on connection errors.
        """
        try:
            data = self._redis.get(self._make_key(key))
            if data is None:
                return None
            return self._deserialize(data)
        except Exception as e:
            logger.error(f"Error retrieving key {key}: {e}")
            raise

    @retry_on_error(exceptions=(Exception,))
    def set(self, key: str, value: Any, expiry: Optional[int] = None) -> None:
        """Set a value for a key.

        Args:
            key: The key
            value: The value to store
            expiry: Optional expiry time in seconds (overrides default TTL)
        """
        try:
            serialized = self._serialize(value)
            redis_key = self._make_key(key)
            ttl = expiry if expiry is not None else self._default_ttl

            if ttl:
                self._redis.setex(name=redis_key, time=ttl, value=serialized)
            else:
                self._redis.set(name=redis_key, value=serialized)
        except Exception as e:
            logger.error(f"Error setting key {key}: {e}")
            raise

    @retry_on_error(exceptions=(Exception,))
    def delete(self, key: str) -> None:
        """Delete a key."""
        try:
            self._redis.delete(self._make_key(key))
        except Exception as e:
            logger.error(f"Error deleting key {key}: {e}")
            raise

    @retry_on_error(exceptions=(Exception,))
    def get_all_keys(self) -> List[str]:
        """Get all keys in the storage."""
        try:
            pattern = self._make_key("*")
            keys = self._redis.keys(pattern)
            prefix_len = len(self._prefix)
            return [k.decode("utf-8")[prefix_len:] for k in keys]
        except Exception as e:
            logger.error(f"Error getting all keys: {e}")
            raise

    @retry_on_error(exceptions=(Exception,))
    def get_keys_by_prefix(self, prefix: str) -> List[str]:
        """Get all keys starting with the given prefix."""
        try:
            pattern = self._make_key(f"{prefix}*")
            keys = self._redis.keys(pattern)
            prefix_len = len(self._prefix)
            return [k.decode("utf-8")[prefix_len:] for k in keys]
        except Exception as e:
            logger.error(f"Error getting keys by prefix {prefix}: {e}")
            raise

    def health_check(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            return bool(self._redis.ping())
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    def clear_all_ranch_keys(self) -> int:
        """Clear all Ranch keys from Redis.

        Returns:
            Number of keys deleted
        """
        try:
            pattern = self._make_key("*")
            keys = self._redis.keys(pattern)
            if keys:
                return self._redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Error clearing all keys: {e}")
            raise
