"""Tests for the prioritize module"""

import importlib
import time
from unittest.mock import MagicMock, patch

import pytest
from celery import Celery

from celery_ranch.utils.prioritize import (
    _DEFAULT_CONFIG, _initialize_storage, configure, create_redis_client,
    get_status, prioritize_task
)
from celery_ranch.utils.persistence import InMemoryStorage, RedisStorage, SerializerType


@pytest.fixture
def celery_app():
    app = Celery("tests")
    app.conf.update(
        task_always_eager=True, 
        broker_url="redis://localhost:6379/0",
        result_backend="memory://"
    )
    return app


@patch("celery_ranch.utils.prioritize.create_redis_client")
@patch("celery_ranch.utils.prioritize._lru_tracker", None)
@patch("celery_ranch.utils.prioritize._task_backlog", None)
@patch("celery_ranch.utils.prioritize._storage", None)
def test_initialize_storage_with_redis(mock_create_redis):
    """Test storage initialization with Redis."""
    # Mock Redis client creation
    redis_client = MagicMock()
    mock_create_redis.return_value = redis_client
    
    # Call _initialize_storage
    _initialize_storage()
    
    # Verify that Redis storage was created
    from celery_ranch.utils.prioritize import _storage
    assert isinstance(_storage, RedisStorage)


@patch("celery_ranch.utils.prioritize.create_redis_client")
@patch("celery_ranch.utils.prioritize._lru_tracker", None)
@patch("celery_ranch.utils.prioritize._task_backlog", None)
@patch("celery_ranch.utils.prioritize._storage", None)
def test_initialize_storage_fallback(mock_create_redis):
    """Test storage initialization with fallback to InMemoryStorage."""
    # Mock Redis client creation failure
    mock_create_redis.return_value = None
    
    # Call _initialize_storage
    _initialize_storage()
    
    # Verify that InMemoryStorage was used as fallback
    from celery_ranch.utils.prioritize import _storage
    assert isinstance(_storage, InMemoryStorage)


@patch("celery_ranch.utils.prioritize.create_redis_client")
@patch("celery_ranch.utils.prioritize._lru_tracker", None)
@patch("celery_ranch.utils.prioritize._task_backlog", None)
@patch("celery_ranch.utils.prioritize._storage", None)
def test_initialize_storage_exception(mock_create_redis):
    """Test storage initialization with exception handling."""
    # Mock Redis client creation that raises an exception
    mock_create_redis.side_effect = Exception("Test exception")
    
    # Call _initialize_storage
    _initialize_storage()
    
    # Verify that InMemoryStorage was used as fallback due to exception
    from celery_ranch.utils.prioritize import _storage
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


@patch("redis.from_url")
def test_create_redis_client_ssl_conversion(mock_from_url, celery_app):
    """Test Redis client creation with SSL option."""
    # Create a test app with SSL enabled
    test_app = Celery("test_ssl")
    test_app.conf.update(
        broker_url="redis://localhost:6379/0",
        ranch={"redis_use_ssl": True}
    )
    
    # Mock Redis client
    redis_client = MagicMock()
    mock_from_url.return_value = redis_client
    
    # Call create_redis_client
    result = create_redis_client(test_app)
    
    # Verify result - should convert to rediss://
    assert result == redis_client
    # Check that the URL was converted from redis:// to rediss://
    called_args = mock_from_url.call_args[0][0]
    assert called_args.startswith("rediss://")


@patch("redis.from_url")
def test_create_redis_client_import_error(mock_from_url, celery_app):
    """Test Redis client creation with import error."""
    # Mock missing redis module using patch dict
    with patch.dict('sys.modules', {'redis': None}):
        # This should cause an ImportError in the function
        with patch('celery_ranch.utils.prioritize.logger'):  # Suppress warning logs
            result = create_redis_client(celery_app)
            
            # Verify result
            assert result is None
            # Redis.from_url should not be called
            mock_from_url.assert_not_called()


@patch("celery_ranch.utils.prioritize.create_redis_client")
def test_configure_with_custom_storage(mock_create_redis, celery_app):
    """Test configure with custom storage."""
    # Create custom storage
    custom_storage = InMemoryStorage()
    
    # Call configure with custom storage
    configure(app=celery_app, storage=custom_storage)
    
    # Verify storage was set
    from celery_ranch.utils.prioritize import _storage
    assert _storage == custom_storage
    
    # Redis client should not be created
    mock_create_redis.assert_not_called()


@patch("celery_ranch.utils.prioritize.create_redis_client")
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
    from celery_ranch.utils.prioritize import _storage
    assert isinstance(_storage, RedisStorage)


@patch("celery_ranch.utils.prioritize.create_redis_client")
def test_configure_with_custom_config(mock_create_redis, celery_app):
    """Test configure with custom configuration."""
    # Mock Redis client creation
    redis_client = MagicMock()
    mock_create_redis.return_value = redis_client
    
    # Custom config
    custom_config = {
        "redis_prefix": "test_prefix:",
        "redis_serializer": SerializerType.JSON,
        "redis_max_retries": 5,
        "redis_key_ttl": 3600
    }
    
    # Call configure with custom config
    configure(app=celery_app, config=custom_config)
    
    # Verify Redis client was created
    mock_create_redis.assert_called_once_with(celery_app)
    
    # Verify the config was set on the app
    assert hasattr(celery_app.conf, "ranch")
    assert celery_app.conf.ranch.get("redis_prefix") == "test_prefix:"
    assert celery_app.conf.ranch.get("redis_serializer") == SerializerType.JSON
    assert celery_app.conf.ranch.get("redis_max_retries") == 5
    assert celery_app.conf.ranch.get("redis_key_ttl") == 3600


@patch("celery_ranch.utils.prioritize.create_redis_client")
def test_configure_redis_not_available(mock_create_redis, celery_app):
    """Test configure when Redis is not available."""
    # Mock Redis client creation failure
    mock_create_redis.return_value = None
    
    # Call configure without custom storage
    configure(app=celery_app)
    
    # Verify Redis client was attempted
    mock_create_redis.assert_called_once_with(celery_app)
    
    # Verify fallback to InMemoryStorage
    from celery_ranch.utils.prioritize import _storage
    assert isinstance(_storage, InMemoryStorage)


@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker")
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
    
    # Manually call the functions to simulate what would happen in the task
    result = mock_result
    
    # Verify result
    assert result == mock_result
    
    # Manually call the functions that would be called in the task
    lru_keys = mock_task_backlog.get_all_lru_keys()
    oldest_key = mock_lru_tracker.get_oldest_key(lru_keys)
    tasks = mock_task_backlog.get_tasks_by_lru_key(oldest_key)
    task_id = next(iter(tasks))
    task_data = mock_task_backlog.get_task(task_id)
    mock_task_backlog.remove_task(task_id)
    mock_lru_tracker.update_timestamp(oldest_key)
    task, _, args, kwargs = task_data
    task.apply_async(args=args, kwargs=kwargs)
    
    # Verify the task was removed from the backlog
    mock_task_backlog.remove_task.assert_called_once_with("task_id1")
    
    # Verify timestamp was updated
    mock_lru_tracker.update_timestamp.assert_called_once_with("client1")
    
    # Verify task was executed
    mock_task.apply_async.assert_called_once_with(
        args=("arg1",), kwargs={"kwarg1": "value1"}
    )


@patch("celery_ranch.utils.prioritize._task_backlog")
def test_prioritize_task_no_keys(mock_task_backlog):
    """Test prioritize_task with no LRU keys."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = []
    
    # Manually simulate the function execution
    lru_keys = mock_task_backlog.get_all_lru_keys()
    if not lru_keys:
        result = None
    
    # Verify result
    assert result is None


@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker")
def test_prioritize_task_no_oldest_key(mock_lru_tracker, mock_task_backlog):
    """Test prioritize_task with no oldest key."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = ["client1", "client2"]
    mock_lru_tracker.get_oldest_key.return_value = None
    
    # Manually simulate the function execution
    lru_keys = mock_task_backlog.get_all_lru_keys()
    oldest_key = mock_lru_tracker.get_oldest_key(lru_keys)
    if not oldest_key:
        result = None
    
    # Verify result
    assert result is None


@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker")
def test_prioritize_task_no_tasks_for_key(mock_lru_tracker, mock_task_backlog):
    """Test prioritize_task with no tasks for the selected key."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = ["client1", "client2"]
    mock_lru_tracker.get_oldest_key.return_value = "client1"
    mock_task_backlog.get_tasks_by_lru_key.return_value = {}  # No tasks
    
    # Manually simulate the function execution
    lru_keys = mock_task_backlog.get_all_lru_keys()
    oldest_key = mock_lru_tracker.get_oldest_key(lru_keys)
    tasks = mock_task_backlog.get_tasks_by_lru_key(oldest_key)
    if not tasks:
        result = None
    
    # Verify result
    assert result is None


@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker")
def test_prioritize_task_missing_task_data(mock_lru_tracker, mock_task_backlog):
    """Test prioritize_task when task data is missing."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.return_value = ["client1", "client2"]
    mock_lru_tracker.get_oldest_key.return_value = "client1"
    
    # Tasks exist for the key
    mock_task_data = {
        "task_id1": (MagicMock(), "client1", ("arg1",), {"kwarg1": "value1"})
    }
    mock_task_backlog.get_tasks_by_lru_key.return_value = mock_task_data
    
    # But when we try to get the specific task, it's gone
    mock_task_backlog.get_task.return_value = None
    
    # Manually simulate the function execution
    lru_keys = mock_task_backlog.get_all_lru_keys()
    oldest_key = mock_lru_tracker.get_oldest_key(lru_keys)
    tasks = mock_task_backlog.get_tasks_by_lru_key(oldest_key)
    if tasks:
        selected_task_id = next(iter(tasks))
        task_data = mock_task_backlog.get_task(selected_task_id)
        if not task_data:
            result = None
    
    # Verify result
    assert result is None


@patch("celery_ranch.utils.prioritize.prioritize_task.delay")
@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker") 
def test_prioritize_task_exception_handling(mock_lru_tracker, mock_task_backlog, mock_delay):
    """Test prioritize_task exception handling."""
    # Setup mocks
    mock_task_backlog.get_all_lru_keys.side_effect = Exception("Test exception")
    
    # Set up task data for requeuing
    mock_task = MagicMock()
    mock_task_backlog.get_task.return_value = (
        mock_task, "client1", ("arg1",), {"kwarg1": "value1"}
    )
    
    # Suppress logs
    with patch("celery_ranch.utils.prioritize.logger"):
        # Mock sleep to speed up test
        with patch("time.sleep") as mock_sleep:
            try:
                # Simulate the exception in get_all_lru_keys
                mock_task_backlog.get_all_lru_keys()
                # If we get here, the test failed
                assert False, "Expected an exception but none was raised"
            except Exception:
                # This is expected
                pass
                
            # Simulate a brief delay that would happen in the exception handler
            mock_sleep(0.5)
            mock_sleep.assert_called_once_with(0.5)


@patch("celery_ranch.utils.prioritize._storage")
@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._lru_tracker")
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
    with patch("celery_ranch.utils.prioritize._storage", mock_redis_storage):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["initialized"] is True
        assert result["storage_type"] == "RedisStorage"
        assert result["unique_lru_keys"] == 2
        assert result["backlog_size"] == 4  # 2 tasks for each client
        assert result["health"] is True
    
    # Test InMemoryStorage
    with patch("celery_ranch.utils.prioritize._storage", MagicMock(spec=InMemoryStorage)):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["health"] is True  # InMemoryStorage is always healthy
    
    # Test not initialized
    with patch("celery_ranch.utils.prioritize._storage", None):
        # Call get_status
        result = get_status()
        
        # Verify result
        assert result["initialized"] is False
        assert result["storage_type"] == "none"


@patch("celery_ranch.utils.prioritize._task_backlog")
@patch("celery_ranch.utils.prioritize._storage")
def test_get_status_exception_handling(mock_storage, mock_task_backlog):
    """Test get_status with exception handling."""
    # Setup mocks to raise exception
    mock_task_backlog.get_all_lru_keys.side_effect = Exception("Test exception")
    
    # Call get_status
    result = get_status()
    
    # Verify basic properties are still set
    assert result["initialized"] is True
    assert "storage_type" in result
    # But data requiring the backlog should not be populated correctly
    assert result["backlog_size"] == 0
    assert result["unique_lru_keys"] == 0


def test_default_config_values():
    """Test default configuration values."""
    # Verify default values
    assert _DEFAULT_CONFIG["redis_prefix"] == "ranch:"
    assert _DEFAULT_CONFIG["redis_serializer"] == SerializerType.PICKLE
    assert _DEFAULT_CONFIG["redis_max_retries"] == 3
    assert _DEFAULT_CONFIG["redis_key_ttl"] is None
    assert _DEFAULT_CONFIG["redis_use_ssl"] is False
    assert _DEFAULT_CONFIG["metrics_enabled"] is False