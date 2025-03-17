from typing import Any, Callable, TypeVar, cast

from celery import Celery, Task

from ranch.utils.prioritize import prioritize_task, configure

F = TypeVar("F", bound=Callable[..., Any])


class LRUTask(Task):
    """Task subclass that adds LRU prioritization functionality."""

    _app: Celery

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

    def lru_delay(self, lru_key: str, *args: Any, **kwargs: Any) -> Any:
        """Schedules task execution with LRU prioritization.

        Args:
            lru_key: The LRU key used to determine task priority
            *args: Task positional arguments
            **kwargs: Task keyword arguments

        Returns:
            The AsyncResult object for the task
        """
        from ranch.utils.prioritize import _task_backlog, _lru_tracker

        # Make sure the storage is initialized
        if _task_backlog is None or _lru_tracker is None:
            configure(app=self._app)

        # Store the task in the backlog
        task_id = _task_backlog.add_task(
            task=self, lru_key=lru_key, args=args, kwargs=kwargs
        )

        # Schedule the prioritization task
        return prioritize_task.delay(task_id=task_id)


def lru_task(app: Celery, **options: Any) -> Callable[[F], F]:
    """Decorator to create an LRU-aware task.

    Args:
        app: The Celery application instance
        **options: Additional options to pass to the task decorator

    Returns:
        A decorator function that creates an LRU-aware task
    """
    # Initialize the LRU priority system with the app
    configure(app=app)

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
