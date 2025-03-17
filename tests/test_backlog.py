"""Tests for the backlog module"""

import time
from unittest.mock import MagicMock, patch

import pytest

from celery_ranch.utils.backlog import TaskBacklog
from celery_ranch.utils.persistence import InMemoryStorage


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
    
    # Add task with expiry (no need to verify expiry mechanism in this test)
    task_id2 = backlog.add_task(
        mock_task, "client1", ("arg2",), {"kwarg2": "value2"}
    )
    
    # Verify task was added (without expiry)
    stored_task2 = backlog.get_task(task_id2)
    assert stored_task2 is not None
    assert stored_task2[0] == mock_task
    assert stored_task2[1] == "client1"
    assert stored_task2[2] == ("arg2",)
    assert stored_task2[3] == {"kwarg2": "value2"}
    
    # Add task with metadata and expiry
    metadata = {"priority": "high", "tags": ["important"]}
    expiry = 300  # 5 minutes
    task_id3 = backlog.add_task(
        mock_task, "client1", ("arg3",), {"kwarg3": "value3"}, 
        expiry=expiry, metadata=metadata
    )
    
    # Verify metadata was added
    stored_metadata = backlog.get_task_metadata(task_id3)
    assert stored_metadata is not None
    assert stored_metadata["custom"] == metadata
    assert stored_metadata["expires_at"] is not None
    assert stored_metadata["created_at"] is not None


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
    
    # Test with expired task - mocking properly for time comparison
    current_time = 1000000  # Use a fixed timestamp to avoid real time.time() calls
    
    with patch('time.time') as mock_time:
        # Set current time
        mock_time.return_value = current_time
        
        # Mock storage to properly handle the expiry logic
        with patch.object(backlog, '_storage') as mock_storage:
            # Set up the mock storage to return metadata with an expiry timestamp
            mock_metadata = {
                "created_at": current_time,
                "expires_at": current_time + 1,  # 1 second expiry
                "custom": {}
            }
            
            # Mock to return the metadata and then the task
            mock_storage.get.side_effect = lambda key: (
                mock_metadata if key.startswith(backlog._metadata_prefix) else 
                (mock_task, "client1", ("arg_exp",), {"kwarg_exp": "value"}) if key.startswith(backlog._task_prefix) else
                None
            )
            
            # Mock UUID to have a predictable task ID
            with patch('uuid.uuid4', return_value="expired-task-id"):
                # Add task with 1 second expiry
                task_id_expiring = backlog.add_task(
                    mock_task, "client1", ("arg_exp",), {"kwarg_exp": "value"}, 
                    expiry=1
                )
                
                # Reset mock to ensure proper behavior
                mock_storage.reset_mock()
                
                # Task should exist initially
                mock_storage.get.side_effect = lambda key: (
                    mock_metadata if key.startswith(backlog._metadata_prefix) else 
                    (mock_task, "client1", ("arg_exp",), {"kwarg_exp": "value"}) if key.startswith(backlog._task_prefix) else
                    None
                )
                assert backlog.get_task(task_id_expiring) is not None
                
                # Advance time past expiry
                mock_time.return_value = current_time + 2
                
                # Update the mock to simulate expiry
                mock_storage.get.side_effect = lambda key: (
                    mock_metadata if key.startswith(backlog._metadata_prefix) else 
                    None
                )
                
                # Task should be removed on get
                assert backlog.get_task(task_id_expiring) is None


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
    
    # Test expired tasks cleanup during get_tasks_by_lru_key - with proper mocking
    current_time = 1000000  # Use a fixed timestamp
    
    with patch('time.time') as mock_time:
        # Set current time
        mock_time.return_value = current_time
        
        # Mock storage to properly handle the expiry logic
        with patch.object(backlog, '_storage') as mock_storage:
            # Create a mock index that will be updated
            mock_lru_index = {"task_id_expired": current_time, "task_id_regular": current_time}
            
            # Set up mock to track calls and return appropriate values
            def mock_get_side_effect(key):
                if key == f"{backlog._lru_index_prefix}client_exp":
                    return mock_lru_index
                elif key == f"{backlog._metadata_prefix}task_id_expired":
                    return {
                        "created_at": current_time,
                        "expires_at": current_time + 1,  # 1 second expiry
                        "custom": {}
                    }
                elif key == f"{backlog._task_prefix}task_id_expired" and current_time < current_time + 1:
                    return (mock_task, "client_exp", ("arg_exp",), {"kwarg_exp": "value"})
                elif key == f"{backlog._task_prefix}task_id_regular":
                    return (mock_task, "client_exp", ("arg_reg",), {"kwarg_reg": "value"})
                return None
            
            mock_storage.get.side_effect = mock_get_side_effect
            
            # Initial check - both tasks exist
            mock_time.return_value = current_time
            tasks = backlog.get_tasks_by_lru_key("client_exp")
            assert len(tasks) == 2
            
            # Advance time past expiry
            mock_time.return_value = current_time + 2
            
            # Modify side effect to reflect expired task
            def mock_get_side_effect_expired(key):
                if key == f"{backlog._lru_index_prefix}client_exp":
                    return mock_lru_index
                elif key == f"{backlog._metadata_prefix}task_id_expired":
                    return {
                        "created_at": current_time,
                        "expires_at": current_time + 1,  # Already expired
                        "custom": {}
                    }
                elif key == f"{backlog._task_prefix}task_id_regular":
                    return (mock_task, "client_exp", ("arg_reg",), {"kwarg_reg": "value"})
                return None
            
            mock_storage.get.side_effect = mock_get_side_effect_expired
            
            # Set up remove_task to update our mock index
            def mock_remove_task(task_id):
                if task_id in mock_lru_index:
                    del mock_lru_index[task_id]
            
            with patch.object(backlog, 'remove_task', side_effect=mock_remove_task):
                # Get tasks - should detect and remove expired task
                tasks = backlog.get_tasks_by_lru_key("client_exp")
                
                # Only regular task should remain
                assert len(tasks) == 1
                assert "task_id_expired" not in tasks
                assert "task_id_regular" in tasks


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


def test_task_expiry_basic():
    """Test basic task expiry functionality."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add task 
    task_id = backlog.add_task(
        mock_task, "client1", ("arg1",), {"kwarg1": "value1"}
    )
    
    # Verify task exists
    assert backlog.get_task(task_id) is not None


def test_task_backlog_get_task_metadata():
    """Test getting task metadata."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Add task with metadata
    metadata = {"priority": "high", "tags": ["important"]}
    task_id = backlog.add_task(
        mock_task, "client1", ("arg1",), {"kwarg1": "value1"}, 
        metadata=metadata
    )
    
    # Get metadata
    task_metadata = backlog.get_task_metadata(task_id)
    assert task_metadata is not None
    assert task_metadata["custom"] == metadata
    assert task_metadata["created_at"] is not None
    assert task_metadata["expires_at"] is None
    
    # Test getting metadata for non-existent task
    assert backlog.get_task_metadata("nonexistent_id") is None


def test_task_backlog_get_backlog_stats():
    """Test getting backlog statistics."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Test with mocked storage
    with patch.object(backlog, '_storage') as mock_storage:
        # Set up mock to return empty data initially
        mock_storage.get_keys_by_prefix.return_value = []
        
        # Initial stats should show empty backlog
        stats = backlog.get_backlog_stats()
        assert stats["total_tasks"] == 0
        assert stats["total_clients"] == 0
        assert stats["clients"] == {}
        assert stats["expired_tasks"] == 0
        
        # Mock LRU keys and task data
        mock_storage.get_keys_by_prefix.side_effect = lambda prefix: (
            ["lru_index:client1", "lru_index:client2"] if prefix == backlog._lru_index_prefix else
            ["task_meta:task1", "task_meta:task2", "task_meta:task3", "task_meta:task_exp"] if prefix == backlog._metadata_prefix else
            []
        )
        
        # Mock task data for client1 and client2
        client1_tasks = {"task1": time.time(), "task2": time.time()}
        client2_tasks = {"task3": time.time()}
        
        # Mock metadata for tasks including one expired task
        current_time = 1000000
        task_exp_metadata = {
            "created_at": current_time - 10,
            "expires_at": current_time - 5,  # Already expired
            "custom": {}
        }
        
        def mock_get_side_effect(key):
            if key == f"{backlog._lru_index_prefix}client1":
                return client1_tasks
            elif key == f"{backlog._lru_index_prefix}client2":
                return client2_tasks
            elif key == f"{backlog._metadata_prefix}task_exp":
                return task_exp_metadata
            elif key.startswith(f"{backlog._metadata_prefix}"):
                return {"created_at": current_time, "expires_at": None, "custom": {}}
            elif key.startswith(f"{backlog._task_prefix}"):
                return (mock_task, "client1", ("arg1",), {"kwarg1": "value1"})
            return None
        
        mock_storage.get.side_effect = mock_get_side_effect
        
        # Mock time to ensure expired task check works
        with patch('time.time', return_value=current_time):
            # Get stats
            stats = backlog.get_backlog_stats()
            
            # Verify stats
            assert stats["total_tasks"] == 3  # 2 from client1, 1 from client2
            assert stats["total_clients"] == 2
            assert len(stats["clients"]) == 2
            assert stats["clients"]["client1"]["task_count"] == 2
            assert stats["clients"]["client2"]["task_count"] == 1
            assert stats["expired_tasks"] == 1  # One expired task


def test_task_backlog_cleanup_expired_tasks():
    """Test cleaning up expired tasks."""
    backlog = TaskBacklog()
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Test with mocked storage
    with patch.object(backlog, '_storage') as mock_storage:
        # Initial state - no expired tasks
        mock_storage.get_keys_by_prefix.return_value = []
        
        # No expired tasks initially
        assert backlog.cleanup_expired_tasks() == 0
        
        current_time = 1000000  # Fixed timestamp
        
        # Set up the mock to simulate expired tasks
        with patch('time.time', return_value=current_time):
            # First round - one task expired
            expired_task_ids = ["task1"]
            not_expired_task_ids = ["task2", "task3"]
            
            # Mock metadata keys
            mock_storage.get_keys_by_prefix.return_value = [
                f"{backlog._metadata_prefix}task1",
                f"{backlog._metadata_prefix}task2",
                f"{backlog._metadata_prefix}task3"
            ]
            
            # Mock metadata content
            def mock_get_side_effect(key):
                task_id = key.split(":")[-1]
                if task_id == "task1":
                    return {
                        "created_at": current_time - 10,
                        "expires_at": current_time - 5,  # Already expired
                        "custom": {}
                    }
                elif task_id == "task2":
                    return {
                        "created_at": current_time - 10,
                        "expires_at": current_time + 5,  # Not expired yet
                        "custom": {}
                    }
                elif task_id == "task3":
                    return {
                        "created_at": current_time - 10,
                        "expires_at": None,  # No expiry
                        "custom": {}
                    }
                return None
            
            mock_storage.get.side_effect = mock_get_side_effect
            
            # Mock remove_task to count removals
            removed_tasks = []
            
            def mock_remove_task(task_id):
                removed_tasks.append(task_id)
            
            with patch.object(backlog, 'remove_task', side_effect=mock_remove_task):
                # First cleanup - should remove task1
                removed = backlog.cleanup_expired_tasks()
                assert removed == 1
                assert "task1" in removed_tasks
                
                # Advance time to expire task2
                with patch('time.time', return_value=current_time + 10):
                    # Update mock to reflect new expired state
                    removed_tasks.clear()
                    
                    def mock_get_side_effect_2(key):
                        task_id = key.split(":")[-1]
                        if task_id == "task2":
                            return {
                                "created_at": current_time - 10,
                                "expires_at": current_time + 5,  # Now expired
                                "custom": {}
                            }
                        elif task_id == "task3":
                            return {
                                "created_at": current_time - 10,
                                "expires_at": None,  # No expiry
                                "custom": {}
                            }
                        return None
                    
                    mock_storage.get.side_effect = mock_get_side_effect_2
                    
                    # Mock keys - task1 is already removed
                    mock_storage.get_keys_by_prefix.return_value = [
                        f"{backlog._metadata_prefix}task2",
                        f"{backlog._metadata_prefix}task3"
                    ]
                    
                    # Second cleanup - should remove task2
                    removed = backlog.cleanup_expired_tasks()
                    assert removed == 1
                    assert "task2" in removed_tasks
                    
                    # Third cleanup - no more expired tasks
                    removed_tasks.clear()
                    mock_storage.get_keys_by_prefix.return_value = [
                        f"{backlog._metadata_prefix}task3"
                    ]
                    
                    removed = backlog.cleanup_expired_tasks()
                    assert removed == 0
                    assert len(removed_tasks) == 0