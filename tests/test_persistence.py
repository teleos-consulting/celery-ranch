"""Tests for the persistence module"""

import json
import pickle
import time
from unittest.mock import MagicMock, patch

import pytest

from ranch.utils.persistence import (InMemoryStorage, StorageBackend, 
                                    RedisStorage, SerializerType, retry_on_error)


def test_retry_decorator_success():
    """Test retry decorator with successful execution."""
    mock_func = MagicMock()
    mock_func.return_value = "success"
    
    # Apply decorator
    decorated = retry_on_error()(mock_func)
    
    # Call the decorated function
    result = decorated("arg1", kwarg1="value1")
    
    # Should succeed on first attempt
    assert result == "success"
    assert mock_func.call_count == 1
    mock_func.assert_called_once_with("arg1", kwarg1="value1")


def test_retry_decorator_with_retries():
    """Test retry decorator with failed attempts and eventual success."""
    mock_func = MagicMock()
    mock_func.side_effect = [ValueError("First error"), 
                             ValueError("Second error"), 
                             "success"]
    
    # Apply decorator with retries
    decorated = retry_on_error(max_attempts=5, 
                               exceptions=(ValueError,),
                               backoff_factor=0.01)(mock_func)
    
    # Call the decorated function
    result = decorated("arg1", kwarg1="value1")
    
    # Should succeed on third attempt
    assert result == "success"
    assert mock_func.call_count == 3


def test_retry_decorator_exhausted():
    """Test retry decorator with all attempts exhausted."""
    mock_func = MagicMock()
    mock_func.side_effect = ValueError("Error")
    
    # Apply decorator with limited retries
    decorated = retry_on_error(max_attempts=3, exceptions=(ValueError,))(mock_func)
    
    # Call the decorated function
    with pytest.raises(ValueError, match="Error"):
        decorated("arg1", kwarg1="value1")
    
    # Should have attempted the specified number of times
    assert mock_func.call_count == 3


def test_in_memory_storage_methods():
    """Test all methods of InMemoryStorage class."""
    storage = InMemoryStorage()
    
    # Test set/get
    storage.set("key1", "value1")
    assert storage.get("key1") == "value1"
    
    # Test set with expiry (not implemented for InMemoryStorage)
    storage.set("key2", "value2", expiry=10)
    assert storage.get("key2") == "value2"
    
    # Test delete
    storage.delete("key1")
    assert storage.get("key1") is None
    
    # Test get_all_keys
    storage.set("key3", "value3")
    storage.set("key4", "value4")
    all_keys = storage.get_all_keys()
    assert sorted(all_keys) == sorted(["key2", "key3", "key4"])
    
    # Test get_keys_by_prefix
    storage.set("prefix_key1", "value5")
    storage.set("prefix_key2", "value6")
    prefix_keys = storage.get_keys_by_prefix("prefix_")
    assert sorted(prefix_keys) == sorted(["prefix_key1", "prefix_key2"])


@patch("redis.Redis")
def test_redis_storage_init(mock_redis):
    """Test initialization of RedisStorage."""
    # Setup mock
    redis_client = MagicMock()
    
    # Create RedisStorage with different parameters
    storage = RedisStorage(
        redis_client=redis_client,
        prefix="test_prefix:",
        serializer=SerializerType.JSON,
        max_retries=5,
        key_ttl=3600
    )
    
    # Verify the attributes were set correctly
    assert storage._redis == redis_client
    assert storage._prefix == "test_prefix:"
    assert storage._serializer == SerializerType.JSON
    assert storage._default_ttl == 3600


@patch("redis.Redis")
def test_redis_storage_json_serializer(mock_redis):
    """Test RedisStorage with JSON serializer."""
    # Setup mock
    redis_client = MagicMock()
    mock_set = MagicMock()
    mock_get = MagicMock()
    
    redis_client.setex = mock_set
    redis_client.get = mock_get
    
    # Mock successful get
    test_value = {"name": "test", "value": 42}
    mock_get.return_value = json.dumps(test_value).encode('utf-8')
    
    # Create storage with JSON serializer
    storage = RedisStorage(
        redis_client=redis_client,
        serializer=SerializerType.JSON
    )
    
    # Test set
    storage.set("test_key", test_value, expiry=100)
    mock_set.assert_called_once()
    
    # Test get
    result = storage.get("test_key")
    assert result == test_value
    mock_get.assert_called_once()


@patch("redis.Redis")
def test_redis_storage_pickle_serializer(mock_redis):
    """Test RedisStorage with Pickle serializer."""
    # Setup mock
    redis_client = MagicMock()
    mock_set = MagicMock()
    mock_get = MagicMock()
    
    redis_client.setex = mock_set
    redis_client.get = mock_get
    
    # Mock successful get
    test_value = {"name": "test", "value": 42}
    mock_get.return_value = pickle.dumps(test_value)
    
    # Create storage with Pickle serializer
    storage = RedisStorage(
        redis_client=redis_client,
        serializer=SerializerType.PICKLE
    )
    
    # Test set
    storage.set("test_key", test_value, expiry=100)
    mock_set.assert_called_once()
    
    # Test get
    result = storage.get("test_key")
    assert result == test_value
    mock_get.assert_called_once()


@patch("redis.Redis")
def test_redis_storage_error_handling(mock_redis):
    """Test error handling in RedisStorage."""
    # Setup mock
    redis_client = MagicMock()
    mock_get = MagicMock()
    
    redis_client.get = mock_get
    
    # Mock Redis error
    mock_get.side_effect = Exception("Redis connection error")
    
    # Create storage
    storage = RedisStorage(
        redis_client=redis_client,
        max_retries=2
    )
    
    # Test get with error
    with pytest.raises(Exception):
        storage.get("test_key")
    
    # There should be retries
    assert mock_get.call_count > 1


@patch("redis.Redis")
def test_redis_storage_key_not_found(mock_redis):
    """Test behavior when key is not found in Redis."""
    # Setup mock
    redis_client = MagicMock()
    mock_get = MagicMock()
    
    redis_client.get = mock_get
    
    # Mock key not found
    mock_get.return_value = None
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test get with non-existent key
    result = storage.get("nonexistent_key")
    
    # Should return None
    assert result is None
    mock_get.assert_called_once()


@patch("redis.Redis")
def test_redis_storage_delete(mock_redis):
    """Test delete method in RedisStorage."""
    # Setup mock
    redis_client = MagicMock()
    mock_delete = MagicMock()
    
    redis_client.delete = mock_delete
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test delete
    storage.delete("test_key")
    
    # Verify delete was called with the correct key
    mock_delete.assert_called_once_with("ranch:test_key")


@patch("redis.Redis")
def test_redis_storage_get_keys(mock_redis):
    """Test get_all_keys method."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    
    redis_client.keys = mock_keys
    
    # Mock keys response
    mock_keys.return_value = [
        b"ranch:key1",
        b"ranch:key2",
        b"ranch:prefix_key1",
        b"ranch:prefix_key2"
    ]
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test get_all_keys
    all_keys = storage.get_all_keys()
    assert sorted(all_keys) == sorted(["key1", "key2", "prefix_key1", "prefix_key2"])


@patch("redis.Redis")
def test_redis_storage_get_keys_by_prefix(mock_redis):
    """Test get_keys_by_prefix method with corrected implementation."""
    # Setup mock
    redis_client = MagicMock()
    
    # Define a custom implementation for keys method
    def mock_keys_impl(pattern):
        prefix = "ranch:prefix_"
        if pattern == f"{prefix}*":
            return [b"ranch:prefix_key1", b"ranch:prefix_key2"]
        return []
    
    # Set the mock implementation
    redis_client.keys = mock_keys_impl
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client, prefix="ranch:")
    
    # Test get_keys_by_prefix
    prefix_keys = storage.get_keys_by_prefix("prefix_")
    assert sorted(prefix_keys) == sorted(["prefix_key1", "prefix_key2"])


@patch("redis.Redis")
def test_redis_storage_health_check(mock_redis):
    """Test health_check method."""
    # Setup mock
    redis_client = MagicMock()
    mock_ping = MagicMock()
    
    redis_client.ping = mock_ping
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test successful health check
    mock_ping.return_value = True
    assert storage.health_check() is True
    
    # Test failed health check
    mock_ping.side_effect = Exception("Connection error")
    assert storage.health_check() is False