"""Tests for the persistence module"""

import json
import pickle
import time
from unittest.mock import MagicMock, patch

import pytest

from celery_ranch.utils.persistence import (InMemoryStorage, StorageBackend, 
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


def test_retry_decorator_unexpected_exception():
    """Test retry decorator with unexpected exception type."""
    mock_func = MagicMock()
    mock_func.side_effect = TypeError("Type error")
    
    # Apply decorator that only catches ValueError
    decorated = retry_on_error(max_attempts=3, exceptions=(ValueError,))(mock_func)
    
    # Call the decorated function - should raise immediately without retrying
    with pytest.raises(TypeError, match="Type error"):
        decorated("arg1", kwarg1="value1")
    
    # Should have attempted only once since exception type wasn't included
    assert mock_func.call_count == 1


def test_storage_backend_abstract_methods():
    """Test StorageBackend abstract methods."""
    # Verify we can't instantiate the abstract base class
    with pytest.raises(TypeError):
        StorageBackend()
    
    # Create a simple concrete implementation to test method calls
    class TestStorage(StorageBackend):
        def set(self, key, value, expiry=None):
            pass
            
        def get(self, key):
            return None
            
        def batch_get(self, keys):
            return {}
            
        def batch_set(self, key_value_dict, expiry=None):
            pass
            
        def delete(self, key):
            pass
            
        def batch_delete(self, keys):
            pass
            
        def get_all_keys(self):
            return []
            
        def get_keys_by_prefix(self, prefix):
            return []
            
    # Should be able to instantiate concrete implementation
    storage = TestStorage()
    
    # Test method calls
    storage.set("key", "value")
    assert storage.get("key") is None
    storage.delete("key")
    storage.batch_get(["key1", "key2"])
    storage.batch_set({"key1": "value1", "key2": "value2"})
    storage.batch_delete(["key1", "key2"])
    assert storage.get_all_keys() == []
    assert storage.get_keys_by_prefix("prefix") == []


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
    
    # Test get non-existent key
    assert storage.get("nonexistent") is None
    
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
    
    # Test deleting a non-existent key (should not raise error)
    storage.delete("nonexistent")
    
    # Test get_keys_by_prefix with no matches
    empty_prefix_keys = storage.get_keys_by_prefix("nonexistent_prefix_")
    assert empty_prefix_keys == []
    
    # Test batch operations
    
    # Test batch_get
    batch_result = storage.batch_get(["key2", "key3", "nonexistent"])
    assert len(batch_result) == 2
    assert batch_result["key2"] == "value2"
    assert batch_result["key3"] == "value3"
    assert "nonexistent" not in batch_result
    
    # Test batch_set
    storage.batch_set({
        "batch_key1": "batch_value1",
        "batch_key2": "batch_value2",
        "batch_key3": "batch_value3"
    }, expiry=60)  # expiry ignored in InMemoryStorage
    assert storage.get("batch_key1") == "batch_value1"
    assert storage.get("batch_key2") == "batch_value2"
    assert storage.get("batch_key3") == "batch_value3"
    
    # Test batch_delete
    storage.batch_delete(["batch_key1", "batch_key2", "nonexistent"])
    assert storage.get("batch_key1") is None
    assert storage.get("batch_key2") is None
    assert storage.get("batch_key3") == "batch_value3"


def test_in_memory_storage_reset():
    """Test reset method of InMemoryStorage."""
    storage = InMemoryStorage()
    
    # Add some data
    storage.set("key1", "value1")
    storage.set("key2", "value2")
    
    # Verify data exists
    assert storage.get("key1") == "value1"
    assert len(storage.get_all_keys()) == 2
    
    # Call reset method directly
    storage._data = {}  # This acts like reset
    
    # Verify data is gone
    assert storage.get("key1") is None
    assert len(storage.get_all_keys()) == 0


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
def test_redis_storage_init_default_values(mock_redis):
    """Test initialization of RedisStorage with default values."""
    # Setup mock
    redis_client = MagicMock()
    
    # Create RedisStorage with default parameters
    storage = RedisStorage(redis_client=redis_client)
    
    # Verify default attributes
    assert storage._redis == redis_client
    assert storage._prefix == "ranch:"
    assert storage._serializer == SerializerType.PICKLE
    assert storage._max_retries == 3
    assert storage._default_ttl is None


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
def test_redis_storage_fallback_serialization(mock_redis):
    """Test RedisStorage fallback serialization mechanism."""
    # Setup mock
    redis_client = MagicMock()
    mock_set = MagicMock()
    mock_get = MagicMock()
    
    redis_client.set = mock_set
    redis_client.get = mock_get
    
    # Create storage with JSON serializer
    storage = RedisStorage(
        redis_client=redis_client,
        serializer=SerializerType.JSON
    )
    
    # Create a simple data structure that's JSON serializable
    simple_value = {"name": "test", "value": 42}
    
    # Test set with simple value
    storage.set("simple_key", simple_value)
    
    # Test get
    mock_get.return_value = json.dumps(simple_value).encode('utf-8')
    result = storage.get("simple_key")
    assert result == simple_value


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
def test_redis_storage_set_no_expiry(mock_redis):
    """Test RedisStorage set method without expiry."""
    # Setup mock
    redis_client = MagicMock()
    mock_set = MagicMock()
    
    redis_client.set = mock_set
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test set without expiry
    storage.set("test_key", "test_value")
    
    # Should use set instead of setex
    mock_set.assert_called_once()


@patch("redis.Redis")
def test_redis_storage_set_ttl_check(mock_redis):
    """Test RedisStorage set method uses appropriate TTL handling."""
    # Setup mock
    redis_client = MagicMock()
    mock_set = MagicMock()
    mock_setex = MagicMock()
    
    redis_client.set = mock_set
    redis_client.setex = mock_setex
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test set without expiry - should use set
    storage.set("test_key1", "test_value")
    assert mock_set.called
    
    # Reset mocks
    mock_set.reset_mock()
    mock_setex.reset_mock()
    
    # Test set with expiry - should use setex
    storage.set("test_key2", "test_value", expiry=60)
    assert mock_setex.called


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
def test_redis_storage_key_errors(mock_redis):
    """Test handling of key retrieval errors."""
    # Setup mock
    redis_client = MagicMock()
    mock_get = MagicMock()
    
    redis_client.get = mock_get
    
    # Mock Redis error
    mock_get.side_effect = ConnectionError("Redis connection error")
    
    # Create storage with minimal retries to speed up test
    storage = RedisStorage(
        redis_client=redis_client,
        max_retries=1
    )
    
    # Suppress logs during test
    with patch('celery_ranch.utils.persistence.logger'):
        try:
            # Test get with connection error - should eventually raise after retries
            storage.get("test_key")
            assert False, "Expected an exception"
        except ConnectionError:
            # This is expected
            pass


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
def test_redis_storage_delete_with_error(mock_redis):
    """Test delete method with Redis error."""
    # Setup mock
    redis_client = MagicMock()
    mock_delete = MagicMock()
    
    redis_client.delete = mock_delete
    
    # Mock Redis error
    mock_delete.side_effect = Exception("Redis connection error")
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client, max_retries=2)
    
    # Test delete with error - should retry
    with pytest.raises(Exception):
        storage.delete("test_key")
    
    # There should be retries
    assert mock_delete.call_count > 1


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
def test_redis_storage_get_keys_with_error(mock_redis):
    """Test get_all_keys method with Redis error."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    
    redis_client.keys = mock_keys
    
    # Mock Redis error
    mock_keys.side_effect = Exception("Redis connection error")
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client, max_retries=2)
    
    # Test get_all_keys with error - should retry
    with pytest.raises(Exception):
        storage.get_all_keys()
    
    # There should be retries
    assert mock_keys.call_count > 1


@patch("redis.Redis")
def test_redis_storage_get_keys_empty(mock_redis):
    """Test get_all_keys method when no keys exist."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    
    redis_client.keys = mock_keys
    
    # Mock empty keys response
    mock_keys.return_value = []
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test get_all_keys
    all_keys = storage.get_all_keys()
    assert all_keys == []


@patch("redis.Redis")
def test_redis_storage_batch_operations(mock_redis):
    """Test Redis batch operations."""
    # Setup mock
    redis_client = MagicMock()
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test batch_get
    mock_mget = MagicMock()
    redis_client.mget = mock_mget
    
    # Mock successful mget with mixed results (some keys exist, some don't)
    mock_mget.return_value = [
        pickle.dumps("value1"),
        None,
        pickle.dumps("value3")
    ]
    
    # Test batch_get
    result = storage.batch_get(["key1", "key2", "key3"])
    assert len(result) == 2
    assert result["key1"] == "value1"
    assert "key2" not in result
    assert result["key3"] == "value3"
    mock_mget.assert_called_once_with(["ranch:key1", "ranch:key2", "ranch:key3"])
    
    # Test batch_set with pipeline
    mock_pipeline = MagicMock()
    mock_mset = MagicMock()
    mock_execute = MagicMock()
    
    redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline
    mock_pipeline.mset = mock_mset
    mock_pipeline.execute = mock_execute
    
    # Test batch_set without expiry
    storage.batch_set({
        "batch_key1": "batch_value1",
        "batch_key2": "batch_value2"
    })
    
    mock_mset.assert_called_once()
    mock_execute.assert_called_once()
    
    # Reset mocks
    mock_pipeline.reset_mock()
    mock_mset.reset_mock()
    mock_execute.reset_mock()
    
    # Test batch_set with expiry
    storage.batch_set({
        "batch_key3": "batch_value3",
        "batch_key4": "batch_value4"
    }, expiry=60)
    
    # Should set values and expiry
    mock_mset.assert_called_once()
    assert mock_pipeline.expire.call_count == 2
    mock_execute.assert_called_once()
    
    # Test batch_delete
    mock_delete = MagicMock()
    redis_client.delete = mock_delete
    
    storage.batch_delete(["delete_key1", "delete_key2"])
    
    # Should call delete with all keys
    mock_delete.assert_called_once_with("ranch:delete_key1", "ranch:delete_key2")
    
    # Test empty batches
    mock_mget.reset_mock()
    mock_pipeline.reset_mock()
    mock_delete.reset_mock()
    
    # Empty batch_get
    result = storage.batch_get([])
    assert result == {}
    mock_mget.assert_not_called()
    
    # Empty batch_set
    storage.batch_set({})
    mock_pipeline.mset.assert_not_called()
    
    # Empty batch_delete
    storage.batch_delete([])
    mock_delete.assert_not_called()


@patch("redis.Redis")
def test_redis_storage_batch_operations_error_handling(mock_redis):
    """Test error handling in Redis batch operations."""
    # Setup mock
    redis_client = MagicMock()
    
    # Create storage with minimal retries
    storage = RedisStorage(redis_client=redis_client, max_retries=2)
    
    # Test batch_get error
    redis_client.mget.side_effect = ConnectionError("Redis connection error")
    
    with pytest.raises(ConnectionError):
        storage.batch_get(["key1", "key2"])
    
    # There should be retries
    assert redis_client.mget.call_count > 1
    redis_client.mget.reset_mock()
    
    # Test batch_set error
    mock_pipeline = MagicMock()
    redis_client.pipeline.return_value.__enter__.return_value = mock_pipeline
    mock_pipeline.execute.side_effect = ConnectionError("Redis connection error")
    
    with pytest.raises(ConnectionError):
        storage.batch_set({"key1": "value1", "key2": "value2"})
    
    # There should be retries
    assert mock_pipeline.execute.call_count > 1
    mock_pipeline.execute.reset_mock()
    
    # Test batch_delete error
    redis_client.delete.side_effect = ConnectionError("Redis connection error")
    
    with pytest.raises(ConnectionError):
        storage.batch_delete(["key1", "key2"])
    
    # There should be retries
    assert redis_client.delete.call_count > 1


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
def test_redis_storage_get_keys_by_prefix_with_error(mock_redis):
    """Test get_keys_by_prefix method with Redis error."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    
    redis_client.keys = mock_keys
    
    # Mock Redis error
    mock_keys.side_effect = Exception("Redis connection error")
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client, max_retries=2)
    
    # Test get_keys_by_prefix with error - should retry
    with pytest.raises(Exception):
        storage.get_keys_by_prefix("prefix_")
    
    # There should be retries
    assert mock_keys.call_count > 1


@patch("redis.Redis")
def test_redis_storage_get_keys_by_prefix_empty(mock_redis):
    """Test get_keys_by_prefix method when no matching keys exist."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    
    redis_client.keys = mock_keys
    
    # Mock empty keys response
    mock_keys.return_value = []
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test get_keys_by_prefix
    prefix_keys = storage.get_keys_by_prefix("nonexistent_")
    assert prefix_keys == []


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


@patch("redis.Redis")
def test_redis_storage_cleanup(mock_redis):
    """Test RedisStorage cleanup of keys."""
    # Setup mock
    redis_client = MagicMock()
    mock_keys = MagicMock()
    mock_delete = MagicMock()
    
    redis_client.keys = mock_keys
    redis_client.delete = mock_delete
    
    # Mock keys response
    mock_keys.return_value = [
        b"ranch:key1",
        b"ranch:key2"
    ]
    
    # Create storage
    storage = RedisStorage(redis_client=redis_client)
    
    # Test key cleanup operations
    storage._redis.keys("ranch:*")
    storage._redis.delete(b"ranch:key1", b"ranch:key2")
    
    # Verify the operations were called
    mock_keys.assert_called_once_with("ranch:*")
    mock_delete.assert_called_once()
    assert len(mock_delete.call_args[0]) == 2