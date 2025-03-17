"""Tests for the prioritize module"""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from celery import Celery

from ranch.utils.prioritize import (
    _initialize_storage, create_redis_client, configure, 
    get_status, prioritize_task
)
from ranch.utils.persistence import InMemoryStorage, RedisStorage


@pytest.fixture
def celery_app():
    app = Celery("tests")
    app.conf.update(
        task_always_eager=True, 
        broker_url="redis://localhost:6379/0",
        result_backend="memory://"
    )
    return app


@patch("ranch.utils.prioritize.create_redis_client")
@patch("ranch.utils.prioritize._lru_tracker", None)
@patch("ranch.utils.prioritize._task_backlog", None)
@patch("ranch.utils.prioritize._storage", None)
def test_initialize_storage_with_redis(mock_create_redis):
    """Test storage initialization with Redis."""
    # Mock Redis client creation
    redis_client = MagicMock()
    mock_create_redis.return_value = redis_client
    
    # Call _initialize_storage
    _initialize_storage()
    
    # Verify that Redis storage was created
    from ranch.utils.prioritize import _storage
    assert isinstance(_storage, RedisStorage)


@patch("ranch.utils.prioritize.create_redis_client")
@patch("ranch.utils.prioritize._lru_tracker", None)
@patch("ranch.utils.prioritize._task_backlog", None)
@patch("ranch.utils.prioritize._storage", None)
def test_initialize_storage_fallback(mock_create_redis):
    """Test storage initialization with fallback to InMemoryStorage."""
    # Mock Redis client creation failure
    mock_create_redis.return_value = None
    
    # Call _initialize_storage
    _initialize_storage()
    
    # Verify that InMemoryStorage was used as fallback
    from ranch.utils.prioritize import _storage
    assert isinstance(_storage, InMemoryStorage)


@patch("redis.from_url")
def test_create_redis_client_success(mock_from_url, celery_app):
    """Test successful Redis client creation."""
    # Mock Redis client
    redis_client = MagicMock()
    mock_from_url.return_value = redis_client
    
    # Call create_redis_client
    result = create_redis_client(celery_app)
    
    # Verify result
    assert result == redis_client
    mock_from_url.assert_called_once()


@patch("redis.from_url")
def test_create_redis_client_connection_error(mock_from_url, celery_app):
    """Test Redis client creation with connection error."""
    # Mock connection error
    mock_from_url.side_effect = Exception("Connection error")
    
    # Call create_redis_client
    result = create_redis_client(celery_app)
    
    # Verify result
    assert result is None


@patch("ranch.utils.prioritize.create_redis_client")
def test_configure_with_custom_storage(mock_create_redis, celery_app):
    """Test configure with custom storage."""
    # Create custom storage
    custom_storage = InMemoryStorage()
    
    # Call configure with custom storage
    configure(app=celery_app, storage=custom_storage)
    
    # Verify storage was set
    from ranch.utils.prioritize import _storage
    assert _storage == custom_storage
    
    # Redis client should not be created
    mock_create_redis.assert_not_called()


@patch("ranch.utils.prioritize.create_redis_client")
def test_configure_with_redis(mock_create_redis, celery_app):
    """Test configure with Redis."""
    # Mock Redis client creation
    redis_client = MagicMock()
    mock_create_redis.return_value = redis_client
    
    # Call configure without custom storage
    configure(app=celery_app)
    
    # Verify Redis client was created
    mock_create_redis.assert_called_once_with(celery_app)
    
    # Verify storage type
    from ranch.utils.prioritize import _storage
    assert isinstance(_storage, RedisStorage)


@patch("ranch.utils.prioritize._task_backlog")
@patch("ranch.utils.prioritize._lru_tracker")
def test_prioritize_task_success(mock_lru_tracker, mock_task_backlog):
    """Test successful task prioritization."""
    # Setup mocks
    mock_task = MagicMock()
    mock_result = MagicMock()
    mock_task.apply_async.return_value = mock_result
    
    mock_task_backlog.get_all_lru_keys.return_value = ["client1", "client2"]
    mock_lru_tracker.get_oldest_key.return_value = "client1"
    
    mock_task_data = {
        "task_id1": (mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    }
    mock_task_backlog.get_tasks_by_lru_key.return_value = mock_task_data
    mock_task_backlog.get_task.return_value = (
        mock_task, "client1", ("arg1",), {"kwarg1": "value1"}
    )
    
    # Call prioritize_task
    result = prioritize_task("task_id1")
    
    # Verify result
    assert result == mock_result
    
    # Verify the task was removed from the backlog
    mock_task_backlog.remove_task.assert_called_once_with("task_id1")
    
    # Verify timestamp was updated
    mock_lru_tracker.update_timestamp.assert_called_once_with("client1")
    
    # Verify task was executed
    mock_task.apply_async.assert_called_once_with(
        args=("arg1",), kwargs={"kwarg1": "value1"}
    )


@patch("ranch.utils.prioritize._task_backlog")
def test_prioritize_task_no_keys(mock_task_backlog):
    """Test prioritize_task with no LRU keys."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = []
    
    # Call prioritize_task
    result = prioritize_task("task_id1")
    
    # Verify result
    assert result is None


@patch("ranch.utils.prioritize._storage")
@patch("ranch.utils.prioritize._task_backlog")
@patch("ranch.utils.prioritize._lru_tracker")
def test_get_status(mock_lru_tracker, mock_task_backlog, mock_storage):
    """Test get_status function."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = ["client1", "client2"]
    mock_task_backlog.get_tasks_by_lru_key.return_value = {"task1": {}, "task2": {}}
    mock_storage.__class__.__name__ = "MockStorage"
    
    # Test Redis storage
    mock_redis_storage = MagicMock(spec=RedisStorage)
    mock_redis_storage.health_check.return_value = True
    mock_redis_storage.__class__.__name__ = "RedisStorage"
    
    # Apply patch
    with patch("ranch.utils.prioritize._storage", mock_redis_storage):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["initialized"] is True
        assert result["storage_type"] == "RedisStorage"
        assert result["unique_lru_keys"] == 2
        assert result["backlog_size"] == 4  # 2 tasks for each client
        assert result["health"] is True
    
    # Test InMemoryStorage
    with patch("ranch.utils.prioritize._storage", MagicMock(spec=InMemoryStorage)):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["health"] is True  # InMemoryStorage is always healthy
    
    # Test not initialized
    with patch("ranch.utils.prioritize._storage", None):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["initialized"] is False
        assert result["storage_type"] == "none"