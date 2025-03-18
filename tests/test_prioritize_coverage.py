"""Tests for increasing coverage of the prioritize module."""

import logging
import time
import pytest
from unittest.mock import patch, MagicMock, Mock, call

from celery import Celery
from celery.result import AsyncResult
from celery.app.task import Task

from celery_ranch.utils.prioritize import (
    configure, prioritize_task, _initialize_storage, get_status,
    create_redis_client, _lru_tracker, _task_backlog
)


def test_prioritize_existing_storage():
    """Test _initialize_storage when storage exists."""
    with patch('celery_ranch.utils.prioritize._storage', MagicMock()):
        _initialize_storage()


def test_create_redis_client_no_app():
    """Test create_redis_client with no app."""
    app = Celery()
    app.conf.broker_url = "memory://"
    
    with patch('celery_ranch.utils.prioritize.current_app', app):
        create_redis_client()


def test_configure_in_memory_fallback():
    """Test configure with fallback to in-memory storage."""
    app = MagicMock()
    
    with patch('celery_ranch.utils.prioritize.create_redis_client', return_value=None):
        with patch('celery_ranch.utils.prioritize.InMemoryStorage') as mock_storage:
            with patch('celery_ranch.utils.prioritize.logger') as mock_logger:
                # Call configure with app
                configure(app)
                
                # Verify in-memory storage was used
                mock_storage.assert_called_once()
                # The message in the code is "Configured in-memory storage" not "default"
                mock_logger.info.assert_called_with("Configured in-memory storage")


def test_configure_with_weight_function():
    """Test configure with weight function."""
    app = MagicMock()
    
    def test_weight_fn(key, metadata):
        return 1.0
    
    # Create a fresh LRUTracker mock with set_weight_function available
    tracker_mock = MagicMock()
    
    # First patch the initial storage to prevent _initialize_storage from running
    with patch('celery_ranch.utils.prioritize._storage', MagicMock()):
        # Then patch the LRUTracker constructor to return our mock
        with patch('celery_ranch.utils.prioritize.LRUTracker', return_value=tracker_mock):
            # Configure with weight function
            configure(app, weight_function=test_weight_fn)
            
            # Verify weight function was set on our mock
            tracker_mock.set_weight_function.assert_called_with(test_weight_fn)


def test_prioritize_task_error_handling():
    """Test prioritize_task error handling."""
    with patch('celery_ranch.utils.prioritize._lru_tracker', MagicMock()) as mock_tracker:
        with patch('celery_ranch.utils.prioritize._task_backlog', MagicMock()) as mock_backlog:
            with patch('celery_ranch.utils.prioritize.logger') as mock_logger:
                # Cause get_all_lru_keys to raise exception
                exception_to_raise = ValueError("Test error")
                mock_backlog.get_all_lru_keys.side_effect = exception_to_raise
                
                # The task requires a task_id parameter
                with pytest.raises(ValueError):
                    prioritize_task(task_id="test_task_id")
                
                # Verify error was logged
                mock_logger.error.assert_called()


if __name__ == "__main__":
    test_prioritize_existing_storage()
    test_create_redis_client_no_app()
    test_configure_in_memory_fallback()
    test_configure_with_weight_function()
    test_prioritize_task_error_handling()