import heapq
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from celery_ranch.utils.persistence import InMemoryStorage, StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class LRUKeyMetadata:
    """Metadata for an LRU key."""

    timestamp: float  # Last access timestamp
    weight: float = 1.0  # Priority weight (1.0 = normal priority)
    tags: Optional[Dict[str, str]] = None  # Optional tags for the key
    # Optional custom data for weight functions
    custom_data: Optional[Dict[str, Any]] = None


class LRUTracker:
    """Tracks the least recently used status of task keys with optional weights.

    This enhanced version supports weighted prioritization, allowing some clients
    to have higher or lower priority than others. It also supports custom dynamic
    weight functions that can be applied at prioritization time.
    """

    def __init__(self, storage: Optional[StorageBackend] = None) -> None:
        """Initialize the LRU tracker.

        Args:
            storage: Storage backend to use for persistence. If None, uses
            in-memory storage.
        """
        # Use the provided storage or create an in-memory one
        self._storage = storage or InMemoryStorage()
        self._lock = threading.RLock()
        self._key_prefix = "lru:"
        self._metadata_prefix = "lru_meta:"
        # Default weight function is None
        self._weight_function: Optional[Callable[[str, LRUKeyMetadata], float]] = None

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
                metadata = LRUKeyMetadata(timestamp=time.time(), weight=1.0)

            # Store updated metadata
            self._set_metadata(lru_key, metadata)

    def set_weight(self, lru_key: str, weight: float) -> None:
        """Set the priority weight for a given LRU key.

        Higher weight values result in lower priority (longer waits).
        Lower weight values result in higher priority (shorter waits).

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
                metadata = LRUKeyMetadata(timestamp=time.time(), weight=weight)

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
                    timestamp=time.time(), weight=1.0, tags={tag_name: tag_value}
                )

            # Store updated metadata
            self._set_metadata(lru_key, metadata)

    def set_custom_data(self, lru_key: str, key: str, value: Any) -> None:
        """Set custom data for an LRU key.

        Custom data can be used by dynamic weight functions to determine priority.

        Args:
            lru_key: The LRU key to update
            key: The custom data key
            value: The custom data value
        """
        with self._lock:
            # Get existing metadata if available
            metadata = self._get_metadata(lru_key)
            if metadata:
                if metadata.custom_data is None:
                    metadata.custom_data = {}
                metadata.custom_data[key] = value
            else:
                # Create new metadata with custom data
                metadata = LRUKeyMetadata(
                    timestamp=time.time(), weight=1.0, custom_data={key: value}
                )

            # Store updated metadata
            self._set_metadata(lru_key, metadata)

    def get_custom_data(self, lru_key: str) -> Optional[Dict[str, Any]]:
        """Get custom data for an LRU key.

        Args:
            lru_key: The LRU key

        Returns:
            Dictionary of custom data or None if no custom data exists
        """
        metadata = self._get_metadata(lru_key)
        return metadata.custom_data if metadata else None

    def set_weight_function(
        self, weight_function: Optional[Callable[[str, LRUKeyMetadata], float]]
    ) -> None:
        """Set a custom dynamic weight function.

        The weight function should take an LRU key and its metadata and return a float
        representing the priority weight. Lower values = higher priority.

        Args:
            weight_function: Function that takes (lru_key, metadata) and returns
                a float, or None to use the static weights
        """
        with self._lock:
            self._weight_function = weight_function
            name = weight_function.__name__ if weight_function else "None"
            logger.info(f"Set custom weight function: {name}")

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

        If a custom weight function is set, it will be used to calculate
        priority for each key.

        Optimized implementation using a heap priority queue for better
        performance with large numbers of keys.

        Args:
            keys: List of LRU keys to compare

        Returns:
            The key with highest priority (oldest * weight), or None if empty
        """
        if not keys:
            return None

        with self._lock:
            # Use a priority queue for better performance with large lists
            priority_queue: List[Tuple[float, float, str]] = []
            now = time.time()

            # Build the priority queue with O(n) complexity
            for key in keys:
                metadata = self._get_metadata(key)

                if metadata:
                    # Calculate effective weight - either custom or static
                    try:
                        if self._weight_function:
                            effective_weight = self._weight_function(key, metadata)
                            if effective_weight <= 0:
                                key_msg = f"Weight function for {key}"
                                logger.warning(
                                    f"{key_msg} returned non-positive weight, "
                                    f"using default weight instead"
                                )
                                effective_weight = metadata.weight
                        else:
                            effective_weight = metadata.weight
                    except Exception as e:
                        logger.error(f"Error in weight function for key {key}: {e}")
                        effective_weight = metadata.weight

                    # Calculate weighted time: actual_time * effective_weight
                    elapsed_time = now - metadata.timestamp
                    # Lower weight = higher priority, so divide by weight for priority
                    # This matches the original algorithm's max() usage where higher
                    # weighted_time values have higher priority
                    priority_value = elapsed_time / effective_weight

                    # Use negative values because heapq is a min-heap but we want max
                    # Priority: (negative priority_value, negative timestamp, key)
                    # Ensures highest priority_value first, with timestamp as tiebreaker
                    priority = (-priority_value, -metadata.timestamp, key)
                else:
                    # Default priority for keys without metadata
                    priority = (0, -now, key)

                heapq.heappush(priority_queue, priority)

            # If no keys are tracked, return the first one from the input
            if not priority_queue:
                return keys[0]

            # Get the highest priority key (min-heap with negated values = max)
            _, _, oldest_key = heapq.heappop(priority_queue)
            return oldest_key

    def get_keys_by_tag(
        self, tag_name: str, tag_value: Optional[str] = None
    ) -> List[str]:
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
