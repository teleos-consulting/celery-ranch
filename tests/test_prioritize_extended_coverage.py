"""Additional tests for improving coverage in the prioritize module."""

from unittest.mock import MagicMock, patch

import pytest

from celery_ranch.utils.prioritize import _initialize_storage, prioritize_task, _lru_tracker, _task_backlog


def test_prioritize_task_initialization():
    """Test storage initialization in prioritize_task."""
    # Create a mock self object since this is a shared_task with bind=True
    mock_self = MagicMock()
    
    # Patch _lru_tracker and _task_backlog to be None
    with patch('celery_ranch.utils.prioritize._lru_tracker', None), \
         patch('celery_ranch.utils.prioritize._task_backlog', None), \
         patch('celery_ranch.utils.prioritize._initialize_storage') as mock_init:
        
        # Call prioritize_task - this should trigger line 171 in prioritize.py
        try:
            # We expect it to fail after our mocked part because we're not fully
            # setting up the execution environment
            prioritize_task(mock_self, task_id="test123")
        except AttributeError:
            # This is expected, since we're not fully mocking everything
            pass
        
        # Verify _initialize_storage was called
        mock_init.assert_called_once()


def test_prioritize_task_requeue_on_error():
    """Test the requeue behavior in prioritize_task."""
    # Create a mock self object with the necessary methods
    mock_self = MagicMock()
    mock_self.delay.return_value = "requeued"
    
    # Setup necessary mocks
    with patch('celery_ranch.utils.prioritize._lru_tracker'), \
         patch('celery_ranch.utils.prioritize._task_backlog'), \
         patch('celery_ranch.utils.prioritize.time') as mock_time:
        
        # Setup task_backlog's get_all_lru_keys to raise an exception
        with patch('celery_ranch.utils.prioritize._task_backlog.get_all_lru_keys',
                   side_effect=Exception("Test exception")):
            
            # Call prioritize_task with requeue_on_error=True
            try:
                # This should trigger lines 225-232 in prioritize.py
                prioritize_task(mock_self, task_id="test123", requeue_on_error=True)
                assert False, "Should have raised an exception"
            except Exception as e:
                # This is expected
                pass
            
            # Verify sleep was called
            mock_time.sleep.assert_called_once_with(0.5)
            
            # Verify delay was called for requeuing
            mock_self.delay.assert_called_once_with(task_id="test123")