"""
Celery Ranch - A Celery extension for fair task scheduling with LRU prioritization.

Celery Ranch provides a way to fairly distribute tasks among multiple clients using
Least Recently Used (LRU) prioritization. This prevents high-volume clients
from monopolizing worker resources.

Basic usage:
    from celery import Celery
    from celery_ranch import lru_task

    app = Celery("tasks")

    @lru_task(app)
    def process_data(data):
        # Process data
        return result

    # Using LRU prioritization - "client_id" is the LRU key
    result = process_data.lru_delay("client_id", data_to_process)
"""

from celery_ranch.task import lru_task
from celery_ranch.utils.persistence import SerializerType
from celery_ranch.utils.prioritize import get_status

__version__ = "0.1.1"
__all__ = ["lru_task", "SerializerType", "get_status"]
