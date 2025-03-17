"""Integration tests with Redis."""

import os
import time
import pytest
import redis

from ranch.utils.persistence import RedisStorage


@pytest.fixture
def redis_client():
    """Create a Redis client for testing."""
    # Skip test if SKIP_REDIS_TESTS is set
    if os.environ.get("SKIP_REDIS_TESTS"):
        pytest.skip("Skipping Redis tests")

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis.from_url(redis_url)
        # Test connection by pinging
        client.ping()
        # Clear the test database
        client.flushdb()
        yield client
        # Clean up after tests
        client.flushdb()
    except redis.exceptions.ConnectionError:
        pytest.skip("Redis server not available")


def test_redis_storage(redis_client):
    """Test that RedisStorage can store and retrieve values using Redis."""
    # Setup
    storage = RedisStorage(redis_client, prefix="ranch_test:")
    test_key = "test_key"
    test_value = {"name": "test", "value": 42}

    # Store value
    storage.set(test_key, test_value)

    # Retrieve value
    retrieved = storage.get(test_key)

    # Verify
    assert retrieved == test_value

    # Delete value
    storage.delete(test_key)

    # Verify deletion
    assert storage.get(test_key) is None


def test_redis_storage_keys(redis_client):
    """Test that RedisStorage can list keys with prefixes."""
    # Setup
    storage = RedisStorage(redis_client, prefix="ranch_test:")

    # Add multiple keys
    storage.set("key1", "value1")
    storage.set("key2", "value2")
    storage.set("prefix_key3", "value3")

    # Get all keys
    all_keys = storage.get_all_keys()
    assert len(all_keys) == 3
    assert "key1" in all_keys
    assert "key2" in all_keys
    assert "prefix_key3" in all_keys

    # Get keys by prefix
    prefix_keys = storage.get_keys_by_prefix("prefix_")
    assert len(prefix_keys) == 1
    assert "prefix_key3" in prefix_keys
