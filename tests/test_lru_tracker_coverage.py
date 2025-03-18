"""Tests for increasing coverage of the LRUTracker class."""

import pytest
from unittest.mock import patch, MagicMock

from celery_ranch.utils.lru_tracker import LRUTracker


def test_lru_tracker_missing_coverage():
    """Test to cover missing lines in LRUTracker."""
    tracker = LRUTracker()
    
    # Test set_weight with a new key (coverage for lines 88-90)
    key = "new_key_for_weight"
    tracker.set_weight(key, 2.5)
    assert tracker.get_weight(key) == 2.5
    
    # Test add_tag with a new key (coverage for line 114)
    key = "new_key_for_tag"
    tracker.add_tag(key, "test_tag", "test_value")
    tags = tracker.get_tags(key)
    assert tags == {"test_tag": "test_value"}
    
    # Test set_custom_data with a new key (coverage for lines 139-141)
    key = "new_key_for_custom_data"
    tracker.set_custom_data(key, "test_key", "test_value")
    custom_data = tracker.get_custom_data(key)
    assert custom_data == {"test_key": "test_value"}
    
    # Test get_metadata directly (coverage for line 204)
    key = "metadata_test_key"
    tracker.update_timestamp(key)
    metadata = tracker.get_metadata(key)
    assert metadata is not None
    assert metadata.timestamp > 0
    assert metadata.weight == 1.0
    
    # Test get_weight and get_tags with non-existent key (coverage for line 227-228)
    assert tracker.get_weight("non_existent_key") == 1.0
    assert tracker.get_tags("non_existent_key") is None
    
    # Test get_oldest_key with empty weighted_times (coverage for line 284)
    with patch.object(tracker, '_get_metadata', return_value=None):
        # This ensures the weighted_times dict will be empty
        assert tracker.get_oldest_key(["test_key"]) == "test_key"
    
    # Test get_oldest_key with no metadata (coverage for line 280)
    with patch.object(tracker, '_get_metadata', return_value=None):
        result = tracker.get_oldest_key(["key1", "key2"])
        assert result in ["key1", "key2"]


def test_lru_tracker_weight_function_errors():
    """Test the error handling in the weight function."""
    tracker = LRUTracker()
    
    # Setup some keys
    tracker.update_timestamp("client1")
    tracker.update_timestamp("client2")
    
    # Test weight function returning negative value (coverage for lines 261-266)
    def negative_weight_function(lru_key, metadata):
        return -1.0
    
    tracker.set_weight_function(negative_weight_function)
    
    # Should use default weight due to negative return value
    with patch('celery_ranch.utils.lru_tracker.logger') as mock_logger:
        oldest = tracker.get_oldest_key(["client1", "client2"])
        assert oldest in ["client1", "client2"]
        mock_logger.warning.assert_called()


if __name__ == "__main__":
    test_lru_tracker_missing_coverage()
    test_lru_tracker_weight_function_errors()