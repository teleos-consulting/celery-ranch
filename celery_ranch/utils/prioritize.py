import logging
import threading
import time
from typing import Any, Callable, Dict, Optional

from celery import current_app, shared_task

from celery_ranch.utils.backlog import TaskBacklog
from celery_ranch.utils.lru_tracker import LRUKeyMetadata, LRUTracker
from celery_ranch.utils.persistence import (
    InMemoryStorage,
    RedisStorage,
    SerializerType,
    StorageBackend,
)

logger = logging.getLogger(__name__)

# Global lock for initialization
_init_lock = threading.RLock()

# Global instances used by the prioritization task
_lru_tracker = None
_task_backlog = None
_storage = None

# Default configuration
_DEFAULT_CONFIG = {
    "redis_prefix": "ranch:",
    "redis_serializer": SerializerType.PICKLE,
    "redis_max_retries": 3,
    "redis_key_ttl": None,  # No expiration by default
    "redis_use_ssl": False,
    "metrics_enabled": False,
}


def create_redis_client(app=None):
    """Create a Redis client from Celery app configuration.

    Args:
        app: Celery application instance

    Returns:
        Redis client instance or None if configuration is invalid
    """
    try:
        import redis
        from redis.exceptions import ConnectionError

        if app is None:
            app = current_app

        # Get Redis configuration from Celery app
        broker_url = app.conf.get("broker_url", "")

        # Check if we're using Redis as broker
        is_redis = broker_url.startswith("redis://") or broker_url.startswith(
            "rediss://"
        )

        if not is_redis:
            return None

        # Parse additional Redis configuration from Celery app
        ranch_config = app.conf.get("ranch", {})
        redis_ssl = ranch_config.get("redis_use_ssl", _DEFAULT_CONFIG["redis_use_ssl"])
        redis_socket_timeout = ranch_config.get("redis_socket_timeout", 5)
        redis_socket_connect_timeout = ranch_config.get(
            "redis_socket_connect_timeout", 3
        )

        # Create connection pool and client
        pool_kwargs = {
            "socket_timeout": redis_socket_timeout,
            "socket_connect_timeout": redis_socket_connect_timeout,
            "health_check_interval": 30,
            "retry_on_timeout": True,
        }

        # If using SSL but URL doesn't specify it, modify URL
        if redis_ssl and broker_url.startswith("redis://"):
            broker_url = broker_url.replace("redis://", "rediss://", 1)

        # Create Redis client from URL
        redis_client = redis.from_url(broker_url, **pool_kwargs)

        # Test connection
        redis_client.ping()

        return redis_client

    except ImportError:
        logger.warning("Redis package not found, falling back to in-memory storage")
        return None
    except (ConnectionError, Exception) as e:
        logger.warning(
            f"Failed to connect to Redis: {e}, falling back to in-memory storage"
        )
        return None


def _initialize_storage():
    """Initialize the storage backend based on Celery configuration."""
    global _lru_tracker, _task_backlog, _storage

    with _init_lock:
        if _storage is not None:
            return

        # Use Redis if available in Celery's configuration
        try:
            redis_client = create_redis_client()

            if redis_client:
                # Get Redis configuration from Celery app
                ranch_config = current_app.conf.get("ranch", {})
                redis_prefix = ranch_config.get(
                    "redis_prefix", _DEFAULT_CONFIG["redis_prefix"]
                )
                redis_serializer = ranch_config.get(
                    "redis_serializer", _DEFAULT_CONFIG["redis_serializer"]
                )
                redis_max_retries = ranch_config.get(
                    "redis_max_retries", _DEFAULT_CONFIG["redis_max_retries"]
                )
                redis_key_ttl = ranch_config.get(
                    "redis_key_ttl", _DEFAULT_CONFIG["redis_key_ttl"]
                )

                # Create Redis storage
                _storage = RedisStorage(
                    redis_client=redis_client,
                    prefix=redis_prefix,
                    serializer=redis_serializer,
                    max_retries=redis_max_retries,
                    key_ttl=redis_key_ttl,
                )

                logger.info(f"Initialized Redis storage with prefix {redis_prefix}")
            else:
                # Fall back to in-memory storage
                _storage = InMemoryStorage()
                logger.info("Initialized in-memory storage")
        except Exception as e:
            # Fall back to in-memory storage
            _storage = InMemoryStorage()
            logger.warning(
                f"Error initializing Redis storage, falling back to in-memory: {e}"
            )

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
    start_time = time.time()

    # Initialize storage if not already done
    if _lru_tracker is None or _task_backlog is None:
        _initialize_storage()

    try:
        # Get all unique LRU keys in the backlog
        lru_keys = _task_backlog.get_all_lru_keys()

        if not lru_keys:
            return None

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

        # Log processing metrics
        processing_time = time.time() - start_time
        logger.debug(
            f"Prioritized task {selected_task_id} for client {oldest_key} "
            f"from {len(tasks_by_id)} available tasks in {processing_time:.3f}s"
        )

        return result

    except Exception as e:
        logger.error(f"Error in prioritize_task: {e}")
        # Requeue the original task ID if there was an error
        # This helps prevent tasks from being lost due to errors
        if _task_backlog and task_id:
            task_data = _task_backlog.get_task(task_id)
            if task_data:
                task, lru_key, args, kwargs = task_data
                logger.info(
                    f"Requeuing task {task_id} for client {lru_key} due to error"
                )
                # Brief delay to prevent rapid retries for persistent errors
                time.sleep(0.5)
                return prioritize_task.delay(task_id=task_id)
        raise


def _update_app_config(app, config: Dict[str, Any]) -> None:
    """Update the Celery app configuration with Ranch settings.

    Args:
        app: Celery application instance
        config: Configuration dictionary to update Celery app config
    """
    # Ensure ranch configuration exists
    if not hasattr(app.conf, "ranch"):
        app.conf.ranch = {}

    # Update ranch configuration
    for key, value in config.items():
        app.conf.ranch[key] = value


def _update_redis_config(app, config: Dict[str, Any]) -> None:
    """Update Redis-specific configuration in the Celery app.

    Args:
        app: Celery application instance
        config: Configuration dictionary containing Redis settings
    """
    # Set Redis configuration in app for later use
    for key, value in config.items():
        if key.startswith("redis_"):
            if not hasattr(app.conf, "ranch"):
                app.conf.ranch = {}
            app.conf.ranch[key] = value


def _setup_redis_storage(app) -> StorageBackend:
    """Set up Redis storage from app configuration.

    Args:
        app: Celery application instance

    Returns:
        Configured storage backend (Redis or in-memory)
    """
    # Create and configure Redis client if applicable
    redis_client = create_redis_client(app)

    if not redis_client:
        logger.info("Configured in-memory storage")
        return InMemoryStorage()

    # Get Redis configuration
    ranch_config = getattr(app.conf, "ranch", {})
    redis_prefix = ranch_config.get("redis_prefix", _DEFAULT_CONFIG["redis_prefix"])
    redis_serializer = ranch_config.get(
        "redis_serializer", _DEFAULT_CONFIG["redis_serializer"]
    )
    redis_max_retries = ranch_config.get(
        "redis_max_retries", _DEFAULT_CONFIG["redis_max_retries"]
    )
    redis_key_ttl = ranch_config.get("redis_key_ttl", _DEFAULT_CONFIG["redis_key_ttl"])

    # Create Redis storage
    storage = RedisStorage(
        redis_client=redis_client,
        prefix=redis_prefix,
        serializer=redis_serializer,
        max_retries=redis_max_retries,
        key_ttl=redis_key_ttl,
    )

    logger.info(f"Configured Redis storage with prefix {redis_prefix}")
    return storage


def configure(
    app=None,
    storage: Optional[StorageBackend] = None,
    config: Optional[Dict[str, Any]] = None,
    weight_function: Optional[Callable[[str, LRUKeyMetadata], float]] = None,
) -> None:
    """Configure the LRU priority system with custom settings.

    Args:
        app: Optional Celery application instance
        storage: Optional custom storage backend
        config: Optional configuration dictionary to update Celery app config
        weight_function: Optional custom function for calculating dynamic weights
                      Should take (lru_key, metadata) and return a float
    """
    global _lru_tracker, _task_backlog, _storage

    with _init_lock:
        # Configure Ranch settings in Celery app if provided
        if app is not None and config is not None:
            _update_app_config(app, config)

        # Determine which storage to use
        if storage is not None:
            _storage = storage
        elif app is not None:
            # Update Redis config if provided
            if config is not None:
                _update_redis_config(app, config)
            # Set up storage based on app configuration
            _storage = _setup_redis_storage(app)
        else:
            _storage = InMemoryStorage()
            logger.info("Configured default in-memory storage")

        # Initialize trackers with the storage
        _lru_tracker = LRUTracker(storage=_storage)
        _task_backlog = TaskBacklog(storage=_storage)

        # Set custom weight function if provided
        if weight_function is not None and _lru_tracker is not None:
            _lru_tracker.set_weight_function(weight_function)
            name = weight_function.__name__ if weight_function else "None"
            logger.info(f"Configured custom weight function: {name}")


def get_status() -> Dict[str, Any]:
    """Get the current status of the LRU priority system.

    Returns:
        A dictionary with status information
    """
    status = {
        "initialized": False,
        "storage_type": "none",
        "backlog_size": 0,
        "unique_lru_keys": 0,
        "health": False,
    }

    if _storage is None:
        return status

    status["initialized"] = True
    status["storage_type"] = _storage.__class__.__name__

    try:
        if _task_backlog:
            lru_keys = _task_backlog.get_all_lru_keys()
            status["unique_lru_keys"] = len(lru_keys)

            # Count total backlog size
            backlog_size = 0
            for key in lru_keys:
                tasks = _task_backlog.get_tasks_by_lru_key(key)
                backlog_size += len(tasks)

            status["backlog_size"] = backlog_size

        # Check storage health if it's Redis
        if isinstance(_storage, RedisStorage):
            status["health"] = _storage.health_check()
        else:
            status["health"] = True

    except Exception as e:
        logger.error(f"Error getting status: {e}")

    return status
