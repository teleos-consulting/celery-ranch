import pytest
from unittest.mock import patch, MagicMock
import time

from celery import Celery
from celery.result import AsyncResult

from celery_lru_priority import lru_task
from celery_lru_priority.utils.lru_tracker import LRUTracker
from celery_lru_priority.utils.backlog import TaskBacklog
from celery_lru_priority.utils.prioritize import prioritize_task


@pytest.fixture
def celery_app():
    app = Celery('tests')
    app.conf.update(
        task_always_eager=True,
        broker_url='memory://',
        result_backend='rpc://'
    )
    return app


def test_lru_task_decorator(celery_app):
    """Test that the lru_task decorator creates a task with lru_delay method."""
    
    @lru_task(celery_app)
    def test_task(arg1, arg2=None):
        return arg1, arg2
    
    # Check that the task has the lru_delay method
    assert hasattr(test_task, 'lru_delay')
    assert callable(test_task.lru_delay)


@patch('celery_lru_priority.utils.prioritize.prioritize_task.delay')
def test_lru_delay_method(mock_prioritize_delay, celery_app):
    """Test that lru_delay stores the task in the backlog and triggers prioritization."""
    
    @lru_task(celery_app)
    def test_task(arg1, arg2=None):
        return arg1, arg2
    
    # Mock the AsyncResult object
    mock_result = MagicMock(spec=AsyncResult)
    mock_prioritize_delay.return_value = mock_result
    
    # Call lru_delay
    result = test_task.lru_delay('client1', 'arg1_value', arg2='arg2_value')
    
    # Check that prioritize_task.delay was called
    assert mock_prioritize_delay.called
    
    # Check that the result is the AsyncResult from prioritize_task.delay
    assert result == mock_result


def test_lru_tracker():
    """Test the LRU tracking functionality."""
    tracker = LRUTracker()
    
    # Test initial state
    assert tracker.get_timestamp('key1') is None
    
    # Test update_timestamp
    tracker.update_timestamp('key1')
    assert tracker.get_timestamp('key1') is not None
    
    # Test get_oldest_key with single key
    assert tracker.get_oldest_key(['key1']) == 'key1'
    
    # Test get_oldest_key with multiple keys
    tracker.update_timestamp('key2')
    time.sleep(0.01)  # Ensure timestamps are different
    tracker.update_timestamp('key3')
    
    assert tracker.get_oldest_key(['key1', 'key2', 'key3']) == 'key1'
    assert tracker.get_oldest_key(['key2', 'key3']) == 'key2'


def test_task_backlog():
    """Test the task backlog functionality."""
    backlog = TaskBacklog()
    
    # Mock a task
    task = MagicMock()
    
    # Test add_task
    task_id = backlog.add_task(task, 'client1', ('arg1',), {'kwarg1': 'value1'})
    assert task_id is not None
    
    # Test get_task
    stored_task = backlog.get_task(task_id)
    assert stored_task is not None
    assert stored_task[0] == task
    assert stored_task[1] == 'client1'
    assert stored_task[2] == ('arg1',)
    assert stored_task[3] == {'kwarg1': 'value1'}
    
    # Test get_tasks_by_lru_key
    tasks_by_key = backlog.get_tasks_by_lru_key('client1')
    assert task_id in tasks_by_key
    assert task_id not in backlog.get_tasks_by_lru_key('nonexistent')
    
    # Test get_all_lru_keys
    assert 'client1' in backlog.get_all_lru_keys()
    
    # Test remove_task
    backlog.remove_task(task_id)
    assert backlog.get_task(task_id) is None
    assert not backlog.get_tasks_by_lru_key('client1')


@patch('celery_lru_priority.utils.prioritize._task_backlog')
@patch('celery_lru_priority.utils.prioritize._lru_tracker')
def test_prioritize_task(mock_lru_tracker, mock_task_backlog):
    """Test the prioritization task."""
    # Mock task backlog
    mock_task = MagicMock()
    mock_task_args = ('arg1',)
    mock_task_kwargs = {'kwarg1': 'value1'}
    mock_task_result = MagicMock()
    mock_task.apply_async.return_value = mock_task_result
    
    mock_task_backlog.get_all_lru_keys.return_value = ['client1', 'client2']
    mock_lru_tracker.get_oldest_key.return_value = 'client1'
    
    mock_task_data = {
        'task_id1': (mock_task, 'client1', mock_task_args, mock_task_kwargs)
    }
    mock_task_backlog.get_tasks_by_lru_key.return_value = mock_task_data
    mock_task_backlog.get_task.return_value = (mock_task, 'client1', mock_task_args, mock_task_kwargs)
    
    # Call prioritize_task
    result = prioritize_task('task_id1')
    
    # Verify the result
    assert result == mock_task_result
    
    # Verify method calls
    mock_task_backlog.get_all_lru_keys.assert_called_once()
    mock_lru_tracker.get_oldest_key.assert_called_once_with(['client1', 'client2'])
    mock_task_backlog.get_tasks_by_lru_key.assert_called_once_with('client1')
    mock_task_backlog.get_task.assert_called_once()
    mock_task_backlog.remove_task.assert_called_once()
    mock_lru_tracker.update_timestamp.assert_called_once_with('client1')
    mock_task.apply_async.assert_called_once_with(args=mock_task_args, kwargs=mock_task_kwargs)