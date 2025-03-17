import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from celery import Task

from ranch.utils.persistence import InMemoryStorage, StorageBackend

logger = logging.getLogger(__name__)


class TaskBacklog:
    """Stores tasks in a backlog for later prioritization and execution.

    Features:
    - Task expiry: Tasks can be set to expire after a certain time
    - Task metadata: Additional information can be stored with tasks
    - Efficient indexing: Tasks are indexed by LRU key for quick retrieval
    """

    def __init__(self, storage: Optional[StorageBackend] = None) -> None:
        """Initialize the task backlog.

        Args:
            storage: Storage backend to use for persistence. If None, uses
            in-memory storage.
        """
        self._storage = storage or InMemoryStorage()
        self._lock = threading.RLock()
        self._task_prefix = "task:"
        self._lru_index_prefix = "lru_index:"
        self._metadata_prefix = "task_meta:"

    def add_task(
        self,
        task: Task,
        lru_key: str,
        args: tuple,
        kwargs: dict,
        expiry: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Add a task to the backlog.

        Args:
            task: The Celery task
            lru_key: The LRU key for prioritization
            args: Task positional arguments
            kwargs: Task keyword arguments
            expiry: Optional expiry time in seconds
            metadata: Optional metadata to store with the task

        Returns:
            The generated task ID
        """
        task_id = str(uuid.uuid4())
        task_data = (task, lru_key, args, kwargs)
        created_at = time.time()

        with self._lock:
            # Store the task data
            self._storage.set(f"{self._task_prefix}{task_id}", task_data, expiry=expiry)

            # Store metadata if provided
            if metadata or expiry:
                task_metadata = {
                    "created_at": created_at,
                    "expires_at": created_at + expiry if expiry else None,
                    "custom": metadata or {},
                }
                self._storage.set(
                    f"{self._metadata_prefix}{task_id}", task_metadata, expiry=expiry
                )

            # Update the LRU index
            lru_index_key = f"{self._lru_index_prefix}{lru_key}"
            lru_tasks = self._storage.get(lru_index_key) or {}
            lru_tasks[task_id] = created_at
            self._storage.set(lru_index_key, lru_tasks)

        return task_id

    def get_task(self, task_id: str) -> Optional[Tuple[Task, str, tuple, dict]]:
        """Get a task from the backlog by its ID.

        Args:
            task_id: The task ID

        Returns:
            A tuple of (task, lru_key, args, kwargs) if found, None otherwise
        """
        with self._lock:
            # Check if task has expired
            metadata = self._storage.get(f"{self._metadata_prefix}{task_id}")
            if metadata and metadata.get("expires_at"):
                if time.time() > metadata["expires_at"]:
                    # Task has expired, remove it
                    self.remove_task(task_id)
                    return None

            return self._storage.get(f"{self._task_prefix}{task_id}")

    def remove_task(self, task_id: str) -> None:
        """Remove a task from the backlog.

        Args:
            task_id: The task ID
        """
        with self._lock:
            # Get the task to find its LRU key
            task_data = self._storage.get(f"{self._task_prefix}{task_id}")
            if task_data:
                _, lru_key, _, _ = task_data

                # Remove from the LRU index
                lru_index_key = f"{self._lru_index_prefix}{lru_key}"
                lru_tasks = self._storage.get(lru_index_key) or {}
                if task_id in lru_tasks:
                    del lru_tasks[task_id]
                    if lru_tasks:
                        self._storage.set(lru_index_key, lru_tasks)
                    else:
                        self._storage.delete(lru_index_key)

                # Remove the task data and metadata
                self._storage.delete(f"{self._task_prefix}{task_id}")
                self._storage.delete(f"{self._metadata_prefix}{task_id}")

    def get_tasks_by_lru_key(
        self, lru_key: str
    ) -> Dict[str, Tuple[Task, str, tuple, dict]]:
        """Get all tasks associated with a given LRU key.

        Args:
            lru_key: The LRU key

        Returns:
            A dictionary mapping task IDs to tasks
        """
        result = {}
        expired_tasks = []

        with self._lock:
            # Get the task IDs from the LRU index
            lru_index_key = f"{self._lru_index_prefix}{lru_key}"
            lru_tasks = self._storage.get(lru_index_key) or {}

            # Get the task data for each task ID
            for task_id in lru_tasks:
                # Check if task has expired
                metadata = self._storage.get(f"{self._metadata_prefix}{task_id}")
                if metadata and metadata.get("expires_at"):
                    if time.time() > metadata["expires_at"]:
                        # Task has expired
                        expired_tasks.append(task_id)
                        continue

                task_data = self._storage.get(f"{self._task_prefix}{task_id}")
                if task_data:
                    result[task_id] = task_data
                else:
                    # Task data missing but in index, mark for cleanup
                    expired_tasks.append(task_id)

            # Clean up expired tasks
            if expired_tasks:
                for task_id in expired_tasks:
                    self.remove_task(task_id)

        return result

    def get_all_lru_keys(self) -> List[str]:
        """Get all unique LRU keys in the backlog.

        Returns:
            A list of unique LRU keys
        """
        with self._lock:
            # Get all keys with the LRU index prefix
            index_keys = self._storage.get_keys_by_prefix(self._lru_index_prefix)

            # Strip the prefix to get the actual LRU keys
            prefix_len = len(self._lru_index_prefix)
            return [key[prefix_len:] for key in index_keys]

    def get_task_metadata(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a task.

        Args:
            task_id: The task ID

        Returns:
            Task metadata or None if not found
        """
        with self._lock:
            return self._storage.get(f"{self._metadata_prefix}{task_id}")

    def get_backlog_stats(self) -> Dict[str, Any]:
        """Get statistics about the backlog.

        Returns:
            Dictionary with backlog statistics
        """
        stats = {
            "total_tasks": 0,
            "total_clients": 0,
            "clients": {},
            "expired_tasks": 0,
        }

        with self._lock:
            # Get all LRU keys
            lru_keys = self.get_all_lru_keys()
            stats["total_clients"] = len(lru_keys)

            # Process each LRU key
            for lru_key in lru_keys:
                # Get tasks for this key
                tasks = self.get_tasks_by_lru_key(lru_key)
                task_count = len(tasks)
                stats["total_tasks"] += task_count

                # Add client info
                stats["clients"][lru_key] = {"task_count": task_count}

            # Get expired tasks count by checking metadata
            now = time.time()
            meta_keys = self._storage.get_keys_by_prefix(self._metadata_prefix)
            for meta_key in meta_keys:
                metadata = self._storage.get(meta_key)
                if (
                    metadata
                    and metadata.get("expires_at")
                    and now > metadata["expires_at"]
                ):
                    stats["expired_tasks"] += 1

        return stats

    def cleanup_expired_tasks(self) -> int:
        """Remove expired tasks from the backlog.

        Returns:
            Number of tasks removed
        """
        removed_count = 0
        now = time.time()
        expired_tasks = []

        with self._lock:
            # Find all expired tasks
            meta_keys = self._storage.get_keys_by_prefix(self._metadata_prefix)
            prefix_len = len(self._metadata_prefix)

            for meta_key in meta_keys:
                metadata = self._storage.get(meta_key)
                if (
                    metadata
                    and metadata.get("expires_at")
                    and now > metadata["expires_at"]
                ):
                    task_id = meta_key[prefix_len:]
                    expired_tasks.append(task_id)

            # Remove expired tasks
            for task_id in expired_tasks:
                self.remove_task(task_id)
                removed_count += 1

        logger.info(f"Cleaned up {removed_count} expired tasks")
        return removed_count
