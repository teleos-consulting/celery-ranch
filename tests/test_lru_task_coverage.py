"""Tests for increasing coverage of the LRUTask class."""

import pytest
from unittest.mock import patch, MagicMock, call

from celery import Celery
from celery_ranch.task import LRUTask, lru_task


def test_lru_task_error_handling():
    """Test the error handling in LRUTask."""
    # Create a mock task instance
    task_mock = MagicMock(spec=LRUTask)
    task_mock._app = MagicMock()
    
    # Test set_priority_weight with exception
    with patch('celery_ranch.utils.prioritize._lru_tracker', MagicMock()) as mock_tracker:
        # Make set_weight raise an exception
        mock_tracker.set_weight.side_effect = ValueError("Test error")
        
        with patch('celery_ranch.task.logger') as mock_logger:
            result = LRUTask.set_priority_weight(task_mock, "client", 1.5)
            # Should return False and log error
            assert result is False
            mock_logger.error.assert_called()
    
    # Test add_tag with exception
    with patch('celery_ranch.utils.prioritize._lru_tracker', MagicMock()) as mock_tracker:
        # Make add_tag raise an exception
        mock_tracker.add_tag.side_effect = ValueError("Test error")
        
        with patch('celery_ranch.task.logger') as mock_logger:
            result = LRUTask.add_tag(task_mock, "client", "tag", "value")
            # Should return False and log error
            assert result is False
            mock_logger.error.assert_called()
    
    # Test set_custom_data with exception
    with patch('celery_ranch.utils.prioritize._lru_tracker', MagicMock()) as mock_tracker:
        # Make set_custom_data raise an exception
        mock_tracker.set_custom_data.side_effect = ValueError("Test error")
        
        with patch('celery_ranch.task.logger') as mock_logger:
            result = LRUTask.set_custom_data(task_mock, "client", "key", "value")
            # Should return False and log error
            assert result is False
            mock_logger.error.assert_called()
    
    # Test get_custom_data with exception
    with patch('celery_ranch.utils.prioritize._lru_tracker', MagicMock()) as mock_tracker:
        # Make get_custom_data raise an exception
        mock_tracker.get_custom_data.side_effect = ValueError("Test error")
        
        with patch('celery_ranch.task.logger') as mock_logger:
            result = LRUTask.get_custom_data(task_mock, "client")
            # Should return empty dict and log error
            assert result == {}
            mock_logger.error.assert_called()


def test_lru_delay_with_invalid_weight():
    """Test lru_delay with invalid weight."""
    app = MagicMock()
    task_mock = MagicMock(spec=LRUTask)
    task_mock._app = app
    
    with patch('celery_ranch.utils.prioritize._lru_tracker') as mock_tracker:
        with patch('celery_ranch.utils.prioritize._task_backlog') as mock_backlog:
            with patch('celery_ranch.task.logger') as mock_logger:
                # Setup mock behaviors
                mock_backlog.add_task.return_value = "task_id"
                
                # Mock the prioritize_task.delay method
                with patch('celery_ranch.utils.prioritize.prioritize_task.delay') as mock_delay:
                    # Make set_weight raise a ValueError
                    mock_tracker.set_weight.side_effect = ValueError("Weight must be positive")
                    
                    # Call lru_delay with invalid weight
                    LRUTask.lru_delay(task_mock, "test_client", 1, 2, priority_weight=-1)
                    
                    # Verify warning was logged
                    mock_logger.warning.assert_called_once()


def test_lru_delay_with_tags():
    """Test lru_delay with tags."""
    app = MagicMock()
    task_mock = MagicMock(spec=LRUTask)
    task_mock._app = app
    
    with patch('celery_ranch.utils.prioritize._lru_tracker') as mock_tracker:
        with patch('celery_ranch.utils.prioritize._task_backlog') as mock_backlog:
            # Setup mock behaviors
            mock_backlog.add_task.return_value = "task_id"
            
            # Mock prioritize_task.delay
            with patch('celery_ranch.utils.prioritize.prioritize_task.delay'):
                # Call lru_delay with tags
                LRUTask.lru_delay(task_mock, "test_client", 1, 2, tags={"tag1": "value1", "tag2": "value2"})
                
                # Verify add_tag was called for each tag
                calls = [call("test_client", "tag1", "value1"), call("test_client", "tag2", "value2")]
                mock_tracker.add_tag.assert_has_calls(calls, any_order=True)


def test_uninitialized_trackers():
    """Test methods with uninitialized trackers."""
    app = MagicMock()
    task_mock = MagicMock(spec=LRUTask)
    task_mock._app = app
    
    # Test set_priority_weight with uninitialized tracker
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.task.configure') as mock_configure:
            LRUTask.set_priority_weight(task_mock, "client", 1.5)
            mock_configure.assert_called_once()
    
    # Test set_priority_weight returns False if tracker still None
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        result = LRUTask.set_priority_weight(task_mock, "client", 1.5)
        assert result is False
    
    # Test add_tag with uninitialized tracker
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.task.configure') as mock_configure:
            LRUTask.add_tag(task_mock, "client", "tag", "value")
            mock_configure.assert_called_once()
    
    # Test add_tag returns False if tracker still None
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        result = LRUTask.add_tag(task_mock, "client", "tag", "value")
        assert result is False
    
    # Test set_custom_data with uninitialized tracker
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.task.configure') as mock_configure:
            LRUTask.set_custom_data(task_mock, "client", "key", "value")
            mock_configure.assert_called_once()
    
    # Test set_custom_data returns False if tracker still None
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        result = LRUTask.set_custom_data(task_mock, "client", "key", "value")
        assert result is False
    
    # Test get_custom_data with uninitialized tracker
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.task.configure') as mock_configure:
            LRUTask.get_custom_data(task_mock, "client")
            mock_configure.assert_called_once()
    
    # Test get_client_metadata with uninitialized trackers
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.utils.prioritize._task_backlog', None):
            with patch('celery_ranch.task.configure') as mock_configure:
                LRUTask.get_client_metadata(task_mock, "client")
                mock_configure.assert_called_once()
    
    # Test get_tagged_clients with uninitialized tracker
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        with patch('celery_ranch.task.configure') as mock_configure:
            LRUTask.get_tagged_clients(task_mock, "tag")
            mock_configure.assert_called_once()
    
    # Test get_tagged_clients returns empty list if tracker still None
    with patch('celery_ranch.utils.prioritize._lru_tracker', None):
        result = LRUTask.get_tagged_clients(task_mock, "tag")
        assert result == []


if __name__ == "__main__":
    test_lru_task_error_handling()
    test_lru_delay_with_invalid_weight()
    test_lru_delay_with_tags()
    test_uninitialized_trackers()