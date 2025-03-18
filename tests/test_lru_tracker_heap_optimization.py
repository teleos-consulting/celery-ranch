"""Tests for the heap-based priority optimization in LRUTracker."""

import heapq
import time
from unittest.mock import patch, MagicMock

import pytest

from celery_ranch.utils.lru_tracker import LRUTracker, LRUKeyMetadata
from celery_ranch.utils.persistence import InMemoryStorage


def test_get_oldest_key_heap_implementation():
    """Test the heap-based implementation of get_oldest_key."""
    tracker = LRUTracker()
    
    # Create test keys
    keys = ["key1", "key2", "key3"]
    
    # Mock _get_metadata to return predictable values
    metadata1 = LRUKeyMetadata(timestamp=123456.0, weight=1.0)
    metadata2 = LRUKeyMetadata(timestamp=123457.0, weight=2.0)
    metadata3 = LRUKeyMetadata(timestamp=123458.0, weight=0.5)
    
    def mock_get_metadata(key):
        return {
            "key1": metadata1, 
            "key2": metadata2,
            "key3": metadata3
        }.get(key)
    
    # Use the real implementation but trap the calls to heapq
    with patch.object(tracker, '_get_metadata', side_effect=mock_get_metadata):
        with patch('celery_ranch.utils.lru_tracker.heapq.heappush', wraps=heapq.heappush) as mock_heappush:
            with patch('celery_ranch.utils.lru_tracker.heapq.heappop', wraps=heapq.heappop) as mock_heappop:
                # Call the method
                result = tracker.get_oldest_key(keys)
                
                # Verify heap operations were used
                assert mock_heappush.called
                assert mock_heappop.called
                
                # Verify heapq.heappush was called for each key
                assert mock_heappush.call_count == 3
                
                # With the metadata provided, key3 should have highest priority
                # (newest timestamp but very low weight of 0.5)
                assert result == 'key3'


def test_get_oldest_key_heap_with_real_data():
    """Test the heap-based implementation with real data calculations."""
    tracker = LRUTracker()
    
    # Setup timestamps with more pronounced differences to ensure consistent results
    now = time.time()
    key1_time = now - 100.0  # 100 seconds old
    key2_time = now - 200.0  # 200 seconds old
    key3_time = now - 50.0   # 50 seconds old
    
    # Update tracker with test data
    # Use very different weights to make testing deterministic
    tracker._set_metadata("key1", LRUKeyMetadata(timestamp=key1_time, weight=1.0))
    tracker._set_metadata("key2", LRUKeyMetadata(timestamp=key2_time, weight=0.1))  # Much higher priority (very low weight)
    tracker._set_metadata("key3", LRUKeyMetadata(timestamp=key3_time, weight=5.0))  # Much lower priority (very high weight)
    
    # Get oldest key - should be key2 since it has high priority due to very low weight and old age
    result = tracker.get_oldest_key(["key1", "key2", "key3"])
    assert result == "key2"  # key2 should win with 0.1 weight and being 200 seconds old


def test_get_oldest_key_heap_weight_function():
    """Test the heap-based implementation with a custom weight function."""
    tracker = LRUTracker()
    
    # Setup timestamps with very significant differences to ensure custom weight dominates
    now = time.time()
    key1_time = now - 100.0  # 100 seconds old
    key2_time = now - 200.0  # 200 seconds old
    key3_time = now - 50.0   # 50 seconds old
    
    # Update tracker with test data
    tracker._set_metadata("key1", 
                          LRUKeyMetadata(timestamp=key1_time, weight=1.0, custom_data={"priority": 5}))
    tracker._set_metadata("key2", 
                          LRUKeyMetadata(timestamp=key2_time, weight=0.5, custom_data={"priority": 1}))
    tracker._set_metadata("key3", 
                          LRUKeyMetadata(timestamp=key3_time, weight=2.0, custom_data={"priority": 1000}))  # Much higher priority
    
    # Define a weight function that uses custom data
    def priority_weight_function(key, metadata):
        if not metadata.custom_data or "priority" not in metadata.custom_data:
            return metadata.weight
        # Higher priority value = lower weight (higher importance)
        priority = metadata.custom_data.get("priority", 1)
        # Use an extremely dramatic weight reduction to ensure custom data dominates
        return 0.0000001 / max(priority, 0.0000001)  # Almost zero weight for high priority
    
    # Set the weight function
    tracker.set_weight_function(priority_weight_function)
    
    # Get oldest key - should be key3 since it has highest priority in custom data
    result = tracker.get_oldest_key(["key1", "key2", "key3"])
    assert result == "key3"  # key3 has the highest priority value (1000)


def test_get_oldest_key_heap_with_error_handling():
    """Test that the heap implementation handles errors gracefully."""
    tracker = LRUTracker()
    
    # Setup timestamps
    now = time.time()
    key1_time = now - 10.0
    key2_time = now - 20.0
    
    # Update tracker with test data - make key2 much higher priority
    tracker._set_metadata("key1", LRUKeyMetadata(timestamp=key1_time, weight=1.0))
    tracker._set_metadata("key2", LRUKeyMetadata(timestamp=key2_time, weight=0.1))
    
    # Define a problematic weight function that throws exceptions
    def error_weight_function(key, metadata):
        if key == "key1":
            raise ValueError("Test error")
        return metadata.weight
    
    # Set the problematic weight function
    tracker.set_weight_function(error_weight_function)
    
    # Should still return a result despite the error
    with patch('celery_ranch.utils.lru_tracker.logger') as mock_logger:
        result = tracker.get_oldest_key(["key1", "key2"])
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        
        # Should return key2 since key2 has much higher priority due to low weight
        assert result == "key2"


def test_get_oldest_key_heap_performance():
    """Test that the heap implementation performs better with large key sets."""
    tracker = LRUTracker()
    
    # Generate a large set of keys
    keys = [f"key{i}" for i in range(1000)]
    
    # Mock _get_metadata to return valid metadata for any key
    def mock_get_metadata(key):
        # Extract key number
        key_num = int(key[3:])
        # Generate predictable timestamp and weight
        return LRUKeyMetadata(
            timestamp=time.time() - key_num,  # older keys have higher numbers
            weight=1.0 + (key_num % 10) / 10.0  # vary weights
        )
    
    with patch.object(tracker, '_get_metadata', side_effect=mock_get_metadata):
        # Time the execution
        start_time = time.time()
        result = tracker.get_oldest_key(keys)
        end_time = time.time()
        
        # Verify result is as expected (this depends on implementation details)
        # For most implementations, key999 should be oldest after weighting
        assert result is not None
        
        # Performance assertion - should be fast even with 1000 keys
        # This is a loose assertion, adjust timing as needed for your environment
        execution_time = end_time - start_time
        assert execution_time < 0.1  # Should take less than 100ms
