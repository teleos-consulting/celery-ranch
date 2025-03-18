import logging
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from celery import Task

from celery_ranch.utils.persistence import InMemoryStorage, StorageBackend

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

                # Remove the task data and metadata using batch delete
                keys_to_delete = [
                    f"{self._task_prefix}{task_id}",
                    f"{self._metadata_prefix}{task_id}",
                ]
                self._storage.batch_delete(keys_to_delete)

    def remove_tasks(self, task_ids: List[str]) -> None:
        """Remove multiple tasks from the backlog efficiently.

        Uses batch operations for better performance.

        Args:
            task_ids: List of task IDs to remove
        """
        if not task_ids:
            return

        with self._lock:
            # Group tasks by LRU key
            task_keys = [f"{self._task_prefix}{task_id}" for task_id in task_ids]
            task_data_dict = self._storage.batch_get(task_keys)

            # Map tasks to their LRU keys
            lru_key_mapping: Dict[str, List[str]] = (
                {}
            )  # Maps LRU keys to lists of task IDs

            for task_id in task_ids:
                task_key = f"{self._task_prefix}{task_id}"
                task_data = task_data_dict.get(task_key)

                if task_data:
                    _, lru_key, _, _ = task_data
                    if lru_key not in lru_key_mapping:
                        lru_key_mapping[lru_key] = []
                    lru_key_mapping[lru_key].append(task_id)

            # Update each LRU index
            for lru_key, ids in lru_key_mapping.items():
                lru_index_key = f"{self._lru_index_prefix}{lru_key}"
                lru_tasks = self._storage.get(lru_index_key) or {}

                # Remove tasks from the index
                for task_id in ids:
                    if task_id in lru_tasks:
                        del lru_tasks[task_id]

                # Update or delete the LRU index
                if lru_tasks:
                    self._storage.set(lru_index_key, lru_tasks)
                else:
                    self._storage.delete(lru_index_key)

            # Batch delete all task data and metadata
            all_task_keys = [f"{self._task_prefix}{task_id}" for task_id in task_ids]
            all_meta_keys = [
                f"{self._metadata_prefix}{task_id}" for task_id in task_ids
            ]

            self._storage.batch_delete(all_task_keys)
            self._storage.batch_delete(all_meta_keys)

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

            if not lru_tasks:
                return {}

            task_ids = list(lru_tasks.keys())
            now = time.time()

            # Batch get all metadata in one operation
            metadata_keys = [
                f"{self._metadata_prefix}{task_id}" for task_id in task_ids
            ]
            metadata_dict = self._storage.batch_get(metadata_keys)

            # Identify non-expired task IDs
            valid_task_ids = []
            for task_id in task_ids:
                metadata_key = f"{self._metadata_prefix}{task_id}"
                metadata = metadata_dict.get(metadata_key)

                # Check if task has expired
                if (
                    metadata
                    and metadata.get("expires_at")
                    and now > metadata["expires_at"]
                ):
                    # Task has expired
                    expired_tasks.append(task_id)
                else:
                    valid_task_ids.append(task_id)

            # Batch get all non-expired task data in one operation
            if valid_task_ids:
                task_keys = [
                    f"{self._task_prefix}{task_id}" for task_id in valid_task_ids
                ]
                task_data_dict = self._storage.batch_get(task_keys)

                # Process task data
                for task_id, task_key in zip(valid_task_ids, task_keys):
                    task_data = task_data_dict.get(task_key)
                    if task_data:
                        result[task_id] = task_data
                    else:
                        # Task data missing but in index, mark for cleanup
                        task_id_short = task_id[:8]  # Use shorter ID in logs
                        logger.info(
                            f"Task {task_id_short}... for {lru_key} missing data, "
                            f"marking for cleanup"
                        )
                        expired_tasks.append(task_id)

            # Clean up expired tasks in batch if any
            if expired_tasks:
                # First update the LRU index
                updated_lru_tasks = {
                    k: v for k, v in lru_tasks.items() if k not in expired_tasks
                }

                if updated_lru_tasks:
                    self._storage.set(lru_index_key, updated_lru_tasks)
                else:
                    self._storage.delete(lru_index_key)

                # Batch delete expired task data and metadata
                task_keys = [
                    f"{self._task_prefix}{task_id}" for task_id in expired_tasks
                ]
                meta_keys = [
                    f"{self._metadata_prefix}{task_id}" for task_id in expired_tasks
                ]

                self._storage.batch_delete(task_keys)
                self._storage.batch_delete(meta_keys)

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

        Uses batch operations for improved performance.

        Returns:
            Dictionary with backlog statistics
        """
        stats: Dict[str, Any] = {
            "total_tasks": 0,
            "total_clients": 0,
            "clients": {},
            "expired_tasks": 0,
        }

        with self._lock:
            # Get all LRU keys
            lru_keys = self.get_all_lru_keys()
            stats["total_clients"] = len(lru_keys)

            # Batch get all LRU indices
            lru_index_keys = [
                f"{self._lru_index_prefix}{lru_key}" for lru_key in lru_keys
            ]
            lru_indices_dict = self._storage.batch_get(lru_index_keys)

            # Calculate task counts by client
            client_task_counts = {}
            for i, lru_key in enumerate(lru_keys):
                lru_index_key = lru_index_keys[i]
                lru_tasks = lru_indices_dict.get(lru_index_key) or {}
                task_count = len(lru_tasks)

                client_task_counts[lru_key] = task_count
                stats["total_tasks"] += task_count
                stats["clients"][lru_key] = {"task_count": task_count}

            # Get expired tasks count efficiently using batch operations
            now = time.time()
            meta_keys = self._storage.get_keys_by_prefix(self._metadata_prefix)

            if meta_keys:
                # Batch get all metadata
                metadata_dict = self._storage.batch_get(meta_keys)

                # Count expired tasks
                for meta_key in meta_keys:
                    metadata = metadata_dict.get(meta_key)
                    if (
                        metadata
                        and isinstance(metadata, dict)
                        and "expires_at" in metadata
                        and metadata["expires_at"] is not None
                        and now > metadata["expires_at"]
                    ):
                        stats["expired_tasks"] += 1

        return stats

    def cleanup_expired_tasks(self) -> int:
        """Remove expired tasks from the backlog.

        Uses batch operations for improved performance.

        Returns:
            Number of tasks removed
        """
        removed_count = 0
        now = time.time()
        expired_tasks = []
        client_task_mapping: Dict[str, List[str]] = (
            {}
        )  # Maps lru_keys to lists of task_ids

        with self._lock:
            # Find all expired tasks
            meta_keys = self._storage.get_keys_by_prefix(self._metadata_prefix)

            if not meta_keys:
                return 0

            # Batch get all metadata
            metadata_dict = self._storage.batch_get(meta_keys)
            prefix_len = len(self._metadata_prefix)

            # Identify expired tasks
            for meta_key in meta_keys:
                metadata = metadata_dict.get(meta_key)
                if (
                    metadata
                    and metadata.get("expires_at")
                    and now > metadata["expires_at"]
                ):
                    task_id = meta_key[prefix_len:]
                    expired_tasks.append(task_id)

            if not expired_tasks:
                return 0

            removed_count = len(expired_tasks)

            # Group tasks by client for efficient LRU index updates
            task_keys = [f"{self._task_prefix}{task_id}" for task_id in expired_tasks]
            task_data_dict = self._storage.batch_get(task_keys)

            for task_id, task_key in zip(expired_tasks, task_keys):
                task_data = task_data_dict.get(task_key)
                if task_data:
                    _, lru_key, _, _ = task_data
                    if lru_key not in client_task_mapping:
                        client_task_mapping[lru_key] = []
                    client_task_mapping[lru_key].append(task_id)

            # Update LRU indices efficiently by client
            for lru_key, client_tasks in client_task_mapping.items():
                lru_index_key = f"{self._lru_index_prefix}{lru_key}"
                lru_tasks = self._storage.get(lru_index_key) or {}

                # Remove expired tasks from the LRU index
                updated_lru_tasks = {
                    k: v for k, v in lru_tasks.items() if k not in client_tasks
                }

                if updated_lru_tasks:
                    self._storage.set(lru_index_key, updated_lru_tasks)
                else:
                    self._storage.delete(lru_index_key)

            # Batch delete task data and metadata
            task_keys = [f"{self._task_prefix}{task_id}" for task_id in expired_tasks]
            meta_keys = [
                f"{self._metadata_prefix}{task_id}" for task_id in expired_tasks
            ]

            self._storage.batch_delete(task_keys)
            self._storage.batch_delete(meta_keys)

        logger.info(f"Cleaned up {removed_count} expired tasks using batch operations")
        return removed_count
