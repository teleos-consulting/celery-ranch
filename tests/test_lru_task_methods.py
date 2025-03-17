"""Tests for the LRUTask methods in task.py"""

import time
from unittest.mock import MagicMock, patch

import pytest
from celery import Celery
from celery.result import AsyncResult

from ranch import lru_task
from ranch.task import LRUTask
from ranch.utils.lru_tracker import LRUTracker
from ranch.utils.backlog import TaskBacklog


@pytest.fixture
def celery_app():
    app = Celery("tests")
    app.conf.update(
        task_always_eager=True, broker_url="memory://", result_backend="rpc://"
    )
    return app


@pytest.fixture
def lru_task_instance(celery_app):
    @lru_task(celery_app)
    def test_task(arg1, arg2=None):
        return arg1, arg2
    
    return test_task


@patch("ranch.utils.prioritize._lru_tracker")
@patch("ranch.utils.prioritize._task_backlog")
@patch("ranch.utils.prioritize.prioritize_task")
def test_lru_delay_with_tags_and_weight(mock_prioritize_task, mock_task_backlog, mock_lru_tracker, lru_task_instance):
    """Test lru_delay with tags and priority weight."""
    # Setup mocks
    mock_result = MagicMock(spec=AsyncResult)
    mock_prioritize_task.delay.return_value = mock_result
    mock_task_backlog.add_task.return_value = "task-id-123"
    
    # Call lru_delay with tags and priority weight
    result = lru_task_instance.lru_delay(
        "client1", 
        "value1", 
        "value2",
        priority_weight=0.5,
        tags={"region": "us-east", "tier": "premium"},
        expiry=300
    )
    
    # Verify result
    assert result == mock_result
    
    # Verify lru_tracker calls
    mock_lru_tracker.set_weight.assert_called_once_with("client1", 0.5)
    assert mock_lru_tracker.add_tag.call_count == 2
    mock_lru_tracker.add_tag.assert_any_call("client1", "region", "us-east")
    mock_lru_tracker.add_tag.assert_any_call("client1", "tier", "premium")
    
    # Verify task_backlog calls
    mock_task_backlog.add_task.assert_called_once()
    args, kwargs = mock_task_backlog.add_task.call_args
    assert kwargs["lru_key"] == "client1"
    assert kwargs["expiry"] == 300
    
    # Verify prioritize_task calls
    mock_prioritize_task.delay.assert_called_once_with(task_id="task-id-123")


@patch("ranch.utils.prioritize._lru_tracker")
def test_set_priority_weight(mock_lru_tracker, lru_task_instance):
    """Test set_priority_weight method."""
    # Setup mocks
    mock_lru_tracker.set_weight.return_value = None
    
    # Test successful call
    result = lru_task_instance.set_priority_weight("client1", 0.5)
    assert result is True
    mock_lru_tracker.set_weight.assert_called_once_with("client1", 0.5)
    
    # Test with exception
    mock_lru_tracker.set_weight.side_effect = ValueError("Invalid weight")
    result = lru_task_instance.set_priority_weight("client1", -1)
    assert result is False


@patch("ranch.utils.prioritize._lru_tracker")
def test_add_tag(mock_lru_tracker, lru_task_instance):
    """Test add_tag method."""
    # Setup mocks
    mock_lru_tracker.add_tag.return_value = None
    
    # Test successful call
    result = lru_task_instance.add_tag("client1", "region", "us-east")
    assert result is True
    mock_lru_tracker.add_tag.assert_called_once_with("client1", "region", "us-east")
    
    # Test with exception
    mock_lru_tracker.add_tag.side_effect = Exception("Failed to add tag")
    result = lru_task_instance.add_tag("client1", "invalid", "value")
    assert result is False


@patch("ranch.utils.prioritize._lru_tracker")
@patch("ranch.utils.prioritize._task_backlog")
def test_get_client_metadata(mock_task_backlog, mock_lru_tracker, lru_task_instance):
    """Test get_client_metadata method."""
    # Setup mocks
    metadata = MagicMock()
    metadata.weight = 0.5
    metadata.timestamp = time.time()
    metadata.tags = {"region": "us-east", "tier": "premium"}
    
    mock_lru_tracker.get_metadata.return_value = metadata
    mock_task_backlog.get_tasks_by_lru_key.return_value = {"task1": {}, "task2": {}}
    
    # Test the method
    result = lru_task_instance.get_client_metadata("client1")
    
    # Verify result
    assert result["lru_key"] == "client1"
    assert result["weight"] == 0.5
    assert result["last_execution"] == metadata.timestamp
    assert result["tags"] == metadata.tags
    assert result["pending_tasks"] == 2
    
    # Verify calls
    mock_lru_tracker.get_metadata.assert_called_once_with("client1")
    mock_task_backlog.get_tasks_by_lru_key.assert_called_once_with("client1")


@patch("ranch.utils.prioritize._lru_tracker")
def test_get_tagged_clients(mock_lru_tracker, lru_task_instance):
    """Test get_tagged_clients method."""
    # Setup mocks
    mock_lru_tracker.get_keys_by_tag.return_value = ["client1", "client3"]
    
    # Test the method
    result = lru_task_instance.get_tagged_clients("region", "us-east")
    
    # Verify result
    assert result == ["client1", "client3"]
    
    # Verify calls
    mock_lru_tracker.get_keys_by_tag.assert_called_once_with("region", "us-east")


@patch("ranch.utils.prioritize.get_status")
def test_get_system_status(mock_get_status, lru_task_instance):
    """Test get_system_status method."""
    # Setup mocks
    mock_get_status.return_value = {
        "initialized": True,
        "storage_type": "InMemoryStorage",
        "backlog_size": 5,
        "unique_lru_keys": 3,
        "health": True
    }
    
    # Test the method
    result = lru_task_instance.get_system_status()
    
    # Verify result
    assert result == mock_get_status.return_value
    
    # Verify calls
    mock_get_status.assert_called_once()