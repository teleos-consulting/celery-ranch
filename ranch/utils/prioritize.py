from typing import Any
import threading

from celery import shared_task, current_app

from ranch.utils.lru_tracker import LRUTracker
from ranch.utils.backlog import TaskBacklog
from ranch.utils.persistence import InMemoryStorage, RedisStorage

# Global lock for initialization
_init_lock = threading.RLock()

# Global instances used by the prioritization task
_lru_tracker = None
_task_backlog = None
_storage = None


def _initialize_storage():
    """Initialize the storage backend based on Celery configuration."""
    global _lru_tracker, _task_backlog, _storage

    with _init_lock:
        if _storage is not None:
            return

        # Use Redis if available in Celery's configuration
        try:
            redis_url = current_app.conf.get("broker_url")
            if redis_url and redis_url.startswith("redis://"):
                import redis

                redis_client = redis.from_url(redis_url)
                _storage = RedisStorage(redis_client)
            else:
                _storage = InMemoryStorage()
        except (ImportError, Exception):
            # Fall back to in-memory storage
            _storage = InMemoryStorage()

        # Initialize trackers with the storage
        _lru_tracker = LRUTracker(storage=_storage)
        _task_backlog = TaskBacklog(storage=_storage)


@shared_task(name="ranch.prioritize_task", bind=True)
def prioritize_task(self, task_id: str) -> Any:
    """Prioritization task that selects and executes the highest priority task.

    Args:
        task_id: The ID of the task that triggered prioritization

    Returns:
        The result of the executed task
    """
    # Initialize storage if not already done
    if _lru_tracker is None or _task_backlog is None:
        _initialize_storage()

    # Get all unique LRU keys in the backlog
    lru_keys = _task_backlog.get_all_lru_keys()

    # Get the least recently used key
    oldest_key = _lru_tracker.get_oldest_key(lru_keys)

    if not oldest_key:
        return None

    # Get all tasks for the selected LRU key
    tasks_by_id = _task_backlog.get_tasks_by_lru_key(oldest_key)

    # If no tasks found, return None
    if not tasks_by_id:
        return None

    # Pick the first task (could implement additional prioritization here)
    selected_task_id = next(iter(tasks_by_id))
    task_data = _task_backlog.get_task(selected_task_id)

    if not task_data:
        return None

    # Remove the task from the backlog
    _task_backlog.remove_task(selected_task_id)

    # Update the LRU timestamp for this key
    _lru_tracker.update_timestamp(oldest_key)

    # Execute the selected task
    task, _, args, kwargs = task_data
    result = task.apply_async(args=args, kwargs=kwargs)

    return result


def configure(app=None, storage=None):
    """Configure the LRU priority system with custom settings.

    Args:
        app: Optional Celery application instance
        storage: Optional custom storage backend
    """
    global _lru_tracker, _task_backlog, _storage

    with _init_lock:
        if storage is not None:
            _storage = storage
        elif app is not None:
            # Use Redis if available in the provided app's configuration
            try:
                redis_url = app.conf.get("broker_url")
                if redis_url and redis_url.startswith("redis://"):
                    import redis

                    redis_client = redis.from_url(redis_url)
                    _storage = RedisStorage(redis_client)
                else:
                    _storage = InMemoryStorage()
            except (ImportError, Exception):
                # Fall back to in-memory storage
                _storage = InMemoryStorage()
        else:
            _storage = InMemoryStorage()

        # Initialize trackers with the storage
        _lru_tracker = LRUTracker(storage=_storage)
        _task_backlog = TaskBacklog(storage=_storage)
