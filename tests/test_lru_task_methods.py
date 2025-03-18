"""Tests for the LRUTask methods in task.py"""

import time
from unittest.mock import MagicMock, patch

import pytest
from celery import Celery
from celery.result import AsyncResult

from celery_ranch import lru_task
from celery_ranch.task import LRUTask
from celery_ranch.utils.lru_tracker import LRUTracker
from celery_ranch.utils.backlog import TaskBacklog


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


def test_lru_delay_simple(lru_task_instance):
    """Test basic lru_delay functionality."""
    with patch("celery_ranch.task.prioritize_task") as mock_prioritize_task:
        mock_result = MagicMock()
        mock_prioritize_task.delay.return_value = mock_result
        
        # Call lru_delay with simple parameters
        result = lru_task_instance.lru_delay("client1", "value1")
        
        # Verify prioritize_task.delay was called
        assert mock_prioritize_task.delay.called
        
        # Result should be what prioritize_task.delay returns
        assert result is mock_prioritize_task.delay.return_value


@patch("celery_ranch.utils.prioritize._lru_tracker")
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


@patch("celery_ranch.utils.prioritize._lru_tracker")
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
    
    
@patch("celery_ranch.utils.prioritize._lru_tracker")
def test_set_custom_data(mock_lru_tracker, lru_task_instance):
    """Test set_custom_data method."""
    # Setup mocks
    mock_lru_tracker.set_custom_data.return_value = None
    
    # Test successful call
    result = lru_task_instance.set_custom_data("client1", "bid", 10.5)
    assert result is True
    mock_lru_tracker.set_custom_data.assert_called_once_with("client1", "bid", 10.5)
    
    # Test with exception
    mock_lru_tracker.set_custom_data.side_effect = Exception("Failed to set custom data")
    result = lru_task_instance.set_custom_data("client1", "invalid", "value")
    assert result is False


@patch("celery_ranch.utils.prioritize._lru_tracker")
def test_get_custom_data(mock_lru_tracker, lru_task_instance):
    """Test get_custom_data method."""
    # Setup mocks
    mock_lru_tracker.get_custom_data.return_value = {"bid": 10.5, "tier": "premium"}
    
    # Test successful call
    result = lru_task_instance.get_custom_data("client1")
    assert result == {"bid": 10.5, "tier": "premium"}
    mock_lru_tracker.get_custom_data.assert_called_once_with("client1")
    
    # Test with exception
    mock_lru_tracker.get_custom_data.side_effect = Exception("Failed to get custom data")
    result = lru_task_instance.get_custom_data("client1")
    assert result == {}


@patch("celery_ranch.utils.prioritize._lru_tracker")
@patch("celery_ranch.utils.prioritize._task_backlog")
def test_get_client_metadata(mock_task_backlog, mock_lru_tracker, lru_task_instance):
    """Test get_client_metadata method."""
    # Setup mocks
    metadata = MagicMock()
    metadata.weight = 0.5
    metadata.timestamp = time.time()
    metadata.tags = {"region": "us-east", "tier": "premium"}
    metadata.custom_data = {"bid": 10.5, "balance": 100.0}
    
    mock_lru_tracker.get_metadata.return_value = metadata
    mock_task_backlog.get_tasks_by_lru_key.return_value = {"task1": {}, "task2": {}}
    
    # Test the method
    result = lru_task_instance.get_client_metadata("client1")
    
    # Verify result
    assert result["lru_key"] == "client1"
    assert result["weight"] == 0.5
    assert result["last_execution"] == metadata.timestamp
    assert result["tags"] == metadata.tags
    assert result["custom_data"] == metadata.custom_data
    assert result["pending_tasks"] == 2
    
    # Verify calls
    mock_lru_tracker.get_metadata.assert_called_once_with("client1")
    mock_task_backlog.get_tasks_by_lru_key.assert_called_once_with("client1")


@patch("celery_ranch.utils.prioritize._lru_tracker")
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


def test_get_system_status(lru_task_instance):
    """Test get_system_status method - much simpler."""
    # Just verify the method exists and returns a dictionary
    result = lru_task_instance.get_system_status()
    assert isinstance(result, dict)
    assert "initialized" in result
    assert "storage_type" in result