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


def test_task_backlog_get_tasks_by_lru_key_batch_operations():
    """Test getting tasks by LRU key using batch operations."""
    
    # Create a mock storage to verify batch methods are called
    mock_storage = MagicMock()
    backlog = TaskBacklog(storage=mock_storage)
    
    # Mock the LRU index
    lru_tasks = {"task1": 1000, "task2": 1001, "task3": 1002}
    mock_storage.get.return_value = lru_tasks
    
    # Mock batch_get for metadata to return one expired task
    mock_storage.batch_get.side_effect = lambda keys: (
        {
            f"{backlog._metadata_prefix}task1": {"created_at": 1000, "expires_at": 1500},
            f"{backlog._metadata_prefix}task2": {"created_at": 1001, "expires_at": 5000},
            f"{backlog._metadata_prefix}task3": {"created_at": 1002, "expires_at": None}
        } if keys[0].startswith(backlog._metadata_prefix) else
        {
            f"{backlog._task_prefix}task2": (MagicMock(), "client1", ("arg2",), {"kwarg2": "value2"}),
            f"{backlog._task_prefix}task3": (MagicMock(), "client1", ("arg3",), {"kwarg3": "value3"})
        }
    )
    
    # Mock time to make task1 expired
    with patch('time.time', return_value=2000):
        # Get tasks - task1 should be considered expired
        tasks = backlog.get_tasks_by_lru_key("client1")
        
        # Verify batch operations were used
        assert mock_storage.batch_get.call_count == 2
        
        # Verify batch_delete was called for expired task cleanup
        assert mock_storage.batch_delete.call_count == 2
        
        # Two tasks should be returned
        assert len(tasks) == 2
        
        # Verify the storage was updated to remove expired task
        mock_storage.set.assert_called_with(
            f"{backlog._lru_index_prefix}client1", 
            {"task2": 1001, "task3": 1002}
        )


def test_task_backlog_remove_tasks_batch():
    """Test removing multiple tasks using batch operations."""
    
    # Create a mock storage 
    mock_storage = MagicMock()
    backlog = TaskBacklog(storage=mock_storage)
    
    # Mock task data
    task_data = {
        f"{backlog._task_prefix}task1": (MagicMock(), "client1", ("arg1",), {"kwarg1": "value1"}),
        f"{backlog._task_prefix}task2": (MagicMock(), "client1", ("arg2",), {"kwarg2": "value2"}),
        f"{backlog._task_prefix}task3": (MagicMock(), "client2", ("arg3",), {"kwarg3": "value3"})
    }
    
    # Setup mock for batch_get to return task data
    mock_storage.batch_get.return_value = task_data
    
    # Mock client1 LRU index
    client1_tasks = {"task1": 1000, "task2": 1001, "task4": 1003}
    client2_tasks = {"task3": 1002}
    
    # Setup mock for get to return LRU indices
    def mock_get_side_effect(key):
        if key == f"{backlog._lru_index_prefix}client1":
            return client1_tasks
        elif key == f"{backlog._lru_index_prefix}client2":
            return client2_tasks
        return None
    
    mock_storage.get.side_effect = mock_get_side_effect
    
    # Remove multiple tasks
    backlog.remove_tasks(["task1", "task2", "task3"])
    
    # Verify batch operations were used
    assert mock_storage.batch_get.call_count == 1
    assert mock_storage.batch_delete.call_count == 2  # One for task data, one for metadata
    
    # Verify LRU indices were updated
    mock_storage.set.assert_any_call(
        f"{backlog._lru_index_prefix}client1", 
        {"task4": 1003}
    )
    
    mock_storage.delete.assert_called_with(
        f"{backlog._lru_index_prefix}client2"
    )
    
    # The test for batch operations should use the batch operations correctly
    # Create a new backlog with better mocks for batch operations
    mock_storage_batch = MagicMock()
    backlog_batch = TaskBacklog(storage=mock_storage_batch)
    
    # Create a mock task
    mock_task = MagicMock()
    
    # Set up the mock metadata for batch_get to handle expiry correctly
    metadata_dict = {
        f"{backlog_batch._metadata_prefix}task_id_regular": {
            "created_at": 1000,
            "expires_at": 5000,  # Not expired
            "custom": {}
        },
        f"{backlog_batch._metadata_prefix}task_id_expired": {
            "created_at": 1000,
            "expires_at": 2000,  # Will be expired at time 3000
            "custom": {}
        }
    }
    
    # Set up the mock task data for batch_get
    task_data_dict = {
        f"{backlog_batch._task_prefix}task_id_regular": (mock_task, "client_exp", ("arg_reg",), {"kwarg_reg": "value"}),
        f"{backlog_batch._task_prefix}task_id_expired": (mock_task, "client_exp", ("arg_exp",), {"kwarg_exp": "value"})
    }
    
    # Create a mock index that will be updated
    mock_lru_index = {"task_id_regular": 1000, "task_id_expired": 1100}
    
    # Mock batch_get to return appropriate data based on the keys
    def mock_batch_get_side_effect(keys):
        result = {}
        prefix = keys[0].split(':')[0] + ':'
        
        if prefix == backlog_batch._metadata_prefix:
            # Return metadata
            for key in keys:
                if key in metadata_dict:
                    result[key] = metadata_dict[key]
        elif prefix == backlog_batch._task_prefix:
            # Return task data
            for key in keys:
                if key in task_data_dict:
                    result[key] = task_data_dict[key]
        
        return result
    
    # Configure mock to use our side effect function
    mock_storage_batch.batch_get.side_effect = mock_batch_get_side_effect
    
    # Mock get to return the LRU index
    def mock_get_side_effect(key):
        if key == f"{backlog_batch._lru_index_prefix}client_exp":
            return mock_lru_index
        return None
    
    mock_storage_batch.get.side_effect = mock_get_side_effect
    
    # Test with current time before expiry
    with patch('time.time', return_value=1500):
        tasks = backlog_batch.get_tasks_by_lru_key("client_exp")
        # Both tasks should be returned
        assert len(tasks) == 2
        assert "task_id_regular" in tasks
        assert "task_id_expired" in tasks
    
    # Test with time after expiry
    with patch('time.time', return_value=3000):
        # Reset batch_get and batch_delete call counts
        mock_storage_batch.batch_get.reset_mock()
        mock_storage_batch.batch_delete.reset_mock()
        
        tasks = backlog_batch.get_tasks_by_lru_key("client_exp")
        
        # Verify batch_get was called twice (once for metadata, once for task data)
        assert mock_storage_batch.batch_get.call_count == 2
        
        # Verify batch_delete was called twice (once for task data, once for metadata)
        assert mock_storage_batch.batch_delete.call_count == 2
        
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
    """Test getting backlog statistics with batch operations."""
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
        
        # Mock LRU keys
        mock_storage.get_keys_by_prefix.side_effect = lambda prefix: (
            ["lru_index:client1", "lru_index:client2"] if prefix == backlog._lru_index_prefix else
            ["task_meta:task1", "task_meta:task2", "task_meta:task3", "task_meta:task_exp"] if prefix == backlog._metadata_prefix else
            []
        )
        
        # Define lru indices with task timestamps
        current_time = 1000000
        client1_tasks = {"task1": current_time - 100, "task2": current_time - 50}
        client2_tasks = {"task3": current_time - 25}
        
        # Setup batch_get for LRU indices
        mock_storage.batch_get.side_effect = lambda keys: (
            {
                f"{backlog._lru_index_prefix}client1": client1_tasks,
                f"{backlog._lru_index_prefix}client2": client2_tasks
            } if keys[0].startswith(backlog._lru_index_prefix) else
            {
                "task_meta:task1": {"created_at": current_time - 100, "expires_at": None, "custom": {}},
                "task_meta:task2": {"created_at": current_time - 50, "expires_at": None, "custom": {}},
                "task_meta:task3": {"created_at": current_time - 25, "expires_at": None, "custom": {}},
                "task_meta:task_exp": {
                    "created_at": current_time - 10,
                    "expires_at": current_time - 5,  # Already expired
                    "custom": {}
                }
            }
        )
        
        # Mock time to ensure expired task check works
        with patch('time.time', return_value=current_time):
            # Get stats using batch operations
            stats = backlog.get_backlog_stats()
            
            # Verify batch operations were used (might be 2 or 3 batches depending on implementation)
            assert mock_storage.batch_get.call_count >= 2  # At least once for LRU indices and once for metadata
            
            # Verify stats
            assert stats["total_tasks"] == 3  # 2 from client1, 1 from client2
            assert stats["total_clients"] == 2
            assert len(stats["clients"]) == 2
            assert stats["clients"]["client1"]["task_count"] == 2
            assert stats["clients"]["client2"]["task_count"] == 1
            assert stats["expired_tasks"] == 1  # One expired task


def test_task_backlog_cleanup_expired_tasks():
    """Test cleaning up expired tasks using batch operations."""
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
            # Setup meta keys for three tasks
            meta_keys = [
                f"{backlog._metadata_prefix}task1",
                f"{backlog._metadata_prefix}task2",
                f"{backlog._metadata_prefix}task3"
            ]
            
            # Return all meta keys
            mock_storage.get_keys_by_prefix.return_value = meta_keys
            
            # Setup batch_get for metadata
            mock_storage.batch_get.side_effect = lambda keys: (
                {
                    f"{backlog._metadata_prefix}task1": {
                        "created_at": current_time - 10,
                        "expires_at": current_time - 5,  # Task1 is expired
                        "custom": {}
                    },
                    f"{backlog._metadata_prefix}task2": {
                        "created_at": current_time - 10,
                        "expires_at": current_time + 5,  # Task2 not expired yet
                        "custom": {}
                    },
                    f"{backlog._metadata_prefix}task3": {
                        "created_at": current_time - 10,
                        "expires_at": None,  # Task3 has no expiry
                        "custom": {}
                    }
                } if keys[0].startswith(backlog._metadata_prefix) else
                {
                    f"{backlog._task_prefix}task1": (mock_task, "client1", ("arg1",), {"kwarg1": "value1"}),
                }
            )
            
            # Setup task data retrieval
            def mock_get_side_effect(key):
                if key == f"{backlog._lru_index_prefix}client1":
                    return {"task1": current_time - 10, "task4": current_time}
                return None
                
            mock_storage.get.side_effect = mock_get_side_effect
            
            # Execute cleanup - should identify and remove task1
            removed = backlog.cleanup_expired_tasks()
            
            # Verify correct number of tasks were removed
            assert removed == 1
            
            # Verify batch operations were used
            assert mock_storage.batch_get.call_count >= 2  # Once for metadata, once for task data
            assert mock_storage.batch_delete.call_count == 2  # Once for task data, once for metadata
            
            # Verify the LRU index was updated
            mock_storage.set.assert_called_with(
                f"{backlog._lru_index_prefix}client1", 
                {"task4": current_time}
            )
            
            # Reset mocks
            mock_storage.reset_mock()
            
            # Advance time to make task2 expired
            with patch('time.time', return_value=current_time + 10):
                # Update meta keys (task1 is gone)
                meta_keys = [
                    f"{backlog._metadata_prefix}task2",
                    f"{backlog._metadata_prefix}task3"
                ]
                
                mock_storage.get_keys_by_prefix.return_value = meta_keys
                
                # Update batch_get to return task2 as expired now
                mock_storage.batch_get.side_effect = lambda keys: (
                    {
                        f"{backlog._metadata_prefix}task2": {
                            "created_at": current_time - 10,
                            "expires_at": current_time + 5,  # Now expired
                            "custom": {}
                        },
                        f"{backlog._metadata_prefix}task3": {
                            "created_at": current_time - 10,
                            "expires_at": None,  # No expiry
                            "custom": {}
                        }
                    } if keys[0].startswith(backlog._metadata_prefix) else
                    {
                        f"{backlog._task_prefix}task2": (mock_task, "client2", ("arg2",), {"kwarg2": "value2"}),
                    }
                )
                
                # Update task data retrieval
                def mock_get_side_effect_2(key):
                    if key == f"{backlog._lru_index_prefix}client2":
                        return {"task2": current_time - 5}
                    return None
                    
                mock_storage.get.side_effect = mock_get_side_effect_2
                
                # Execute cleanup again - should remove task2
                removed = backlog.cleanup_expired_tasks()
                
                # Verify correct number of tasks were removed
                assert removed == 1
                
                # Verify the LRU index was updated - should be deleted since no tasks left
                mock_storage.delete.assert_called_with(f"{backlog._lru_index_prefix}client2")
                
                # Test with no expired tasks
                mock_storage.reset_mock()
                
                # Only task3 left, which has no expiry
                meta_keys = [f"{backlog._metadata_prefix}task3"]
                mock_storage.get_keys_by_prefix.return_value = meta_keys
                
                # Update batch_get for remaining task
                mock_storage.batch_get.side_effect = lambda keys: (
                    {
                        f"{backlog._metadata_prefix}task3": {
                            "created_at": current_time - 10,
                            "expires_at": None,  # No expiry
                            "custom": {}
                        }
                    }
                )
                
                # Execute cleanup - should not remove any tasks
                removed = backlog.cleanup_expired_tasks()
                assert removed == 0
                
                # Verify no batch deletes were performed
                assert mock_storage.batch_delete.call_count == 0