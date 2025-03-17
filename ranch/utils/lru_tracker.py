from typing import Dict, Optional, List
import time
import threading

from ranch.utils.persistence import InMemoryStorage


class LRUTracker:
    """Tracks the least recently used status of task keys."""
    
    def __init__(self, storage=None) -> None:
        # Use the provided storage or create an in-memory one
        self._storage = storage or InMemoryStorage()
        self._lock = threading.RLock()
        self._key_prefix = "lru:"
    
    def update_timestamp(self, lru_key: str) -> None:
        """Update the last access timestamp for a given LRU key."""
        with self._lock:
            self._storage.set(f"{self._key_prefix}{lru_key}", time.time())
    
    def get_timestamp(self, lru_key: str) -> Optional[float]:
        """Get the last access timestamp for a given LRU key."""
        with self._lock:
            return self._storage.get(f"{self._key_prefix}{lru_key}")
    
    def get_oldest_key(self, keys: List[str]) -> Optional[str]:
        """Get the oldest (least recently used) key from a list of keys.
        
        Args:
            keys: List of LRU keys to compare
            
        Returns:
            The oldest key, or None if the list is empty
        """
        if not keys:
            return None
            
        with self._lock:
            # Get timestamps for all keys
            timestamps = {}
            for key in keys:
                ts = self._storage.get(f"{self._key_prefix}{key}")
                if ts is not None:
                    timestamps[key] = ts
            
            # If no keys are tracked yet, return the first one from the input
            if not timestamps:
                return keys[0]
            
            # Return the key with the oldest timestamp
            return min(timestamps.keys(), key=lambda k: timestamps[k])
