import logging
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast

from celery import Celery, Task

from celery_ranch.utils.lru_tracker import LRUKeyMetadata
from celery_ranch.utils.prioritize import configure, get_status, prioritize_task

F = TypeVar("F", bound=Callable[..., Any])
logger = logging.getLogger(__name__)


class LRUTask(Task):
    """Task subclass that adds LRU prioritization functionality with
    weighted fairness."""

    _app: Celery

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def lru_delay(
        self,
        lru_key: str,
        *args: Any,
        priority_weight: Optional[float] = None,
        tags: Optional[Dict[str, str]] = None,
        expiry: Optional[int] = None,
        **kwargs: Any,
    ) -> Any:
        """Schedules task execution with LRU prioritization.

        Args:
            lru_key: The LRU key used to determine task priority
            *args: Task positional arguments
            priority_weight: Optional priority weight (lower value = higher priority)
            tags: Optional metadata tags for the LRU key
            expiry: Optional expiry time in seconds for this task
            **kwargs: Task keyword arguments

        Returns:
            The AsyncResult object for the task
        """
        from celery_ranch.utils.prioritize import _lru_tracker, _task_backlog

        # Make sure the storage is initialized
        if _task_backlog is None or _lru_tracker is None:
            configure(app=self._app)

        # Update weight if provided
        if priority_weight is not None and _lru_tracker is not None:
            try:
                _lru_tracker.set_weight(lru_key, priority_weight)
            except ValueError as e:
                logger.warning(f"Invalid priority weight for {lru_key}: {e}")

        # Add tags if provided
        if tags and _lru_tracker is not None:
            for tag_name, tag_value in tags.items():
                _lru_tracker.add_tag(lru_key, tag_name, tag_value)

        # Store the task in the backlog
        task_id = _task_backlog.add_task(
            task=self, lru_key=lru_key, args=args, kwargs=kwargs, expiry=expiry
        )

        # Schedule the prioritization task
        return prioritize_task.delay(task_id=task_id)

    def set_priority_weight(self, lru_key: str, weight: float) -> bool:
        """Set the priority weight for a given LRU key.

        Lower weight values result in higher priority (shorter waits).
        Higher weight values result in lower priority (longer waits).

        Args:
            lru_key: The LRU key to update
            weight: The priority weight (must be positive)

        Returns:
            True if successful, False otherwise
        """
        from celery_ranch.utils.prioritize import _lru_tracker

        if _lru_tracker is None:
            configure(app=self._app)

        if _lru_tracker is not None:
            try:
                _lru_tracker.set_weight(lru_key, weight)
                return True
            except Exception as e:
                logger.error(f"Error setting priority weight: {e}")
                return False
        return False

    def add_tag(self, lru_key: str, tag_name: str, tag_value: str) -> bool:
        """Add a tag to an LRU key.

        Tags can be used for grouping or categorizing keys.

        Args:
            lru_key: The LRU key to tag
            tag_name: The tag name
            tag_value: The tag value

        Returns:
            True if successful, False otherwise
        """
        from celery_ranch.utils.prioritize import _lru_tracker

        if _lru_tracker is None:
            configure(app=self._app)

        if _lru_tracker is not None:
            try:
                _lru_tracker.add_tag(lru_key, tag_name, tag_value)
                return True
            except Exception as e:
                logger.error(f"Error adding tag: {e}")
                return False
        return False

    def set_custom_data(self, lru_key: str, key: str, value: Any) -> bool:
        """Set custom data for an LRU key.

        Custom data can be used by dynamic weight functions to determine priority.

        Args:
            lru_key: The LRU key to update
            key: The custom data key
            value: The custom data value

        Returns:
            True if successful, False otherwise
        """
        from celery_ranch.utils.prioritize import _lru_tracker

        if _lru_tracker is None:
            configure(app=self._app)

        if _lru_tracker is not None:
            try:
                _lru_tracker.set_custom_data(lru_key, key, value)
                return True
            except Exception as e:
                logger.error(f"Error setting custom data: {e}")
                return False
        return False

    def get_custom_data(self, lru_key: str) -> Dict[str, Any]:
        """Get custom data for an LRU key.

        Args:
            lru_key: The LRU key

        Returns:
            Dictionary of custom data (empty dict if none exists)
        """
        from celery_ranch.utils.prioritize import _lru_tracker

        if _lru_tracker is None:
            configure(app=self._app)

        if _lru_tracker is not None:
            try:
                return _lru_tracker.get_custom_data(lru_key) or {}
            except Exception as e:
                logger.error(f"Error getting custom data: {e}")
        return {}

    def get_client_metadata(self, lru_key: str) -> Dict[str, Any]:
        """Get metadata for an LRU client.

        Args:
            lru_key: The LRU key

        Returns:
            Dictionary with client metadata
        """
        from celery_ranch.utils.prioritize import _lru_tracker, _task_backlog

        if _lru_tracker is None or _task_backlog is None:
            configure(app=self._app)

        result = {
            "lru_key": lru_key,
            "weight": 1.0,
            "last_execution": None,
            "tags": None,
            "custom_data": None,
            "pending_tasks": 0,
        }

        if _lru_tracker is not None:
            metadata = _lru_tracker.get_metadata(lru_key)
            if metadata:
                result["weight"] = metadata.weight
                result["last_execution"] = metadata.timestamp
                result["tags"] = metadata.tags
                result["custom_data"] = metadata.custom_data

        if _task_backlog is not None:
            tasks = _task_backlog.get_tasks_by_lru_key(lru_key)
            result["pending_tasks"] = len(tasks)

        return result

    def get_tagged_clients(
        self, tag_name: str, tag_value: Optional[str] = None
    ) -> List[str]:
        """Get all client keys with a specific tag.

        Args:
            tag_name: The tag name to search for
            tag_value: Optional specific value to match

        Returns:
            List of client keys with the specified tag
        """
        from celery_ranch.utils.prioritize import _lru_tracker

        if _lru_tracker is None:
            configure(app=self._app)

        if _lru_tracker is not None:
            return _lru_tracker.get_keys_by_tag(tag_name, tag_value)
        return []

    def get_system_status(self) -> Dict[str, Any]:
        """Get the current status of the LRU priority system.

        Returns:
            A dictionary with status information
        """
        return get_status()


def lru_task(
    app: Celery,
    config: Optional[Dict[str, Any]] = None,
    weight_function: Optional[Callable[[str, LRUKeyMetadata], float]] = None,
    **options: Any,
) -> Callable[[F], F]:
    """Decorator to create an LRU-aware task.

    Args:
        app: The Celery application instance
        config: Optional configuration dictionary for Celery Ranch
        weight_function: Optional function for calculating dynamic priority weights
                       Should take (lru_key, metadata) and return a float
        **options: Additional options to pass to the task decorator

    Returns:
        A decorator function that creates an LRU-aware task
    """
    # Initialize the LRU priority system with the app
    configure(app=app, config=config, weight_function=weight_function)

    def decorator(func: F) -> F:
        task_options = options.copy()
        base = task_options.pop("base", LRUTask)

        # Create the task
        task = app.task(base=base, **task_options)(func)

        # Attach the Celery app to the task
        if isinstance(task, LRUTask):
            task._app = app

        return cast(F, task)

    return decorator
