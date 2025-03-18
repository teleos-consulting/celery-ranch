"""Additional tests for edge cases in LRUTracker."""

import time
from unittest.mock import patch, MagicMock

import pytest

from celery_ranch.utils.lru_tracker import LRUTracker, LRUKeyMetadata
from celery_ranch.utils.persistence import InMemoryStorage


def test_set_weight_with_negative_value():
    """Test that set_weight raises ValueError with non-positive weight values."""
    tracker = LRUTracker()
    
    with pytest.raises(ValueError, match="Weight must be positive"):
        tracker.set_weight("test_key", -1.0)
    
    with pytest.raises(ValueError, match="Weight must be positive"):
        tracker.set_weight("test_key", 0)


def test_add_tag_with_null_tags():
    """Test adding a tag to metadata that has null tags."""
    # Create a tracker with mocked storage
    storage = InMemoryStorage()
    tracker = LRUTracker(storage=storage)
    
    # Create metadata with None tags
    key = "null_tags_key"
    metadata = LRUKeyMetadata(timestamp=time.time(), weight=1.0, tags=None)
    
    # Set the metadata directly in storage
    with patch.object(tracker, '_get_metadata', return_value=metadata):
        with patch.object(tracker, '_set_metadata') as mock_set:
            # Add a tag - this should initialize the tags dict
            tracker.add_tag(key, "test_tag", "test_value")
            
            # Get the metadata passed to _set_metadata
            call_args = mock_set.call_args[0]
            updated_metadata = call_args[1]
            
            # Verify tags were initialized properly
            assert updated_metadata.tags == {"test_tag": "test_value"}


def test_set_custom_data_with_null_data():
    """Test setting custom data when custom_data is None."""
    # Create a tracker with mocked storage
    storage = InMemoryStorage()
    tracker = LRUTracker(storage=storage)
    
    # Create metadata with None custom_data
    key = "null_custom_data_key"
    metadata = LRUKeyMetadata(timestamp=time.time(), weight=1.0, custom_data=None)
    
    # Set the metadata directly in storage
    with patch.object(tracker, '_get_metadata', return_value=metadata):
        with patch.object(tracker, '_set_metadata') as mock_set:
            # Set custom data - this should initialize the custom_data dict
            tracker.set_custom_data(key, "test_key", "test_value")
            
            # Get the metadata passed to _set_metadata
            call_args = mock_set.call_args[0]
            updated_metadata = call_args[1]
            
            # Verify custom_data was initialized properly
            assert updated_metadata.custom_data == {"test_key": "test_value"}


def test_get_oldest_key_with_empty_keys():
    """Test that get_oldest_key returns None for empty list input."""
    tracker = LRUTracker()
    result = tracker.get_oldest_key([])
    assert result is None


def test_get_oldest_key_with_empty_weighted_times():
    """Test get_oldest_key when no metadata is available for any keys."""
    tracker = LRUTracker()
    keys = ["key1", "key2", "key3"]
    
    # Setup _get_metadata to return None for any key
    # This will result in an empty weighted_times dictionary
    # This should trigger the edge case at line 281
    with patch.object(tracker, '_get_metadata', return_value=None):
        with patch.object(tracker, '_storage') as mock_storage:
            # Mock storage to ensure no actual storage access happens
            mock_storage.get.return_value = None
            
            # Call get_oldest_key - this will end up at line 281 where it returns keys[0]
            result = tracker.get_oldest_key(keys)
            assert result == "key1"


def test_get_metadata_with_legacy_timestamp():
    """Test legacy timestamp conversion in _get_metadata."""
    # Create tracker with mocked storage
    storage = MagicMock()
    tracker = LRUTracker(storage=storage)
    
    # Setup mock behavior - no metadata but has legacy timestamp
    storage.get.side_effect = lambda key: {
        f"{tracker._key_prefix}test_key:meta": None,
        f"{tracker._key_prefix}test_key": 12345.0
    }.get(key)
    
    # Get metadata
    metadata = tracker._get_metadata("test_key")
    
    # Verify conversion from legacy timestamp
    assert metadata is not None
    assert metadata.timestamp == 12345.0
    assert metadata.weight == 1.0
    assert metadata.tags is None
    assert metadata.custom_data is None