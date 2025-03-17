import uuid
import pickle
from typing import Any, Dict, Optional, Tuple, List
import threading

from celery import Task
from celery_lru_priority.utils.persistence import InMemoryStorage


class TaskBacklog:
    """Stores tasks in a backlog for later prioritization and execution."""
    
    def __init__(self, storage=None) -> None:
        self._storage = storage or InMemoryStorage()
        self._lock = threading.RLock()
        self._task_prefix = "task:"
        self._lru_index_prefix = "lru_index:"
        
    def add_task(self, task: Task, lru_key: str, args: tuple, kwargs: dict) -> str:
        """Add a task to the backlog.
        
        Args:
            task: The Celery task
            lru_key: The LRU key for prioritization
            args: Task positional arguments
            kwargs: Task keyword arguments
            
        Returns:
            The generated task ID
        """
        task_id = str(uuid.uuid4())
        task_data = (task, lru_key, args, kwargs)
        
        with self._lock:
            # Store the task data
            self._storage.set(f"{self._task_prefix}{task_id}", task_data)
            
            # Update the LRU index
            lru_index_key = f"{self._lru_index_prefix}{lru_key}"
            lru_tasks = self._storage.get(lru_index_key) or {}
            lru_tasks[task_id] = True
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
                
                # Remove the task data
                self._storage.delete(f"{self._task_prefix}{task_id}")
    
    def get_tasks_by_lru_key(self, lru_key: str) -> Dict[str, Tuple[Task, str, tuple, dict]]:
        """Get all tasks associated with a given LRU key.
        
        Args:
            lru_key: The LRU key
            
        Returns:
            A dictionary mapping task IDs to tasks
        """
        result = {}
        
        with self._lock:
            # Get the task IDs from the LRU index
            lru_index_key = f"{self._lru_index_prefix}{lru_key}"
            lru_tasks = self._storage.get(lru_index_key) or {}
            
            # Get the task data for each task ID
            for task_id in lru_tasks:
                task_data = self._storage.get(f"{self._task_prefix}{task_id}")
                if task_data:
                    result[task_id] = task_data
                    
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
