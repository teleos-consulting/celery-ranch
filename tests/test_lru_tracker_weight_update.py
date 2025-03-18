"""Tests for LRUTracker weight update functionality."""

import time
from unittest.mock import patch, MagicMock

import pytest

from celery_ranch.utils.lru_tracker import LRUTracker, LRUKeyMetadata
from celery_ranch.utils.persistence import InMemoryStorage


def test_update_existing_key_weight():
    """Test updating the weight of an existing key with metadata.
    
    This specifically targets lines 88-90 in lru_tracker.py where the
    weight is updated and timestamp is reset.
    """
    # Setup
    tracker = LRUTracker()
    key = "test_key"
    
    # Mock time to control timestamps
    with patch('celery_ranch.utils.lru_tracker.time') as mock_time:
        # Setup initial timestamp and metadata
        initial_time = 1000.0
        mock_time.time.return_value = initial_time
        
        # Create metadata with initial weight
        metadata = LRUKeyMetadata(timestamp=initial_time, weight=1.0)
        
        # Set up get_metadata to return our controlled metadata
        with patch.object(tracker, '_get_metadata', return_value=metadata):
            # Set up set_metadata to verify the changes
            with patch.object(tracker, '_set_metadata') as mock_set_metadata:
                # Set a new timestamp for the update
                new_time = 2000.0
                mock_time.time.return_value = new_time
                
                # Update the weight - this should trigger lines 88-90
                new_weight = 5.0
                tracker.set_weight(key, new_weight)
                
                # Verify the metadata was updated properly
                assert metadata.weight == new_weight
                assert metadata.timestamp == new_time  # Timestamp should be reset
                
                # Verify _set_metadata was called with the updated metadata
                mock_set_metadata.assert_called_once_with(key, metadata)