import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ranch.utils.persistence import InMemoryStorage, StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class LRUKeyMetadata:
    """Metadata for an LRU key."""
    timestamp: float  # Last access timestamp
    weight: float = 1.0  # Priority weight (1.0 = normal priority)
    tags: Optional[Dict[str, str]] = None  # Optional tags for the key


class LRUTracker:
    """Tracks the least recently used status of task keys with optional weights.
    
    This enhanced version supports weighted prioritization, allowing some clients
    to have higher or lower priority than others.
    """

    def __init__(self, storage: Optional[StorageBackend] = None) -> None:
        """Initialize the LRU tracker.
        
        Args:
            storage: Storage backend to use for persistence. If None, uses in-memory storage.
        """
        # Use the provided storage or create an in-memory one
        self._storage = storage or InMemoryStorage()
        self._lock = threading.RLock()
        self._key_prefix = "lru:"
        self._metadata_prefix = "lru_meta:"

    def update_timestamp(self, lru_key: str) -> None:
        """Update the last access timestamp for a given LRU key.
        
        Args:
            lru_key: The LRU key to update
        """
        with self._lock:
            # Get existing metadata if available
            metadata = self._get_metadata(lru_key)
            if metadata:
                metadata.timestamp = time.time()
            else:
                # Create new metadata with default weight
                metadata = LRUKeyMetadata(
                    timestamp=time.time(),
                    weight=1.0
                )
                
            # Store updated metadata
            self._set_metadata(lru_key, metadata)

    def set_weight(self, lru_key: str, weight: float) -> None:
        """Set the priority weight for a given LRU key.
        
        Higher weight values result in lower priority (longer waits between task execution).
        Lower weight values result in higher priority (shorter waits between task execution).
        
        For example:
        - Weight of 0.5 means twice the priority of weight 1.0
        - Weight of 2.0 means half the priority of weight 1.0
        
        Args:
            lru_key: The LRU key to update
            weight: The priority weight (must be positive)
        
        Raises:
            ValueError: If weight is not positive
        """
        if weight <= 0:
            raise ValueError("Weight must be positive")
            
        with self._lock:
            # Get existing metadata if available
            metadata = self._get_metadata(lru_key)
            if metadata:
                metadata.weight = weight
                # Reset timestamp when weight changes
                metadata.timestamp = time.time()
            else:
                # Create new metadata with specified weight
                metadata = LRUKeyMetadata(
                    timestamp=time.time(),
                    weight=weight
                )
                
            # Store updated metadata
            self._set_metadata(lru_key, metadata)
            logger.debug(f"Set weight {weight} for key {lru_key}")

    def add_tag(self, lru_key: str, tag_name: str, tag_value: str) -> None:
        """Add a tag to an LRU key.
        
        Tags can be used for grouping or categorizing keys.
        
        Args:
            lru_key: The LRU key to tag
            tag_name: The tag name
            tag_value: The tag value
        """
        with self._lock:
            # Get existing metadata if available
            metadata = self._get_metadata(lru_key)
            if metadata:
                if metadata.tags is None:
                    metadata.tags = {}
                metadata.tags[tag_name] = tag_value
            else:
                # Create new metadata with tag
                metadata = LRUKeyMetadata(
                    timestamp=time.time(),
                    weight=1.0,
                    tags={tag_name: tag_value}
                )
                
            # Store updated metadata
            self._set_metadata(lru_key, metadata)

    def get_tags(self, lru_key: str) -> Optional[Dict[str, str]]:
        """Get tags for an LRU key.
        
        Args:
            lru_key: The LRU key
            
        Returns:
            Dictionary of tags or None if no tags exist
        """
        metadata = self._get_metadata(lru_key)
        return metadata.tags if metadata else None

    def get_metadata(self, lru_key: str) -> Optional[LRUKeyMetadata]:
        """Get all metadata for an LRU key.
        
        Args:
            lru_key: The LRU key
            
        Returns:
            Complete metadata or None if not found
        """
        return self._get_metadata(lru_key)

    def get_timestamp(self, lru_key: str) -> Optional[float]:
        """Get the last access timestamp for a given LRU key.
        
        Args:
            lru_key: The LRU key
            
        Returns:
            Timestamp as a float or None if not found
        """
        metadata = self._get_metadata(lru_key)
        return metadata.timestamp if metadata else None

    def get_weight(self, lru_key: str) -> float:
        """Get the priority weight for a given LRU key.
        
        Args:
            lru_key: The LRU key
            
        Returns:
            Weight as a float (defaults to 1.0 if not set)
        """
        metadata = self._get_metadata(lru_key)
        return metadata.weight if metadata else 1.0

    def get_oldest_key(self, keys: List[str]) -> Optional[str]:
        """Get the oldest (least recently used) key from a list of keys,
        taking priority weights into account.

        Args:
            keys: List of LRU keys to compare

        Returns:
            The key with highest priority (oldest * weight), or None if the list is empty
        """
        if not keys:
            return None

        with self._lock:
            # Get weighted timestamps for all keys
            now = time.time()
            weighted_times: Dict[str, Tuple[float, float]] = {}
            
            for key in keys:
                metadata = self._get_metadata(key)
                
                if metadata:
                    # Calculate weighted time: actual_time * weight
                    weighted_time = (now - metadata.timestamp) * metadata.weight
                    weighted_times[key] = (weighted_time, metadata.timestamp)
                else:
                    # Use default weight if no metadata
                    weighted_times[key] = (now, now)

            # If no keys are tracked yet, return the first one from the input
            if not weighted_times:
                return keys[0]

            # Return the key with the highest weighted time (most overdue according to its weight)
            # In case of a tie, use the oldest actual timestamp
            return max(weighted_times.keys(), 
                       key=lambda k: (weighted_times[k][0], weighted_times[k][1]))

    def get_keys_by_tag(self, tag_name: str, tag_value: Optional[str] = None) -> List[str]:
        """Get all keys with a specific tag.
        
        Args:
            tag_name: The tag name to search for
            tag_value: Optional specific value to match (if None, matches any value)
            
        Returns:
            List of keys with the specified tag
        """
        matching_keys = []
        
        # This is inefficient but we don't expect a large number of keys
        # For production use, this could be optimized with a secondary index
        for key in self._get_all_keys():
            metadata = self._get_metadata(key)
            if metadata and metadata.tags:
                if tag_name in metadata.tags:
                    if tag_value is None or metadata.tags[tag_name] == tag_value:
                        matching_keys.append(key)
        
        return matching_keys

    # Private helper methods
    
    def _get_metadata_key(self, lru_key: str) -> str:
        """Create a metadata key for a given LRU key."""
        return f"{self._metadata_prefix}{lru_key}"
        
    def _get_metadata(self, lru_key: str) -> Optional[LRUKeyMetadata]:
        """Get metadata for an LRU key."""
        with self._lock:
            # Check for metadata first
            metadata = self._storage.get(self._get_metadata_key(lru_key))
            if metadata:
                return metadata
                
            # Fall back to legacy timestamp if exists
            legacy_ts = self._storage.get(f"{self._key_prefix}{lru_key}")
            if legacy_ts is not None:
                # Convert legacy timestamp to metadata
                return LRUKeyMetadata(timestamp=legacy_ts, weight=1.0)
                
            return None
            
    def _set_metadata(self, lru_key: str, metadata: LRUKeyMetadata) -> None:
        """Store metadata for an LRU key."""
        with self._lock:
            # Store both metadata and legacy timestamp for backward compatibility
            self._storage.set(self._get_metadata_key(lru_key), metadata)
            self._storage.set(f"{self._key_prefix}{lru_key}", metadata.timestamp)
            
    def _get_all_keys(self) -> List[str]:
        """Get all LRU keys with metadata."""
        with self._lock:
            # Get metadata keys
            meta_keys = self._storage.get_keys_by_prefix(self._metadata_prefix)
            prefix_len = len(self._metadata_prefix)
            return [k[prefix_len:] for k in meta_keys]
