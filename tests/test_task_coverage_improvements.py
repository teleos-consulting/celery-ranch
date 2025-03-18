"""Additional tests for improving coverage in the task module."""

from unittest.mock import MagicMock, patch

import pytest

from celery_ranch.task import LRUTask, configure
from celery_ranch.utils.prioritize import _lru_tracker, _task_backlog


def test_lru_task_initialization():
    """Test LRUTask initialization specifically for the conditional configure call."""
    # Create a mock app
    mock_app = MagicMock()
    
    # Patch the prioritize module's _lru_tracker and _task_backlog to be None
    with patch('celery_ranch.task._lru_tracker', None), \
         patch('celery_ranch.task._task_backlog', None), \
         patch('celery_ranch.task.configure') as mock_configure:
        
        # Create a mock LRUTask
        with patch.object(LRUTask, '__init__', return_value=None):
            task = LRUTask()
            task._app = mock_app
            
            # Call the method that should trigger the configure line
            # We're specifically setting up a situation where line 48 in task.py will be executed
            task.lru_delay(lru_key="test")
            
            # Verify configure was called with the app
            mock_configure.assert_called_once_with(app=mock_app)