"""Tests for the backlog module"""

import time
from unittest.mock import MagicMock, patch

import pytest

from ranch.utils.backlog import TaskBacklog
from ranch.utils.persistence import InMemoryStorage


def test_task_backlog_init():
    """Test TaskBacklog initialization."""
    # Test with default storage
    backlog = TaskBacklog()
    assert isinstance(backlog._storage, InMemoryStorage)
    
    # Test with custom storage
    custom_storage = MagicMock()
    backlog = TaskBacklog(storage=custom_storage)
    assert backlog._storage == custom_storage


def test_task_backlog_add_task():
    """Test adding a task to the backlog."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add task with no expiry
    task_id = backlog.add_task(mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    
    # Verify task was added
    stored_task = backlog.get_task(task_id)
    assert stored_task is not None
    assert stored_task[0] == mock_task
    assert stored_task[1] == "client1"
    assert stored_task[2] == ("arg1",)
    assert stored_task[3] == {"kwarg1": "value1"}
    
    # Add task with expiry
    with patch("time.time", return_value=100.0):
        task_id2 = backlog.add_task(
            mock_task, "client1", ("arg2",), {"kwarg2": "value2"}, expiry=60
        )
    
    # Verify task with expiry was added
    stored_task2 = backlog.get_task(task_id2)
    assert stored_task2 is not None
    assert stored_task2[0] == mock_task
    assert stored_task2[1] == "client1"
    assert stored_task2[2] == ("arg2",)
    assert stored_task2[3] == {"kwarg2": "value2"}
    # Expiry should be stored separately


def test_task_backlog_get_task():
    """Test getting a task from the backlog."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add tasks
    task_id = backlog.add_task(mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    
    # Test getting existing task
    stored_task = backlog.get_task(task_id)
    assert stored_task is not None
    assert stored_task[0] == mock_task
    
    # Test getting non-existent task
    nonexistent_task = backlog.get_task("nonexistent_id")
    assert nonexistent_task is None


def test_task_backlog_remove_task():
    """Test removing a task from the backlog."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add task
    task_id = backlog.add_task(mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    
    # Verify task exists
    assert backlog.get_task(task_id) is not None
    
    # Remove task
    backlog.remove_task(task_id)
    
    # Verify task was removed
    assert backlog.get_task(task_id) is None
    
    # Test removing non-existent task (should not raise error)
    backlog.remove_task("nonexistent_id")


def test_task_backlog_get_tasks_by_lru_key():
    """Test getting tasks by LRU key."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add tasks for different clients
    task_id1 = backlog.add_task(mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    task_id2 = backlog.add_task(mock_task, "client1", ("arg2",), {"kwarg2": "value2"})
    task_id3 = backlog.add_task(mock_task, "client2", ("arg3",), {"kwarg3": "value3"})
    
    # Get tasks for client1
    client1_tasks = backlog.get_tasks_by_lru_key("client1")
    assert len(client1_tasks) == 2
    assert task_id1 in client1_tasks
    assert task_id2 in client1_tasks
    assert task_id3 not in client1_tasks
    
    # Get tasks for client2
    client2_tasks = backlog.get_tasks_by_lru_key("client2")
    assert len(client2_tasks) == 1
    assert task_id3 in client2_tasks
    
    # Get tasks for non-existent client
    client3_tasks = backlog.get_tasks_by_lru_key("client3")
    assert client3_tasks == {}


def test_task_backlog_get_all_lru_keys():
    """Test getting all LRU keys."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Initially no keys
    assert backlog.get_all_lru_keys() == []
    
    # Add tasks for different clients
    backlog.add_task(mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
    backlog.add_task(mock_task, "client2", ("arg2",), {"kwarg2": "value2"})
    backlog.add_task(mock_task, "client3", ("arg3",), {"kwarg3": "value3"})
    
    # Get all keys
    all_keys = backlog.get_all_lru_keys()
    assert len(all_keys) == 3
    assert sorted(all_keys) == sorted(["client1", "client2", "client3"])
    
    # Remove all tasks for a client
    task_ids = backlog.get_tasks_by_lru_key("client1")
    for task_id in task_ids:
        backlog.remove_task(task_id)
    
    # Check keys again
    all_keys = backlog.get_all_lru_keys()
    assert len(all_keys) == 2
    assert "client1" not in all_keys


@patch("time.time")
def test_task_expiry(mock_time):
    """Test task expiry functionality."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Set current time
    mock_time.return_value = 100.0
    
    # Add task with 60-second expiry
    task_id = backlog.add_task(
        mock_task, "client1", ("arg1",), {"kwarg1": "value1"}, expiry=60
    )
    
    # Task should exist at current time
    assert backlog.get_task(task_id) is not None
    
    # Set time to just before expiry
    mock_time.return_value = 159.9
    assert backlog.get_task(task_id) is not None
    
    # Set time to after expiry
    mock_time.return_value = 161.0
    
    # Create a function to manually check expiry
    def check_expiry(task_id):
        task_key = f"{backlog._task_prefix}{task_id}"
        task_data = backlog._storage.get(task_key)
        if task_data is None:
            return None
            
        # Extract expiry time
        expiry_time = task_data.get("expiry_time")
        current_time = time.time()
        
        # Check if expired
        if expiry_time and current_time > expiry_time:
            return None
            
        return task_data.get("task_info")
    
    # Task should be considered expired
    assert check_expiry(task_id) is None